"""Supabase real API integration.

Read-only discovery tools (validate, list orgs, list projects, project status,
connection info, healthcheck). All outputs go through redact() to prevent
service role keys or connection strings from leaking.
"""

import httpx

from deploy_orchestrator_mcp.audit import create_audit_event
from deploy_orchestrator_mcp.credentials import get_credential
from deploy_orchestrator_mcp.execution import evaluate_execution_gate
from deploy_orchestrator_mcp.redaction import redact
from typing import Any

SUPABASE_API_BASE_URL = "https://api.supabase.com/v1"


def _supabase_token(token: str | None = None) -> str | None:
    return token or get_credential("supabase")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _http_client(client: httpx.Client | None = None) -> httpx.Client:
    return client or httpx.Client(base_url=SUPABASE_API_BASE_URL, timeout=30.0)


def _request(
    method: str,
    path: str,
    *,
    token: str,
    client: httpx.Client | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    operation: str,
) -> tuple[Any, dict[str, Any]]:
    owns_client = client is None
    http_client = _http_client(client)
    try:
        response = http_client.request(
            method, path, headers=_headers(token), params=params, json=json_body
        )
        status_code = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = {"text": response.text}

        audit_event = create_audit_event(
            "supabase.api.call",
            {
                "provider": "supabase",
                "operation": operation,
                "method": method,
                "path": path,
                "status_code": status_code,
            },
        )

        if response.is_error:
            return (
                {"error": "supabase_api_error", "status_code": status_code, "response": body},
                audit_event,
            )

        return body, audit_event
    finally:
        if owns_client:
            http_client.close()


