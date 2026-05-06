import time
from collections.abc import Mapping
from typing import Any

import httpx

from deploy_orchestrator_mcp.audit import create_audit_event
from deploy_orchestrator_mcp.credentials import get_credential
from deploy_orchestrator_mcp.execution import evaluate_execution_gate
from deploy_orchestrator_mcp.redaction import redact

RENDER_API_BASE_URL = "https://api.render.com/v1"
FINAL_DEPLOY_STATUSES = {"live", "deactivated", "build_failed", "update_failed", "canceled"}


def _render_api_key(api_key: str | None = None) -> str | None:
    return api_key or get_credential("render")


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _client(client: httpx.Client | None = None, timeout: float = 30.0) -> httpx.Client:
    return client or httpx.Client(base_url=RENDER_API_BASE_URL, timeout=timeout)


def _json_or_text(response: httpx.Response) -> Any:
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {"text": response.text}


def _request(
    method: str,
    path: str,
    *,
    api_key: str,
    client: httpx.Client | None = None,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    operation: str,
) -> tuple[Any, dict[str, Any]]:
    owns_client = client is None
    http_client = _client(client)

    try:
        response = http_client.request(
            method,
            path,
            headers=_headers(api_key),
            params=params,
            json=json,
        )
        status_code = response.status_code
        body = _json_or_text(response)
        audit_event = create_audit_event(
            "render.api.call",
            {
                "provider": "render",
                "operation": operation,
                "method": method,
                "path": path,
                "status_code": status_code,
            },
        )

        if response.is_error:
            return (
                {
                    "error": "render_api_error",
                    "status_code": status_code,
                    "response": body,
                },
                audit_event,
            )

        return body, audit_event
    finally:
        if owns_client:
            http_client.close()


def _missing_api_key_result(operation: str) -> dict[str, Any]:
    return {
        "provider": "render",
        "valid": False,
        "mode": "read-only",
        "errors": ["Render API key is not configured (use credentials_set or set RENDER_API_KEY env var)"],
        "audit_event": create_audit_event(
            "render.api.blocked",
            {
                "provider": "render",
                "operation": operation,
                "reason": "missing_api_key",
            },
        ),
    }


def _first_owner_label(data: Any) -> str | None:
    owner: Any = None

    if isinstance(data, list) and data:
        owner = data[0].get("owner") if isinstance(data[0], Mapping) else data[0]
    elif isinstance(data, Mapping):
        owners = data.get("owners")
        if isinstance(owners, list) and owners:
            owner = owners[0].get("owner") if isinstance(owners[0], Mapping) else owners[0]
        else:
            owner = data.get("owner") or data

    if isinstance(owner, Mapping):
        for key in ("name", "email", "id", "slug"):
            if owner.get(key):
                return str(owner[key])
    if owner:
        return str(owner)
    return None


def _items_from_response(data: Any, key: str) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, Mapping):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _normalize_service(item: Any) -> dict[str, Any]:
    service = item.get("service") if isinstance(item, Mapping) and isinstance(item.get("service"), Mapping) else item
    if not isinstance(service, Mapping):
        return {"raw": service}

    details = service.get("serviceDetails") or service.get("service_details") or {}
    if not isinstance(details, Mapping):
        details = {}

    return {
        "id": service.get("id"),
        "name": service.get("name"),
        "type": service.get("type"),
        "service_type": service.get("serviceType") or service.get("service_type"),
        "repo": service.get("repo"),
        "branch": service.get("branch"),
        "url": details.get("url") or service.get("url"),
    }


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


def _next_cursor(data: Any) -> str | None:
    if not isinstance(data, Mapping):
        return None
    cursor = data.get("nextCursor") or data.get("next_cursor")
    return str(cursor) if cursor else None


