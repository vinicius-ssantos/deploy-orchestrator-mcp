from typing import Any

import httpx

from deploy_orchestrator_mcp.audit import create_audit_event
from deploy_orchestrator_mcp.credentials import get_credential
from deploy_orchestrator_mcp.redaction import redact

VERCEL_API_BASE_URL = "https://api.vercel.com"

_SENSITIVE_TERMS = {
    "token", "secret", "password", "private", "key", "api_key",
    "access_token", "jwt", "service_role", "database_url", "auth",
    "client_secret", "mcp_api_key", "mcp_token",
}

_PUBLIC_PREFIXES = ("VITE_", "NEXT_PUBLIC_", "REACT_APP_", "PUBLIC_")


def _vercel_token(token: str | None = None) -> str | None:
    return token or get_credential("vercel")


def _team_id(team_id: str | None = None) -> str | None:
    return team_id or get_credential("vercel_team_id")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _missing_token_result(operation: str) -> dict[str, Any]:
    return {
        "provider": "vercel",
        "ok": False,
        "configured": False,
        "errors": ["Vercel token is not configured (use credentials_set or set VERCEL_TOKEN env var)"],
        "audit_event": create_audit_event(
            "vercel.api.blocked",
            {"provider": "vercel", "operation": operation, "reason": "missing_token"},
        ),
    }


def check_public_env_vars(env_var_names: list[str]) -> dict[str, Any]:
    """Check a list of env var names for sensitive values exposed via public prefixes."""
    exposed = [
        v for v in env_var_names
        if any(v.startswith(p) for p in _PUBLIC_PREFIXES)
        and any(term in v.lower() for term in _SENSITIVE_TERMS)
    ]
    return {
        "ok": len(exposed) == 0,
        "severity": "blocker" if exposed else "ok",
        "exposed_candidates": exposed,
        "message": (
            "VITE_*/NEXT_PUBLIC_*/REACT_APP_* variables are bundled into client-side JavaScript. "
            "Remove sensitive values before deploying."
            if exposed else "No sensitive public env vars detected."
        ),
    }


