"""Pure Render deploy orchestration helpers.

This module receives already-resolved deployment inputs and credentials. It does
not evaluate approval, policy or CI gates; callers must do that before invoking
these functions.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

import httpx

from deploy_orchestrator_mcp.audit import create_audit_event
from deploy_orchestrator_mcp.redaction import redact

RENDER_API_BASE_URL = "https://api.render.com/v1"
FINAL_DEPLOY_STATUSES = {"live", "deactivated", "build_failed", "update_failed", "canceled"}


def _api_key(credentials: Mapping[str, Any] | str | None) -> str | None:
    if isinstance(credentials, str):
        return credentials
    if isinstance(credentials, Mapping):
        value = credentials.get("api_key") or credentials.get("token") or credentials.get("render_api_key")
        return str(value) if value else None
    return None


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _json_or_text(response: httpx.Response) -> Any:
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {"text": response.text}


def _normalize_deploy(data: Any) -> dict[str, Any]:
    deploy = data.get("deploy") if isinstance(data, Mapping) and isinstance(data.get("deploy"), Mapping) else data
    if isinstance(deploy, list):
        deploy = deploy[0] if deploy else {}
    if not isinstance(deploy, Mapping):
        return {"raw": deploy}
    return {
        "id": deploy.get("id"),
        "status": deploy.get("status"),
        "commit": deploy.get("commit"),
        "created_at": deploy.get("createdAt") or deploy.get("created_at"),
        "updated_at": deploy.get("updatedAt") or deploy.get("updated_at"),
        "finished_at": deploy.get("finishedAt") or deploy.get("finished_at"),
        "raw": deploy,
    }


def _client(client: httpx.Client | None = None, timeout: float = 30.0) -> httpx.Client:
    return client or httpx.Client(base_url=RENDER_API_BASE_URL, timeout=timeout)


def _request(method: str, path: str, *, api_key: str, client: httpx.Client | None = None,
             params: dict[str, Any] | None = None, json: dict[str, Any] | None = None,
             operation: str) -> tuple[Any, dict[str, Any]]:
    owns_client = client is None
    http_client = _client(client)
    try:
        response = http_client.request(method, path, headers=_headers(api_key), params=params, json=json)
        body = _json_or_text(response)
        audit_event = create_audit_event(
            "render.api.call",
            {"provider": "render", "operation": operation, "method": method,
             "path": path, "status_code": response.status_code, "attempts": 1},
        )
        if response.is_error:
            return {"error": "render_api_error", "status_code": response.status_code, "response": body}, audit_event
        return body, audit_event
    except httpx.HTTPError as exc:
        audit_event = create_audit_event(
            "render.api.call",
            {"provider": "render", "operation": operation, "method": method,
             "path": path, "status_code": 0, "attempts": 1},
        )
        return {"error": "render_connection_error", "status_code": 0, "message": str(exc)}, audit_event
    finally:
        if owns_client:
            http_client.close()


def trigger_deploy(plan: Mapping[str, Any], credentials: Mapping[str, Any] | str,
                   *, client: httpx.Client | None = None, clear_cache: bool = False) -> dict[str, Any]:
    """Trigger a Render deploy. The caller must pass an already-gated plan."""
    api_key = _api_key(credentials)
    service_id = str(plan.get("service_id") or "")
    if not api_key:
        return {"provider": "render", "triggered": False, "deploy_id": None, "errors": ["Render API key is not configured"]}
    if not service_id:
        return {"provider": "render", "triggered": False, "deploy_id": None, "errors": ["service_id is required"]}
    payload = {"clearCache": "clear"} if clear_cache else None
    body, audit_event = _request("POST", f"/services/{service_id}/deploys", api_key=api_key,
                                 client=client, json=payload, operation="deploy_staging")
    if isinstance(body, Mapping) and body.get("error"):
        return redact({"provider": "render", "triggered": False, "deploy_id": None,
                       "errors": [body], "audit_event": audit_event})
    deploy = _normalize_deploy(body)
    return redact({"provider": "render", "triggered": True, "deploy_id": deploy.get("id"),
                   "status": deploy.get("status"), "deploy": deploy,
                   "logs_url": f"/deploys/{deploy.get('id')}/logs" if deploy.get("id") else None,
                   "audit_event": audit_event})


def poll_deploy_status(deploy_id: str | None, credentials: Mapping[str, Any] | str,
                       *, service_id: str, timeout_s: int = 300,
                       poll_interval_s: float = 5.0,
                       client: httpx.Client | None = None) -> dict[str, Any]:
    """Read or poll Render deploy status until final state or timeout."""
    api_key = _api_key(credentials)
    if not api_key:
        return {"provider": "render", "ok": False, "errors": ["Render API key is not configured"]}
    deadline = time.monotonic() + max(timeout_s, 0)
    attempts = 0
    while True:
        attempts += 1
        path = f"/services/{service_id}/deploys/{deploy_id}" if deploy_id else f"/services/{service_id}/deploys"
        params = None if deploy_id else {"limit": 1}
        body, audit_event = _request("GET", path, api_key=api_key, client=client,
                                     params=params, operation="get_deploy_status")
        if isinstance(body, Mapping) and body.get("error"):
            return redact({"provider": "render", "ok": False, "service_id": service_id,
                           "deploy_id": deploy_id, "errors": [body], "audit_event": audit_event})
        deploy = _normalize_deploy(body)
        status = deploy.get("status")
        if not timeout_s or status in FINAL_DEPLOY_STATUSES or time.monotonic() >= deadline:
            return redact({"provider": "render", "ok": True, "service_id": service_id,
                           "deploy_id": deploy.get("id") or deploy_id, "status": status,
                           "complete": status in FINAL_DEPLOY_STATUSES, "attempts": attempts,
                           "deploy": deploy, "duration_seconds": 0 if not timeout_s else max(0, int(time.monotonic() - (deadline - timeout_s))),
                           "audit_event": audit_event})
        time.sleep(max(poll_interval_s, 0))


def fetch_logs(deploy_id: str, credentials: Mapping[str, Any] | str,
               *, tail: int = 100, client: httpx.Client | None = None) -> dict[str, Any]:
    """Fetch Render build logs for a deploy."""
    api_key = _api_key(credentials)
    if not api_key:
        return {"provider": "render", "deploy_id": deploy_id, "lines": [], "errors": ["Render API key is not configured"]}
    capped_tail = min(tail, 500)
    body, audit_event = _request("GET", f"/deploys/{deploy_id}/logs", api_key=api_key,
                                 client=client, params={"limit": capped_tail}, operation="get_build_logs")
    if isinstance(body, Mapping) and body.get("error"):
        return redact({"provider": "render", "deploy_id": deploy_id, "lines": [],
                       "errors": [body.get("response", {}).get("message", "unknown error")],
                       "audit_event": audit_event})
    raw_lines = body if isinstance(body, list) else body.get("logs", []) if isinstance(body, Mapping) else []
    lines = [{"timestamp": entry.get("timestamp"), "message": entry.get("message", "")}
             for entry in raw_lines if isinstance(entry, Mapping)]
    return redact({"provider": "render", "deploy_id": deploy_id, "lines": lines,
                   "truncated": len(lines) >= capped_tail, "audit_event": audit_event})


def run_healthcheck(url: str, *, retries: int = 3, expected_status: int = 200,
                    timeout_seconds: float = 10.0,
                    client: httpx.Client | None = None) -> dict[str, Any]:
    """Run an HTTP healthcheck with bounded retries."""
    if not url.startswith(("http://", "https://")):
        return {"provider": "render", "healthy": False, "status_code": None,
                "errors": ["healthcheck url must start with http:// or https://"],
                "audit_event": create_audit_event("render.healthcheck.blocked",
                                                  {"provider": "render", "reason": "invalid_url"})}
    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)
    attempts = max(retries, 1)
    try:
        for attempt in range(1, attempts + 1):
            try:
                response = http_client.get(url)
                healthy = response.status_code == expected_status
                if healthy or attempt == attempts:
                    return redact({"provider": "render", "healthy": healthy,
                                   "status_code": response.status_code,
                                   "expected_status": expected_status, "url": url,
                                   "attempts": attempt,
                                   "audit_event": create_audit_event("render.healthcheck.completed",
                                                                     {"provider": "render", "url": url,
                                                                      "status_code": response.status_code,
                                                                      "healthy": healthy})})
            except httpx.HTTPError as exc:
                if attempt == attempts:
                    return redact({"provider": "render", "healthy": False,
                                   "status_code": None, "errors": [str(exc)],
                                   "url": url, "attempts": attempt,
                                   "audit_event": create_audit_event("render.healthcheck.failed",
                                                                     {"provider": "render", "url": url,
                                                                      "error": str(exc)})})
    finally:
        if owns_client:
            http_client.close()
    return {"provider": "render", "healthy": False, "status_code": None,
            "errors": ["healthcheck failed"], "url": url}