def render_validate_credentials(
    *,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Validate Render credentials using the read-only owners endpoint."""
    resolved_api_key = _render_api_key(api_key)
    if not resolved_api_key:
        return _missing_api_key_result("validate_credentials")

    body, audit_event = _request(
        "GET",
        "/owners",
        api_key=resolved_api_key,
        client=client,
        operation="validate_credentials",
    )

    if isinstance(body, Mapping) and body.get("error"):
        return redact(
            {
                "provider": "render",
                "valid": False,
                "owner": None,
                "mode": "read-only",
                "errors": [body],
                "audit_event": audit_event,
            }
        )

    return redact(
        {
            "provider": "render",
            "valid": True,
            "owner": _first_owner_label(body),
            "mode": "read-only",
            "audit_event": audit_event,
        }
    )


def render_list_services(
    *,
    limit: int = 20,
    cursor: str | None = None,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """List Render services for the authenticated account."""
    resolved_api_key = _render_api_key(api_key)
    if not resolved_api_key:
        return _missing_api_key_result("list_services")

    params: dict[str, Any] = {"limit": limit}
    if cursor:
        params["cursor"] = cursor

    body, audit_event = _request(
        "GET",
        "/services",
        api_key=resolved_api_key,
        client=client,
        params=params,
        operation="list_services",
    )

    if isinstance(body, Mapping) and body.get("error"):
        return redact(
            {
                "provider": "render",
                "ok": False,
                "services": [],
                "next_cursor": None,
                "errors": [body],
                "audit_event": audit_event,
            }
        )

    services = [_normalize_service(item) for item in _items_from_response(body, "services")]

    return redact(
        {
            "provider": "render",
            "ok": True,
            "services": services,
            "next_cursor": _next_cursor(body),
            "mode": "read-only",
            "audit_event": audit_event,
        }
    )


def _deploy_plan(service_id: str, environment: str = "staging") -> dict[str, Any]:
    return {
        "provider": "render",
        "environment": environment,
        "mode": "execute",
        "approval_required": True,
        "approval_required_actions": ["trigger Render deployment"],
        "service_id": service_id,
    }


def render_deploy_staging(
    *,
    service_id: str,
    approval: str | bool | None = None,
    clear_cache: bool = False,
    api_key: str | None = None,
    client: httpx.Client | None = None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Trigger a Render staging deploy after the execution gate allows it."""
    deploy_plan = plan or _deploy_plan(service_id, environment="staging")
    gate = evaluate_execution_gate(deploy_plan, approval=approval, mode="execute")
    if not gate["allowed"]:
        return redact(
            {
                "provider": "render",
                "triggered": False,
                "deploy_id": None,
                "gate": gate,
                "audit_event": create_audit_event(
                    "render.deploy.blocked",
                    {
                        "provider": "render",
                        "operation": "deploy_staging",
                        "service_id": service_id,
                        "reasons": gate.get("reasons", []),
                    },
                ),
            }
        )

    resolved_api_key = _render_api_key(api_key)
    if not resolved_api_key:
        result = _missing_api_key_result("deploy_staging")
        result.update({"triggered": False, "deploy_id": None, "gate": gate})
        return redact(result)

    payload = {"clearCache": "clear"} if clear_cache else None
    body, audit_event = _request(
        "POST",
        f"/services/{service_id}/deploys",
        api_key=resolved_api_key,
        client=client,
        json=payload,
        operation="deploy_staging",
    )

    if isinstance(body, Mapping) and body.get("error"):
        return redact(
            {
                "provider": "render",
                "triggered": False,
                "deploy_id": None,
                "gate": gate,
                "errors": [body],
                "audit_event": audit_event,
            }
        )

    deploy = _normalize_deploy(body)
    return redact(
        {
            "provider": "render",
            "triggered": True,
            "deploy_id": deploy.get("id"),
            "status": deploy.get("status"),
            "gate": gate,
            "deploy": deploy,
            "audit_event": audit_event,
        }
    )


def render_get_deploy_status(
    *,
    service_id: str,
    deploy_id: str | None = None,
    timeout_seconds: int = 0,
    poll_interval_seconds: float = 5.0,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Read Render deploy status, optionally polling until completion or timeout."""
    resolved_api_key = _render_api_key(api_key)
    if not resolved_api_key:
        return _missing_api_key_result("get_deploy_status")

    deadline = time.monotonic() + max(timeout_seconds, 0)
    attempts = 0

    while True:
        attempts += 1
        path = f"/services/{service_id}/deploys/{deploy_id}" if deploy_id else f"/services/{service_id}/deploys"
        params = None if deploy_id else {"limit": 1}
        body, audit_event = _request(
            "GET",
            path,
            api_key=resolved_api_key,
            client=client,
            params=params,
            operation="get_deploy_status",
        )

        if isinstance(body, Mapping) and body.get("error"):
            return redact(
                {
                    "provider": "render",
                    "ok": False,
                    "service_id": service_id,
                    "deploy_id": deploy_id,
                    "errors": [body],
                    "audit_event": audit_event,
                }
            )

        deploy = _normalize_deploy(body)
        status = deploy.get("status")
        if not timeout_seconds or status in FINAL_DEPLOY_STATUSES or time.monotonic() >= deadline:
            return redact(
                {
                    "provider": "render",
                    "ok": True,
                    "service_id": service_id,
                    "deploy_id": deploy.get("id") or deploy_id,
                    "status": status,
                    "complete": status in FINAL_DEPLOY_STATUSES,
                    "attempts": attempts,
                    "deploy": deploy,
                    "audit_event": audit_event,
                }
            )

        time.sleep(max(poll_interval_seconds, 0))


def render_healthcheck(
    *,
    url: str,
    expected_status: int = 200,
    timeout_seconds: float = 10.0,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Run an HTTP healthcheck against a Render service URL."""
    if not url.startswith(("http://", "https://")):
        return {
            "provider": "render",
            "healthy": False,
            "status_code": None,
            "errors": ["healthcheck url must start with http:// or https://"],
            "audit_event": create_audit_event(
                "render.healthcheck.blocked",
                {"provider": "render", "reason": "invalid_url"},
            ),
        }

    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds)

    try:
        response = http_client.get(url)
        healthy = response.status_code == expected_status
        return redact(
            {
                "provider": "render",
                "healthy": healthy,
                "status_code": response.status_code,
                "expected_status": expected_status,
                "url": url,
                "audit_event": create_audit_event(
                    "render.healthcheck.completed",
                    {
                        "provider": "render",
                        "url": url,
                        "status_code": response.status_code,
                        "healthy": healthy,
                    },
                ),
            }
        )
    except httpx.HTTPError as exc:
        return redact(
            {
                "provider": "render",
                "healthy": False,
                "status_code": None,
                "errors": [str(exc)],
                "url": url,
                "audit_event": create_audit_event(
                    "render.healthcheck.failed",
                    {"provider": "render", "url": url, "error": str(exc)},
                ),
            }
        )
    finally:
        if owns_client:
            http_client.close()