def vercel_validate_credentials(
    *,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Validate Vercel credentials using the /v2/user endpoint."""
    resolved_token = _vercel_token(token)
    if not resolved_token:
        return _missing_token_result("validate_credentials")

    owns_client = client is None
    http_client = client or httpx.Client(base_url=VERCEL_API_BASE_URL, timeout=15.0)

    try:
        response = http_client.get("/v2/user", headers=_headers(resolved_token))
        audit_event = create_audit_event(
            "vercel.api.call",
            {"provider": "vercel", "operation": "validate_credentials", "status_code": response.status_code},
        )

        if response.is_error:
            return redact({
                "provider": "vercel",
                "ok": False,
                "configured": True,
                "valid": False,
                "errors": [f"HTTP {response.status_code}"],
                "audit_event": audit_event,
            })

        try:
            body = response.json()
        except ValueError:
            body = {}

        user = body.get("user") or body
        username = user.get("username") or user.get("email") or user.get("name")

        return redact({
            "provider": "vercel",
            "ok": True,
            "configured": True,
            "valid": True,
            "username": username,
            "audit_event": audit_event,
        })
    except httpx.HTTPError as exc:
        return redact({
            "provider": "vercel",
            "ok": False,
            "configured": True,
            "valid": False,
            "errors": [type(exc).__name__],
            "audit_event": create_audit_event(
                "vercel.api.call",
                {"provider": "vercel", "operation": "validate_credentials", "status_code": 0},
            ),
        })
    finally:
        if owns_client:
            http_client.close()


def vercel_project_plan(
    *,
    project_name: str,
    repo: str,
    branch: str,
    framework: str = "vite",
    build_command: str = "npm run build",
    output_dir: str = "dist",
    env_var_names: list[str] | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Dry-run plan for a Vercel frontend deployment. No HTTP calls."""
    configured = _vercel_token(token) is not None
    env_check = check_public_env_vars(env_var_names or [])

    return {
        "provider": "vercel",
        "mode": "dry-run",
        "environment": "preview",
        "project_name": project_name,
        "repo": repo,
        "branch": branch,
        "framework": framework,
        "build_command": build_command,
        "output_dir": output_dir,
        "will_create_or_use_project": True,
        "will_trigger_preview_deployment": True,
        "production": False,
        "credentials_configured": configured,
        "approval_required": True,
        "public_env_check": env_check,
        "risks": [
            "Vercel account quota may apply (Hobby: 100 deployments/day)",
            "Git provider permissions required for gitSource deploy",
            "VITE_* env vars are bundled into client JavaScript — review before deploying",
        ],
        "audit_event": create_audit_event(
            "vercel.deploy.planned",
            {
                "provider": "vercel",
                "operation": "project_plan",
                "project_name": project_name,
                "repo": repo,
                "branch": branch,
                "environment": "preview",
                "env_check_ok": env_check["ok"],
            },
        ),
    }


def vercel_deploy_preview(
    *,
    project_name: str,
    repo: str,
    repo_id: str,
    branch: str,
    framework: str = "vite",
    build_command: str = "npm run build",
    output_dir: str = "dist",
    token: str | None = None,
    team_id: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Trigger a Vercel preview deployment via gitSource. Never targets production."""
    resolved_token = _vercel_token(token)
    if not resolved_token:
        result = _missing_token_result("deploy_preview")
        result["triggered"] = False
        result["environment"] = "preview"
        return result

    resolved_team_id = _team_id(team_id)

    payload: dict[str, Any] = {
        "name": project_name,
        "gitSource": {
            "type": "github",
            "repoId": repo_id,
            "ref": branch,
        },
        "projectSettings": {
            "framework": framework,
            "buildCommand": build_command,
            "outputDirectory": output_dir,
            "installCommand": "npm install",
        },
    }

    params: dict[str, str] = {}
    if resolved_team_id:
        params["teamId"] = resolved_team_id

    owns_client = client is None
    http_client = client or httpx.Client(base_url=VERCEL_API_BASE_URL, timeout=30.0)

    try:
        response = http_client.post(
            "/v13/deployments",
            headers=_headers(resolved_token),
            json=payload,
            params=params or None,
        )
        status_code = response.status_code
        audit_event = create_audit_event(
            "vercel.deploy.triggered",
            {
                "provider": "vercel",
                "operation": "deploy_preview",
                "project_name": project_name,
                "repo": repo,
                "branch": branch,
                "environment": "preview",
                "status_code": status_code,
            },
        )

        if response.is_error:
            try:
                err_body = response.json()
            except ValueError:
                err_body = {"text": response.text[:200]}
            return redact({
                "provider": "vercel",
                "ok": False,
                "triggered": False,
                "environment": "preview",
                "errors": [f"HTTP {status_code}", err_body],
                "audit_event": audit_event,
            })

        try:
            body = response.json()
        except ValueError:
            body = {}

        deployment_id = body.get("id") or body.get("uid")
        url = body.get("url")
        deploy_status = body.get("readyState") or body.get("status") or "INITIALIZING"

        return redact({
            "provider": "vercel",
            "ok": True,
            "triggered": True,
            "environment": "preview",
            "project_name": project_name,
            "deployment_id": deployment_id,
            "url": f"https://{url}" if url and not url.startswith("http") else url,
            "status": deploy_status,
            "target": "preview",
            "audit_event": audit_event,
        })
    except httpx.HTTPError as exc:
        return redact({
            "provider": "vercel",
            "ok": False,
            "triggered": False,
            "environment": "preview",
            "errors": [type(exc).__name__],
            "audit_event": create_audit_event(
                "vercel.deploy.triggered",
                {"provider": "vercel", "operation": "deploy_preview", "status_code": 0, "error": type(exc).__name__},
            ),
        })
    finally:
        if owns_client:
            http_client.close()


def vercel_get_deploy_status(
    *,
    deployment_id: str,
    token: str | None = None,
    team_id: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Read current status of a Vercel deployment."""
    resolved_token = _vercel_token(token)
    if not resolved_token:
        return _missing_token_result("get_deploy_status")

    resolved_team_id = _team_id(team_id)
    params: dict[str, str] = {}
    if resolved_team_id:
        params["teamId"] = resolved_team_id

    owns_client = client is None
    http_client = client or httpx.Client(base_url=VERCEL_API_BASE_URL, timeout=15.0)

    try:
        response = http_client.get(
            f"/v13/deployments/{deployment_id}",
            headers=_headers(resolved_token),
            params=params or None,
        )
        audit_event = create_audit_event(
            "vercel.api.call",
            {
                "provider": "vercel",
                "operation": "get_deploy_status",
                "deployment_id": deployment_id,
                "status_code": response.status_code,
            },
        )

        if response.is_error:
            return redact({
                "provider": "vercel",
                "ok": False,
                "deployment_id": deployment_id,
                "errors": [f"HTTP {response.status_code}"],
                "audit_event": audit_event,
            })

        try:
            body = response.json()
        except ValueError:
            body = {}

        deploy_status = body.get("readyState") or body.get("status")
        url = body.get("url")
        created_at = body.get("createdAt")

        return redact({
            "provider": "vercel",
            "ok": True,
            "deployment_id": deployment_id,
            "status": deploy_status,
            "url": f"https://{url}" if url and not url.startswith("http") else url,
            "created_at": created_at,
            "target": body.get("target") or "preview",
            "audit_event": audit_event,
        })
    except httpx.HTTPError as exc:
        return redact({
            "provider": "vercel",
            "ok": False,
            "deployment_id": deployment_id,
            "errors": [type(exc).__name__],
            "audit_event": create_audit_event(
                "vercel.api.call",
                {"provider": "vercel", "operation": "get_deploy_status", "deployment_id": deployment_id, "status_code": 0},
            ),
        })
    finally:
        if owns_client:
            http_client.close()
