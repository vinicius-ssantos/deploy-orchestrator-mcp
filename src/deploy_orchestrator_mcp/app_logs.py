"""Provider-agnostic application log helpers.

The helpers in this module are read-only wrappers over provider-specific log
APIs. They normalize log shapes, apply bounded tail limits and best-effort
filters, and never include raw provider credentials or unredacted log values in
audit metadata.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from deploy_orchestrator_mcp.audit import create_audit_event
from deploy_orchestrator_mcp.redaction import redact
from deploy_orchestrator_mcp.render_api import (
    render_get_build_logs,
    render_get_runtime_logs,
)

MAX_TAIL = 500

LogFetcher = Callable[..., dict[str, Any]]


def _cap_tail(tail: int | None) -> int:
    try:
        value = int(tail if tail is not None else 100)
    except (TypeError, ValueError):
        value = 100
    return max(1, min(value, MAX_TAIL))


def _message(line: Any) -> str:
    if isinstance(line, Mapping):
        return str(line.get("message") or line.get("text") or line.get("line") or "")
    return str(line)


def _timestamp(line: Any) -> str | None:
    if isinstance(line, Mapping):
        value = line.get("timestamp") or line.get("time") or line.get("created_at")
        return str(value) if value is not None else None
    return None


def _infer_level(message: str) -> str | None:
    lower = message.lower()
    if any(token in lower for token in ("error", "exception", "traceback", "failed", "failure")):
        return "error"
    if any(token in lower for token in ("warn", "warning")):
        return "warning"
    if "info" in lower:
        return "info"
    return None


def _normalize_lines(raw_lines: list[Any], *, query: str | None = None, level: str | None = None) -> list[dict[str, Any]]:
    query_lower = query.lower() if query else None
    level_lower = level.lower() if level else None
    normalized: list[dict[str, Any]] = []

    for raw in raw_lines:
        message = _message(raw)
        inferred_level = None
        if isinstance(raw, Mapping) and raw.get("level") is not None:
            inferred_level = str(raw.get("level")).lower()
        else:
            inferred_level = _infer_level(message)

        if query_lower and query_lower not in message.lower():
            continue
        if level_lower and inferred_level != level_lower:
            continue

        normalized.append({
            "timestamp": _timestamp(raw),
            "level": inferred_level,
            "message": message,
        })

    return redact(normalized)


def _unsupported_provider(provider: str, operation: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "ok": False,
        "lines": [],
        "count": 0,
        "truncated": False,
        "redacted": True,
        "errors": [f"provider '{provider}' is not supported for {operation}"],
        "audit_event": create_audit_event(
            "app.logs.blocked",
            {"provider": provider, "operation": operation, "reason": "unsupported_provider"},
        ),
    }


def _provider_error(provider: str, operation: str, target: dict[str, Any], errors: list[Any]) -> dict[str, Any]:
    metadata = {"provider": provider, "operation": operation, **target, "error_count": len(errors)}
    return redact({
        "provider": provider,
        "ok": False,
        "lines": [],
        "count": 0,
        "truncated": False,
        "redacted": True,
        "errors": errors,
        "audit_event": create_audit_event("app.logs.read.failed", metadata),
    })


def app_get_runtime_logs(
    *,
    provider: str,
    service_id: str,
    tail: int = 100,
    since: str | None = None,
    level: str | None = None,
    query: str | None = None,
    fetcher: LogFetcher | None = None,
) -> dict[str, Any]:
    """Fetch normalized runtime logs for a service."""
    provider_name = provider.lower()
    capped_tail = _cap_tail(tail)
    if provider_name != "render":
        return _unsupported_provider(provider, "runtime_logs")

    runtime_fetcher = fetcher or render_get_runtime_logs
    raw = runtime_fetcher(service_id=service_id, tail=capped_tail)
    if raw.get("errors"):
        return _provider_error(provider_name, "runtime_logs", {"service_id": service_id}, raw.get("errors", []))

    lines = _normalize_lines(raw.get("lines", []), query=query, level=level)
    return redact({
        "provider": provider_name,
        "ok": True,
        "service_id": service_id,
        "lines": lines,
        "count": len(lines),
        "truncated": bool(raw.get("truncated")) or capped_tail < (tail or capped_tail),
        "redacted": True,
        "filters": {"query": query, "level": level, "since": since},
        "audit_event": create_audit_event(
            "app.logs.read",
            {"provider": provider_name, "operation": "runtime_logs", "service_id": service_id,
             "tail": capped_tail, "count": len(lines), "filtered": bool(query or level or since)},
        ),
    })


def app_get_build_logs(
    *,
    provider: str,
    deploy_id: str,
    tail: int = 100,
    query: str | None = None,
    fetcher: LogFetcher | None = None,
) -> dict[str, Any]:
    """Fetch normalized build/deploy logs for a deployment."""
    provider_name = provider.lower()
    capped_tail = _cap_tail(tail)
    if provider_name != "render":
        return _unsupported_provider(provider, "build_logs")

    build_fetcher = fetcher or render_get_build_logs
    raw = build_fetcher(deploy_id=deploy_id, tail=capped_tail)
    if raw.get("errors"):
        return _provider_error(provider_name, "build_logs", {"deploy_id": deploy_id}, raw.get("errors", []))

    lines = _normalize_lines(raw.get("lines", []), query=query)
    return redact({
        "provider": provider_name,
        "ok": True,
        "deploy_id": deploy_id,
        "lines": lines,
        "count": len(lines),
        "truncated": bool(raw.get("truncated")) or capped_tail < (tail or capped_tail),
        "redacted": True,
        "filters": {"query": query},
        "audit_event": create_audit_event(
            "app.logs.read",
            {"provider": provider_name, "operation": "build_logs", "deploy_id": deploy_id,
             "tail": capped_tail, "count": len(lines), "filtered": bool(query)},
        ),
    })


def app_search_logs(
    *,
    provider: str,
    service_id: str,
    query: str,
    tail: int = 200,
    since: str | None = None,
    level: str | None = None,
    fetcher: LogFetcher | None = None,
) -> dict[str, Any]:
    """Search runtime logs using text and optional severity filters."""
    if not query:
        return {
            "provider": provider,
            "ok": False,
            "lines": [],
            "count": 0,
            "truncated": False,
            "redacted": True,
            "errors": ["query is required"],
            "audit_event": create_audit_event(
                "app.logs.blocked",
                {"provider": provider, "operation": "search_logs", "reason": "missing_query"},
            ),
        }
    return app_get_runtime_logs(
        provider=provider,
        service_id=service_id,
        tail=tail,
        since=since,
        level=level,
        query=query,
        fetcher=fetcher,
    )
