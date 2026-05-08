import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from deploy_orchestrator_mcp.redaction import redact

MCP_AUDIT_BACKEND_ENV = "MCP_AUDIT_BACKEND"
AUDIT_LOG_PATH_ENV = "MCP_AUDIT_LOG_PATH"
MCP_AUDIT_SUPABASE_URL_ENV = "MCP_AUDIT_SUPABASE_URL"
MCP_AUDIT_SUPABASE_KEY_ENV = "MCP_AUDIT_SUPABASE_KEY"
MCP_AUDIT_SUPABASE_TABLE_ENV = "MCP_AUDIT_SUPABASE_TABLE"
SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_SERVICE_ROLE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"
DEFAULT_AUDIT_SUPABASE_TABLE = "audit_events"

SUPABASE_AUDIT_SELECT = "id,created_at,event_type,actor,environment,provider,repository,payload"


def _default_now():
    return datetime.now(timezone.utc).isoformat()


def _configured_audit_log_path() -> str | None:
    path = os.getenv(AUDIT_LOG_PATH_ENV, "").strip()
    return path or None


def _supabase_audit_config() -> dict[str, Any]:
    url = (
        os.getenv(MCP_AUDIT_SUPABASE_URL_ENV, "").strip()
        or os.getenv(SUPABASE_URL_ENV, "").strip()
    )
    key = (
        os.getenv(MCP_AUDIT_SUPABASE_KEY_ENV, "").strip()
        or os.getenv(SUPABASE_SERVICE_ROLE_KEY_ENV, "").strip()
    )
    table = (
        os.getenv(MCP_AUDIT_SUPABASE_TABLE_ENV, DEFAULT_AUDIT_SUPABASE_TABLE).strip()
        or DEFAULT_AUDIT_SUPABASE_TABLE
    )
    return {
        "configured": bool(url and key),
        "url": url.rstrip("/"),
        "key": key,
        "table": table,
    }


def _configured_audit_backend() -> str | None:
    backend = os.getenv(MCP_AUDIT_BACKEND_ENV, "").strip().lower()
    if backend in {"jsonl", "supabase"}:
        return backend
    if _configured_audit_log_path():
        return "jsonl"
    if _supabase_audit_config()["configured"]:
        return "supabase"
    return None


def _rest_endpoint(supabase_url: str, table: str) -> str:
    return f"{supabase_url.rstrip('/')}/rest/v1/{table}"


def _supabase_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Prefer": "return=representation",
    }