def _missing_token_result(operation: str) -> dict[str, Any]:
    return {
        "provider": "supabase",
        "valid": False,
        "errors": [
            "Supabase access token is not configured "
            "(use credentials_set or set SUPABASE_ACCESS_TOKEN env var)"
        ],
        "audit_event": create_audit_event(
            "supabase.api.blocked",
            {"provider": "supabase", "operation": operation, "reason": "missing_token"},
        ),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def supabase_validate_credentials(
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Validate Supabase access token via the /organizations endpoint."""
    resolved = _supabase_token(token)
    if not resolved:
        return _missing_token_result("validate_credentials")

    body, audit_event = _request(
        "GET", "/organizations", token=resolved, client=client,
        operation="validate_credentials",
    )

    if isinstance(body, dict) and body.get("error"):
        return redact({
            "provider": "supabase",
            "valid": False,
            "errors": [body],
            "audit_event": audit_event,
        })

    org_count = len(body) if isinstance(body, list) else 0
    return redact({
        "provider": "supabase",
        "valid": True,
        "organization_count": org_count,
        "audit_event": audit_event,
    })


def supabase_list_organizations(
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """List Supabase organizations accessible to the token."""
    resolved = _supabase_token(token)
    if not resolved:
        return _missing_token_result("list_organizations")

    body, audit_event = _request(
        "GET", "/organizations", token=resolved, client=client,
        operation="list_organizations",
    )

    if isinstance(body, dict) and body.get("error"):
        return redact({
            "provider": "supabase",
            "organizations": [],
            "errors": [body],
            "audit_event": audit_event,
        })

    orgs = [
        {"id": org.get("id"), "name": org.get("name")}
        for org in (body if isinstance(body, list) else [])
    ]
    return redact({
        "provider": "supabase",
        "organizations": orgs,
        "count": len(orgs),
        "audit_event": audit_event,
    })


def supabase_list_projects(
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """List all Supabase projects accessible to the token."""
    resolved = _supabase_token(token)
    if not resolved:
        return _missing_token_result("list_projects")

    body, audit_event = _request(
        "GET", "/projects", token=resolved, client=client,
        operation="list_projects",
    )

    if isinstance(body, dict) and body.get("error"):
        return redact({
            "provider": "supabase",
            "projects": [],
            "errors": [body],
            "audit_event": audit_event,
        })

    projects = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "organization_id": p.get("organization_id"),
            "region": p.get("region"),
            "status": p.get("status"),
        }
        for p in (body if isinstance(body, list) else [])
    ]
    return redact({
        "provider": "supabase",
        "projects": projects,
        "count": len(projects),
        "audit_event": audit_event,
    })


def supabase_get_project_status(
    project_id: str,
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Get the current status of a Supabase project."""
    resolved = _supabase_token(token)
    if not resolved:
        return _missing_token_result("get_project_status")

    body, audit_event = _request(
        "GET", f"/projects/{project_id}", token=resolved, client=client,
        operation="get_project_status",
    )

    if isinstance(body, dict) and body.get("error"):
        return redact({
            "provider": "supabase",
            "project_id": project_id,
            "status": None,
            "errors": [body],
            "audit_event": audit_event,
        })

    return redact({
        "provider": "supabase",
        "project_id": project_id,
        "name": body.get("name"),
        "status": body.get("status"),
        "region": body.get("region"),
        "organization_id": body.get("organization_id"),
        "audit_event": audit_event,
    })


def supabase_get_connection_info(
    project_id: str,
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Return safe/redacted connection metadata for a Supabase project.

    Never returns service role keys, database passwords, or full connection strings.
    Only exposes the project URL and anon key metadata.
    """
    resolved = _supabase_token(token)
    if not resolved:
        return _missing_token_result("get_connection_info")

    body, audit_event = _request(
        "GET", f"/projects/{project_id}/api-keys", token=resolved, client=client,
        operation="get_connection_info",
    )

    if isinstance(body, dict) and body.get("error"):
        return redact({
            "provider": "supabase",
            "project_id": project_id,
            "errors": [body],
            "audit_event": audit_event,
        })

    keys = body if isinstance(body, list) else []
    # Only expose the anon key name/role — never the actual key value
    safe_keys = [
        {"name": k.get("name"), "role": k.get("role")}
        for k in keys
        if k.get("role") in ("anon", "authenticated")
    ]

    project_url = f"https://{project_id}.supabase.co"
    return redact({
        "provider": "supabase",
        "project_id": project_id,
        "project_url": project_url,
        "key_roles": safe_keys,
        "note": "Service role key and database password are never returned by this tool",
        "audit_event": audit_event,
    })


def supabase_healthcheck(
    project_id: str,
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Check reachability of a Supabase project's REST API."""
    resolved = _supabase_token(token)
    if not resolved:
        return _missing_token_result("healthcheck")

    # First get the project to confirm it exists and get its status
    body, audit_event = _request(
        "GET", f"/projects/{project_id}", token=resolved, client=client,
        operation="healthcheck",
    )

    if isinstance(body, dict) and body.get("error"):
        return redact({
            "provider": "supabase",
            "project_id": project_id,
            "healthy": False,
            "errors": [body],
            "audit_event": audit_event,
        })

    status = body.get("status", "UNKNOWN")
    healthy = status in ("ACTIVE_HEALTHY",)

    # Attempt a lightweight HTTP ping to the project REST endpoint
    project_url = f"https://{project_id}.supabase.co/rest/v1/"
    ping_status_code = None
    owns_http = http_client is None
    ping_client = http_client or httpx.Client(timeout=10.0)
    try:
        ping_resp = ping_client.get(project_url)
        ping_status_code = ping_resp.status_code
        # 401 means the endpoint is reachable (just unauthenticated)
        reachable = ping_status_code in (200, 400, 401)
    except httpx.HTTPError:
        reachable = False
    finally:
        if owns_http:
            ping_client.close()

    return redact({
        "provider": "supabase",
        "project_id": project_id,
        "healthy": healthy and reachable,
        "project_status": status,
        "reachable": reachable,
        "ping_status_code": ping_status_code,
        "audit_event": audit_event,
    })


def supabase_create_project(
    project_name: str,
    organization_id: str,
    *,
    region: str = "us-east-1",
    plan: dict[str, Any] | None = None,
    approval: str | bool | None = None,
    ci_gate: dict[str, Any] | None = None,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Create a Supabase project with approval, policy and CI gate validation."""
    deploy_plan = plan or {
        "provider": "supabase",
        "environment": "staging",
        "mode": "execute",
        "approval_required": True,
        "approval_required_actions": ["create Supabase project"],
        "project_name": project_name,
        "organization_id": organization_id,
    }
    gate = evaluate_execution_gate(
        deploy_plan,
        approval=approval,
        mode="execute",
        ci_gate=ci_gate,
    )
    if not gate["allowed"]:
        return redact({
            "provider": "supabase",
            "created": False,
            "project_id": None,
            "project_name": project_name,
            "organization_id": organization_id,
            "gate": gate,
            "errors": gate.get("errors", gate.get("reasons", [])),
            "missing_fields": gate.get("missing_fields", []),
            "audit_event": create_audit_event(
                "supabase.project.blocked",
                {
                    "provider": "supabase",
                    "operation": "create_project",
                    "project_name": project_name,
                    "organization_id": organization_id,
                    "reasons": gate.get("reasons", []),
                    "missing_fields": gate.get("missing_fields", []),
                },
            ),
        })

    resolved = _supabase_token(token)
    if not resolved:
        result = _missing_token_result("create_project")
        result.update({"created": False, "project_id": None, "gate": gate})
        return redact(result)

    body, audit_event = _request(
        "POST",
        "/projects",
        token=resolved,
        client=client,
        json_body={
            "name": project_name,
            "organization_id": organization_id,
            "region": region,
        },
        operation="create_project",
    )
    if isinstance(body, dict) and body.get("error"):
        return redact({
            "provider": "supabase",
            "created": False,
            "project_id": None,
            "project_name": project_name,
            "organization_id": organization_id,
            "region": region,
            "gate": gate,
            "errors": [body],
            "audit_event": audit_event,
        })

    return redact({
        "provider": "supabase",
        "created": True,
        "project_id": (body or {}).get("id"),
        "project_name": (body or {}).get("name") or project_name,
        "organization_id": (body or {}).get("organization_id") or organization_id,
        "region": (body or {}).get("region") or region,
        "status": (body or {}).get("status"),
        "gate": gate,
        "audit_event": audit_event,
    })


def supabase_apply_migration(
    project_id: str,
    migration_name: str,
    sql: str,
    *,
    plan: dict[str, Any] | None = None,
    approval: str | bool | None = None,
    ci_gate: dict[str, Any] | None = None,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Apply a SQL migration through Supabase Management API with execute gate."""
    deploy_plan = plan or {
        "provider": "supabase",
        "environment": "staging",
        "mode": "execute",
        "approval_required": True,
        "approval_required_actions": ["apply database migration"],
        "project_id": project_id,
        "migration_name": migration_name,
    }
    gate = evaluate_execution_gate(
        deploy_plan,
        approval=approval,
        mode="execute",
        ci_gate=ci_gate,
    )
    if not gate["allowed"]:
        return redact({
            "provider": "supabase",
            "applied": False,
            "project_id": project_id,
            "migration_name": migration_name,
            "gate": gate,
            "errors": gate.get("errors", gate.get("reasons", [])),
            "missing_fields": gate.get("missing_fields", []),
            "audit_event": create_audit_event(
                "supabase.migration.blocked",
                {
                    "provider": "supabase",
                    "operation": "apply_migration",
                    "project_id": project_id,
                    "migration_name": migration_name,
                    "reasons": gate.get("reasons", []),
                    "missing_fields": gate.get("missing_fields", []),
                },
            ),
        })

    if not sql or not sql.strip():
        return redact({
            "provider": "supabase",
            "applied": False,
            "project_id": project_id,
            "migration_name": migration_name,
            "errors": ["sql is required"],
            "missing_fields": ["sql"],
            "gate": gate,
            "audit_event": create_audit_event(
                "supabase.migration.blocked",
                {
                    "provider": "supabase",
                    "operation": "apply_migration",
                    "project_id": project_id,
                    "migration_name": migration_name,
                    "reason": "missing_sql",
                },
            ),
        })

    resolved = _supabase_token(token)
    if not resolved:
        result = _missing_token_result("apply_migration")
        result.update({"applied": False, "project_id": project_id, "gate": gate})
        return redact(result)

    body, audit_event = _request(
        "POST",
        f"/projects/{project_id}/database/query",
        token=resolved,
        client=client,
        json_body={"query": sql},
        operation="apply_migration",
    )
    if isinstance(body, dict) and body.get("error"):
        return redact({
            "provider": "supabase",
            "applied": False,
            "project_id": project_id,
            "migration_name": migration_name,
            "gate": gate,
            "errors": [body],
            "audit_event": audit_event,
        })

    return redact({
        "provider": "supabase",
        "applied": True,
        "project_id": project_id,
        "migration_name": migration_name,
        "result": body,
        "gate": gate,
        "audit_event": audit_event,
    })