class JsonlAuditLog:
    """Append-only JSONL audit log with redaction before persistence."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        redacted_event = redact(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(redacted_event, sort_keys=True) + "\n")
        return redacted_event

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        safe_limit = max(0, min(int(limit), 500))
        if safe_limit == 0:
            return []

        events: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    events.append(redact(value))

        return events[-safe_limit:]

    def status(self) -> dict[str, Any]:
        exists = self.path.exists()
        return {
            "enabled": True,
            "backend": "jsonl",
            "path": str(self.path),
            "exists": exists,
            "size_bytes": self.path.stat().st_size if exists else 0,
        }


class SupabaseAuditLog:
    """Supabase REST API-backed persistent audit log."""

    def __init__(
        self,
        *,
        supabase_url: str,
        key: str,
        table: str = DEFAULT_AUDIT_SUPABASE_TABLE,
        client: httpx.Client | None = None,
    ):
        self.supabase_url = supabase_url.rstrip("/")
        self.key = key
        self.table = table
        self._client = client

    def _request(self, method: str, *, json_body=None, params=None) -> httpx.Response:
        endpoint = _rest_endpoint(self.supabase_url, self.table)
        if self._client is not None:
            return self._client.request(
                method,
                endpoint,
                headers=_supabase_headers(self.key),
                json=json_body,
                params=params,
            )
        return httpx.request(
            method,
            endpoint,
            headers=_supabase_headers(self.key),
            json=json_body,
            params=params,
            timeout=30.0,
        )

    def _build_row(self, event: dict[str, Any]) -> dict[str, Any]:
        metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else {}
        row = {
            "event_type": event.get("type"),
            "created_at": event.get("created_at"),
            "actor": metadata.get("actor"),
            "environment": metadata.get("environment"),
            "provider": metadata.get("provider"),
            "repository": metadata.get("repository"),
            "payload": event,
        }
        return {k: v for k, v in row.items() if v is not None}

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        redacted_event = redact(event)
        row = redact(self._build_row(redacted_event))
        response = self._request("POST", json_body=row)
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, list) and body and isinstance(body[0], dict):
            return redact(body[0].get("payload") or redacted_event)
        return redacted_event

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        safe_limit = max(0, min(int(limit), 500))
        if safe_limit == 0:
            return []

        response = self._request(
            "GET",
            params={
                "select": SUPABASE_AUDIT_SELECT,
                "order": "created_at.desc",
                "limit": safe_limit,
            },
        )
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError:
            return []

        events: list[dict[str, Any]] = []
        for row in body if isinstance(body, list) else []:
            if isinstance(row, dict):
                payload = row.get("payload")
                if isinstance(payload, dict):
                    events.append(redact(payload))
        return events[::-1]

    def status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "backend": "supabase",
            "url": self.supabase_url,
            "table": self.table,
            "configured": bool(self.supabase_url and self.key),
        }


def _active_audit_log():
    backend = _configured_audit_backend()
    if backend == "jsonl":
        path = _configured_audit_log_path()
        return JsonlAuditLog(path) if path else None
    if backend == "supabase":
        config = _supabase_audit_config()
        if not config["configured"]:
            return None
        return SupabaseAuditLog(
            supabase_url=config["url"],
            key=config["key"],
            table=config["table"],
        )
    return None


def _persist_if_configured(event: dict[str, Any]) -> None:
    audit_log = _active_audit_log()
    if not audit_log:
        return
    try:
        audit_log.record(event)
    except (OSError, httpx.HTTPError, httpx.TimeoutException):
        return


def create_audit_event(event_type, metadata=None, now=None):
    """Create a redacted audit event and optionally persist it."""
    now_fn = now or _default_now
    event = {
        "type": str(event_type),
        "created_at": now_fn(),
        "metadata": redact(metadata or {}),
    }
    _persist_if_configured(event)
    return event


def create_plan_audit_event(plan, now=None):
    """Create a summary audit event for a deployment plan."""
    policy_result = plan.get("policy_result") or {}
    app_provider = plan.get("app_provider") or {}
    database_provider = plan.get("database_provider") or {}

    metadata = {
        "environment": plan.get("environment"),
        "mode": plan.get("mode"),
        "app_provider": app_provider.get("provider"),
        "database_provider": database_provider.get("provider"),
        "policy_valid": policy_result.get("valid"),
        "policy_errors": policy_result.get("errors", []),
        "approval_required": plan.get("approval_required"),
        "approval_required_actions": plan.get("approval_required_actions", []),
        "risks": plan.get("risks", []),
    }

    return create_audit_event("deployment.plan.generated", metadata, now)


def audit_log_status() -> dict[str, Any]:
    """Return safe status for the configured persistent audit backend."""
    backend = _configured_audit_backend()
    if backend == "jsonl":
        path = _configured_audit_log_path()
        if not path:
            return {"enabled": False, "backend": "jsonl", "path": None}
        return JsonlAuditLog(path).status()

    if backend == "supabase":
        config = _supabase_audit_config()
        if not config["configured"]:
            return {
                "enabled": False,
                "backend": "supabase",
                "configured": False,
                "table": config["table"],
                "errors": [
                    "Supabase audit backend requires SUPABASE_URL and "
                    "SUPABASE_SERVICE_ROLE_KEY (or MCP_AUDIT_SUPABASE_URL / "
                    "MCP_AUDIT_SUPABASE_KEY)."
                ],
            }
        return SupabaseAuditLog(
            supabase_url=config["url"],
            key=config["key"],
            table=config["table"],
        ).status()

    return {
        "enabled": False,
        "backend": None,
        "path": None,
        "exists": False,
        "size_bytes": 0,
    }


def audit_log_list(limit: int = 50) -> dict[str, Any]:
    """List recent persisted audit events with redacted output."""
    backend = _configured_audit_backend()
    safe_limit = max(0, min(int(limit), 500))

    if backend == "jsonl":
        path = _configured_audit_log_path()
        if not path:
            return {"enabled": False, "backend": "jsonl", "events": [], "limit": limit}
        events = JsonlAuditLog(path).list(limit=safe_limit)
        return {"enabled": True, "backend": "jsonl", "events": events, "limit": safe_limit}

    if backend == "supabase":
        config = _supabase_audit_config()
        if not config["configured"]:
            return {
                "enabled": False,
                "backend": "supabase",
                "events": [],
                "limit": safe_limit,
                "errors": ["Supabase audit backend is not fully configured"],
            }
        try:
            events = SupabaseAuditLog(
                supabase_url=config["url"],
                key=config["key"],
                table=config["table"],
            ).list(limit=safe_limit)
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            return {
                "enabled": True,
                "backend": "supabase",
                "events": [],
                "limit": safe_limit,
                "errors": [type(exc).__name__],
            }
        return {"enabled": True, "backend": "supabase", "events": events, "limit": safe_limit}

    return {"enabled": False, "backend": None, "events": [], "limit": limit}


class InMemoryAuditLog:
    """Simple in-memory audit log store for tests and dry-run flows."""

    def __init__(self):
        self._events = []

    def record(self, event):
        self._events.append(redact(event))
        return self._events[-1]

    def list(self):
        return list(self._events)
