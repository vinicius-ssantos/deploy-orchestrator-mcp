import hashlib
import os
import time

from fastmcp import FastMCP

_START_TIME = time.time()

from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.audit import audit_log_list as _audit_log_list, audit_log_status as _audit_log_status
from deploy_orchestrator_mcp.auth import auth_status, validate_bearer_token
from deploy_orchestrator_mcp.config import get_settings
from deploy_orchestrator_mcp.coolify_provider import (
    coolify_generate_app_plan,
    coolify_generate_database_plan,
    coolify_validate_request,
)
from deploy_orchestrator_mcp.credentials import (
    clear_credential,
    credential_status,
    get_credential,
    known_providers,
    set_credential,
)
from deploy_orchestrator_mcp.fly_provider import fly_generate_app_plan, fly_validate_request
from deploy_orchestrator_mcp.koyeb_provider import koyeb_generate_service_plan, koyeb_validate_request
from deploy_orchestrator_mcp.migrations import run_staging_migration as migrations_run_staging_migration
from deploy_orchestrator_mcp.planner import generate_deployment_plan
from deploy_orchestrator_mcp.policy import evaluate_policy, parse_repo_policy
from deploy_orchestrator_mcp.providers import get_provider_capability, list_provider_capabilities
from deploy_orchestrator_mcp.railway_api import (
    railway_deploy as railway_api_deploy,
    railway_get_deploy_status as railway_api_get_deploy_status,
    railway_get_postgres_status as railway_api_get_postgres_status,
    railway_get_project as railway_api_get_project,
    railway_healthcheck as railway_api_healthcheck,
    railway_list_deployments as railway_api_list_deployments,
    railway_list_projects as railway_api_list_projects,
    railway_provision_postgres as railway_api_provision_postgres,
    railway_validate_credentials as railway_api_validate_credentials,
)
from deploy_orchestrator_mcp.railway_provider import (
    railway_generate_postgres_plan,
    railway_generate_service_plan,
    railway_validate_request,
)
from deploy_orchestrator_mcp.render_api import (
    render_deploy_staging as render_api_deploy_staging,
    render_get_build_logs as render_api_get_build_logs,
    render_get_deploy_status as render_api_get_deploy_status,
    render_get_runtime_logs as render_api_get_runtime_logs,
    render_healthcheck as render_api_healthcheck,
    render_list_services as render_api_list_services,
    render_rollback_staging as render_api_rollback_staging,
    render_validate_credentials as render_api_validate_credentials,
)
from deploy_orchestrator_mcp.render_provider import (
    render_generate_service_plan,
    render_validate_request,
)
from deploy_orchestrator_mcp.render_workflows import (
    render_cancel_task_run as render_workflows_cancel_task_run,
    render_get_task_run as render_workflows_get_task_run,
    render_list_task_runs as render_workflows_list_task_runs,
    render_run_task as render_workflows_run_task,
)
from deploy_orchestrator_mcp.supabase_api import (
    supabase_get_connection_info as supabase_api_get_connection_info,
    supabase_get_project_status as supabase_api_get_project_status,
    supabase_healthcheck as supabase_api_healthcheck,
    supabase_list_organizations as supabase_api_list_organizations,
    supabase_list_projects as supabase_api_list_projects,
    supabase_validate_credentials as supabase_api_validate_credentials,
)
from deploy_orchestrator_mcp.supabase_provider import (
    supabase_generate_project_plan,
    supabase_validate_request,
)

mcp = FastMCP("deploy-orchestrator-mcp")


# ---------------------------------------------------------------------------
# Auth & server info
# ---------------------------------------------------------------------------


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(_request):
    """Public health endpoint for platform probes."""
    import importlib.metadata

    from starlette.responses import JSONResponse

    try:
        version = importlib.metadata.version("deploy-orchestrator-mcp")
    except importlib.metadata.PackageNotFoundError:
        version = "unknown"

    tool_names = sorted(t.name for t in await mcp.list_tools())
    tool_schema_version = hashlib.sha256(" ".join(tool_names).encode()).hexdigest()[:8]

    commit_sha = (
        os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("GIT_COMMIT")
        or "unknown"
    )

    return JSONResponse({
        "ok": True,
        "service": "deploy-orchestrator-mcp",
        "version": version,
        "tool_schema_version": tool_schema_version,
        "commit_sha": commit_sha,
        "uptime_seconds": int(time.time() - _START_TIME),
    })


@mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET"])
async def oauth_discovery(request):
    """RFC 8414 authorization server metadata — consumed by ChatGPT connector."""
    from starlette.responses import JSONResponse

    from deploy_orchestrator_mcp.oauth import discovery_document, is_oauth_enabled

    if not is_oauth_enabled():
        return JSONResponse({"error": "OAuth is not configured"}, status_code=404)

    base_url = str(request.base_url).rstrip("/")
    return JSONResponse(discovery_document(base_url))


@mcp.custom_route("/oauth/authorize", methods=["GET"])
async def oauth_authorize(request):
    """OAuth 2.0 authorization endpoint — redirects back with auth code."""
    from urllib.parse import urlencode, urlparse

    from starlette.responses import JSONResponse, RedirectResponse

    from deploy_orchestrator_mcp.oauth import OAuthError, authorize, is_oauth_enabled

    if not is_oauth_enabled():
        return JSONResponse({"error": "OAuth is not configured"}, status_code=404)

    params = request.query_params
    client_id = params.get("client_id", "")
    redirect_uri = params.get("redirect_uri", "")
    response_type = params.get("response_type", "code")
    scope = params.get("scope", "mcp")
    state = params.get("state")
    code_challenge = params.get("code_challenge")
    code_challenge_method = params.get("code_challenge_method")

    try:
        result = authorize(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type=response_type,
            scope=scope,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
    except OAuthError as exc:
        return JSONResponse({"error": exc.error, "error_description": exc.description}, status_code=exc.status)

    # Basic redirect_uri structure check before redirecting.
    parsed = urlparse(redirect_uri)
    if not parsed.scheme or not parsed.netloc:
        return JSONResponse({"error": "invalid_request", "error_description": "Malformed redirect_uri"}, status_code=400)

    qs = urlencode(result)
    return RedirectResponse(url=f"{redirect_uri}?{qs}", status_code=302)


@mcp.custom_route("/oauth/token", methods=["POST"])
async def oauth_token(request):
    """OAuth 2.0 token endpoint — exchanges auth code for access token."""
    from starlette.responses import JSONResponse

    from deploy_orchestrator_mcp.oauth import OAuthError, exchange_code, is_oauth_enabled

    if not is_oauth_enabled():
        return JSONResponse({"error": "OAuth is not configured"}, status_code=404)

    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        body = await request.form()
        data = dict(body)
    else:
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_request", "error_description": "Unreadable request body"}, status_code=400)

    try:
        token_response = exchange_code(
            grant_type=data.get("grant_type", ""),
            code=data.get("code", ""),
            client_id=data.get("client_id", ""),
            client_secret=data.get("client_secret", ""),
            redirect_uri=data.get("redirect_uri", ""),
            code_verifier=data.get("code_verifier"),
        )
    except OAuthError as exc:
        return JSONResponse({"error": exc.error, "error_description": exc.description}, status_code=exc.status)

    return JSONResponse(token_response)


@mcp.tool()
def server_auth_status():
    """Return current server authentication configuration (no secrets exposed)."""
    return auth_status()


# ---------------------------------------------------------------------------
# Credential management
# ---------------------------------------------------------------------------


@mcp.tool()
def credentials_status():
    """List which providers have credentials configured (values are never returned)."""
    return {
        "providers": credential_status(),
        "known_providers": known_providers(),
    }


@mcp.tool()
def credentials_set(provider: str, token: str):
    """Set or update a provider credential at runtime.

    Supported providers: render, railway, fly, koyeb, coolify, supabase.
    Extra keys: coolify_base_url, supabase_org_id.
    """
    try:
        set_credential(provider, token)
        return {"ok": True, "provider": provider, "message": f"Credential for '{provider}' updated."}
    except ValueError as exc:
        return {"ok": False, "provider": provider, "error": str(exc)}


@mcp.tool()
def credentials_clear(provider: str):
    """Remove a provider credential from the runtime store."""
    clear_credential(provider)
    return {"ok": True, "provider": provider, "message": f"Credential for '{provider}' cleared."}


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@mcp.tool()
def audit_log_status():
    """Return the status of the persistent audit log backend."""
    return _audit_log_status()


@mcp.tool()
def audit_log_list(limit: int = 50):
    """List recent audit events from the persistent log. Returns empty list if MCP_AUDIT_LOG_PATH is not set."""
    return _audit_log_list(limit=limit)


# ---------------------------------------------------------------------------
# Safety & policy
# ---------------------------------------------------------------------------


@mcp.tool()
def safety_settings():
    """Return current safety settings without exposing secrets."""
    return get_settings()


@mcp.tool()
def policy_evaluate(
    environment: str,
    app_provider: str,
    database_provider: str | None = None,
    policy: dict | None = None,
):
    """Evaluate repository deployment policy for a planned deployment."""
    return evaluate_policy(
        policy=policy,
        environment=environment,
        app_provider=app_provider,
        database_provider=database_provider,
    )


@mcp.tool()
def policy_load(yaml_content: str):
    """Parse the raw YAML content of .deploy-orchestrator/policy.yml.

    Pass the file content as a string. Returns the parsed policy dict merged
    with default values. Use the returned dict as the `policy` argument to
    `policy_evaluate` or `deployment_plan`.
    """
    try:
        parsed = parse_repo_policy(yaml_content)
        return {"ok": True, "policy": parsed}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


@mcp.tool()
def provider_list():
    """List supported app and database providers."""
    capabilities = list_provider_capabilities()
    return {
        "app_providers": list(capabilities["app_providers"].keys()),
        "database_providers": list(capabilities["database_providers"].keys()),
        "mode": "dry-run",
    }


@mcp.tool()
def provider_capabilities(provider: str | None = None):
    """Return provider capabilities for one provider or all providers."""
    if provider:
        return {
            "provider": provider,
            "capabilities": get_provider_capability(provider),
            "mode": "dry-run",
        }
    return list_provider_capabilities()


# ---------------------------------------------------------------------------
# Repo & plan
# ---------------------------------------------------------------------------


@mcp.tool()
def repo_analyze(files: list[str]):
    """Analyze repository file paths and detect runtime/deployment needs."""
    return analyze_file_list(files)


@mcp.tool()
def deploy_generate_plan(
    files: list[str],
    environment: str = "staging",
    policy: dict | None = None,
):
    """Generate a dry-run deployment plan from repository file paths."""
    analysis = analyze_file_list(files)
    return generate_deployment_plan(analysis, environment=environment, policy=policy)


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


@mcp.tool()
def render_validate(environment: str = "staging"):
    """Validate whether a Render dry-run request is allowed."""
    return render_validate_request(environment=environment)


@mcp.tool()
def render_service_plan(repo_full_name: str, service_name: str, environment: str = "staging"):
    """Generate a dry-run Render service plan without executing provider writes."""
    return render_generate_service_plan(
        repo_full_name=repo_full_name,
        service_name=service_name,
        environment=environment,
    )


@mcp.tool()
def render_validate_credentials():
    """Validate Render API credentials using a read-only API call."""
    return render_api_validate_credentials()


@mcp.tool()
def render_list_services(limit: int = 20, cursor: str | None = None):
    """List Render services for the authenticated account."""
    return render_api_list_services(limit=limit, cursor=cursor)


@mcp.tool()
def render_deploy_staging(
    service_id: str,
    approval: str | bool | None = None,
    clear_cache: bool = False,
):
    """Trigger a Render staging deploy after approval gate validation."""
    return render_api_deploy_staging(
        service_id=service_id,
        approval=approval,
        clear_cache=clear_cache,
    )


@mcp.tool()
def render_get_deploy_status(
    service_id: str,
    deploy_id: str | None = None,
    timeout_seconds: int = 0,
    poll_interval_seconds: float = 5.0,
):
    """Read or poll Render deploy status."""
    return render_api_get_deploy_status(
        service_id=service_id,
        deploy_id=deploy_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )


@mcp.tool()
def render_healthcheck(url: str, expected_status: int = 200, timeout_seconds: float = 10.0):
    """Run an HTTP healthcheck against a Render service URL."""
    return render_api_healthcheck(
        url=url,
        expected_status=expected_status,
        timeout_seconds=timeout_seconds,
    )


@mcp.tool()
def render_get_build_logs(deploy_id: str, tail: int = 100):
    """Fetch build logs for a Render deploy. Use after a failed deploy to diagnose the cause."""
    return render_api_get_build_logs(deploy_id=deploy_id, tail=tail)


@mcp.tool()
def render_get_runtime_logs(service_id: str, tail: int = 100):
    """Fetch recent runtime logs for a Render service."""
    return render_api_get_runtime_logs(service_id=service_id, tail=tail)


@mcp.tool()
def render_rollback_staging(
    service_id: str,
    target_deploy_id: str,
    approval: str,
    confirm: str,
):
    """Revert a staging service to a previous deploy.

    Requires approval='APPROVED' and confirm='CONFIRM_DESTRUCTIVE_OPERATION'.
    After rollback, poll render_get_deploy_status until 'live', then run render_healthcheck.
    """
    return render_api_rollback_staging(
        service_id=service_id,
        target_deploy_id=target_deploy_id,
        approval=approval,
        confirm=confirm,
    )


# ---------------------------------------------------------------------------
# Render Workflows
# ---------------------------------------------------------------------------


@mcp.tool()
def render_run_task(
    task_slug: str,
    input_data: dict | list | None = None,
    wait: bool = True,
    environment: str = "staging",
    approval: str | None = None,
):
    """Trigger a Render Workflow task (e.g. migrations, smoke tests).

    task_slug format: "workflow-slug/task-name"
    Production environments require approval='APPROVED'.
    Set wait=False to start the task and return immediately with the task_run_id.
    """
    return render_workflows_run_task(
        task_slug=task_slug,
        input_data=input_data,
        wait=wait,
        environment=environment,
        approval=approval,
    )


@mcp.tool()
def render_task_status(task_run_id: str):
    """Poll the current status and output of a Render Workflow task run."""
    return render_workflows_get_task_run(task_run_id=task_run_id)


@mcp.tool()
def run_staging_migration(
    task_slug: str,
    ci_gate: dict,
    approval: str | None = None,
    environment: str = "staging",
    app_provider: str = "render",
    database_provider: str | None = "supabase",
    policy: dict | None = None,
    input_data: dict | list | None = None,
    wait: bool = True,
):
    """Run a staging-first migration task with approval, policy, CI and audit gates."""
    return migrations_run_staging_migration(
        task_slug=task_slug,
        ci_gate=ci_gate,
        approval=approval,
        environment=environment,
        app_provider=app_provider,
        database_provider=database_provider,
        policy=policy,
        input_data=input_data,
        wait=wait,
    )


@mcp.tool()
def render_list_task_runs(limit: int = 20):
    """List recent Render Workflow task runs across all workflows."""
    return render_workflows_list_task_runs(limit=limit)


@mcp.tool()
def render_cancel_task(task_run_id: str, confirm: str = ""):
    """Cancel an in-progress Render Workflow task run.

    Requires confirm='CONFIRM_DESTRUCTIVE_OPERATION'.
    """
    return render_workflows_cancel_task_run(task_run_id=task_run_id, confirm=confirm)


# ---------------------------------------------------------------------------
# Railway
# ---------------------------------------------------------------------------


@mcp.tool()
def railway_validate(environment: str = "staging"):
    """Validate whether a Railway dry-run request is allowed."""
    return railway_validate_request(environment=environment)


@mcp.tool()
def railway_service_plan(
    repo_full_name: str,
    service_name: str,
    environment: str = "staging",
    needs_postgres: bool = False,
):
    """Generate a dry-run Railway service plan without executing provider writes."""
    return railway_generate_service_plan(
        repo_full_name=repo_full_name,
        service_name=service_name,
        environment=environment,
        needs_postgres=needs_postgres,
    )


@mcp.tool()
def railway_validate_credentials():
    """Validate Railway API token using a read-only query."""
    return railway_api_validate_credentials()


@mcp.tool()
def railway_list_projects():
    """List all Railway projects for the authenticated account."""
    return railway_api_list_projects()


@mcp.tool()
def railway_get_project(project_id: str):
    """Get a Railway project with its services and environments."""
    return railway_api_get_project(project_id)


@mcp.tool()
def railway_list_deployments(service_id: str, environment_id: str):
    """List recent deployments for a Railway service."""
    return railway_api_list_deployments(service_id, environment_id)


@mcp.tool()
def railway_deploy_service(
    service_id: str,
    environment_id: str,
    approval: str | bool | None = None,
):
    """Trigger a Railway deployment after approval gate validation."""
    return railway_api_deploy(service_id, environment_id, approval=approval)


@mcp.tool()
def railway_get_deploy_status(
    deployment_id: str,
    timeout_seconds: int = 0,
    poll_interval_seconds: float = 5.0,
):
    """Read or poll Railway deployment status until completion or timeout."""
    return railway_api_get_deploy_status(
        deployment_id,
        timeout_seconds=timeout_seconds,
        poll_interval_seconds=poll_interval_seconds,
    )


@mcp.tool()
def railway_healthcheck(url: str, expected_status: int = 200, timeout_seconds: float = 10.0):
    """Run an HTTP healthcheck against a Railway service URL."""
    return railway_api_healthcheck(url, expected_status=expected_status, timeout_seconds=timeout_seconds)


@mcp.tool()
def railway_provision_postgres(
    project_id: str,
    environment_id: str,
    name: str = "postgres",
    approval: str | bool | None = None,
):
    """Provision a Railway PostgreSQL database with approval gate (requires approval='APPROVED')."""
    return railway_api_provision_postgres(
        project_id,
        environment_id,
        name=name,
        approval=approval,
    )


@mcp.tool()
def railway_get_postgres_status(project_id: str, environment_id: str, service_id: str):
    """Get Railway Postgres connection status — secret values are never returned."""
    return railway_api_get_postgres_status(project_id, environment_id, service_id)


@mcp.tool()
def railway_postgres_plan(project_name: str, environment: str = "staging"):
    """Generate a dry-run Railway Postgres plan without executing provider writes."""
    return railway_generate_postgres_plan(project_name=project_name, environment=environment)


# ---------------------------------------------------------------------------
# Fly
# ---------------------------------------------------------------------------


@mcp.tool()
def fly_validate(environment: str = "staging"):
    """Validate whether a Fly dry-run request is allowed."""
    return fly_validate_request(environment=environment)


@mcp.tool()
def fly_app_plan(
    repo_full_name: str,
    app_name: str,
    environment: str = "staging",
    needs_volume: bool = False,
):
    """Generate a dry-run Fly app plan without executing provider writes."""
    return fly_generate_app_plan(
        repo_full_name=repo_full_name,
        app_name=app_name,
        environment=environment,
        needs_volume=needs_volume,
    )


# ---------------------------------------------------------------------------
# Koyeb
# ---------------------------------------------------------------------------


@mcp.tool()
def koyeb_validate(environment: str = "staging"):
    """Validate whether a Koyeb dry-run request is allowed."""
    return koyeb_validate_request(environment=environment)


@mcp.tool()
def koyeb_service_plan(
    repo_full_name: str,
    app_name: str,
    service_name: str,
    environment: str = "staging",
    service_type: str = "web",
    source: str = "github",
):
    """Generate a dry-run Koyeb service plan without executing provider writes."""
    return koyeb_generate_service_plan(
        repo_full_name=repo_full_name,
        app_name=app_name,
        service_name=service_name,
        environment=environment,
        service_type=service_type,
        source=source,
    )


# ---------------------------------------------------------------------------
# Coolify
# ---------------------------------------------------------------------------


@mcp.tool()
def coolify_validate(environment: str = "staging"):
    """Validate whether a Coolify dry-run request is allowed."""
    return coolify_validate_request(environment=environment)


@mcp.tool()
def coolify_app_plan(
    repo_full_name: str,
    project_name: str,
    app_name: str,
    environment: str = "staging",
    deployment_method: str = "github-app",
    needs_database: bool = False,
    enable_preview: bool = False,
):
    """Generate a dry-run Coolify application plan without executing provider writes."""
    return coolify_generate_app_plan(
        repo_full_name=repo_full_name,
        project_name=project_name,
        app_name=app_name,
        environment=environment,
        deployment_method=deployment_method,
        needs_database=needs_database,
        enable_preview=enable_preview,
    )


@mcp.tool()
def coolify_database_plan(
    project_name: str,
    database_name: str,
    engine: str = "postgres",
    environment: str = "staging",
):
    """Generate a dry-run Coolify database plan without executing provider writes."""
    return coolify_generate_database_plan(
        project_name=project_name,
        database_name=database_name,
        engine=engine,
        environment=environment,
    )


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------


@mcp.tool()
def supabase_validate(environment: str = "staging"):
    """Validate whether a Supabase dry-run request is allowed."""
    return supabase_validate_request(environment=environment)


@mcp.tool()
def supabase_project_plan(
    project_name: str,
    environment: str = "staging",
    needs_auth: bool = False,
    needs_storage: bool = False,
):
    """Generate a dry-run Supabase project plan without executing provider writes."""
    return supabase_generate_project_plan(
        project_name=project_name,
        environment=environment,
        needs_auth=needs_auth,
        needs_storage=needs_storage,
    )


@mcp.tool()
def supabase_validate_credentials():
    """Validate Supabase access token without exposing it."""
    return supabase_api_validate_credentials()


@mcp.tool()
def supabase_list_organizations():
    """List Supabase organizations accessible to the configured token."""
    return supabase_api_list_organizations()


@mcp.tool()
def supabase_list_projects():
    """List all Supabase projects accessible to the configured token."""
    return supabase_api_list_projects()


@mcp.tool()
def supabase_get_project_status(project_id: str):
    """Get the current status of a Supabase project."""
    return supabase_api_get_project_status(project_id)


@mcp.tool()
def supabase_get_connection_info(project_id: str):
    """Return safe redacted connection metadata for a Supabase project. Never returns service role key or DB password."""
    return supabase_api_get_connection_info(project_id)


@mcp.tool()
def supabase_healthcheck(project_id: str):
    """Check reachability of a Supabase project REST API."""
    return supabase_api_healthcheck(project_id)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def _make_asgi_app():
    """Wrap the FastMCP HTTP app with a simple Bearer API key middleware."""
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    _PUBLIC_PATHS = {
        "/healthz",
        "/.well-known/oauth-authorization-server",
        "/oauth/authorize",
        "/oauth/token",
    }

    class _BearerAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            from deploy_orchestrator_mcp.auth import is_auth_enabled, validate_any_token

            if request.url.path in _PUBLIC_PATHS:
                return await call_next(request)

            if not is_auth_enabled():
                return await call_next(request)

            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return JSONResponse(
                    {"error": "unauthorized", "detail": "Missing or invalid Authorization header"},
                    status_code=401,
                )
            token = auth_header[len("Bearer "):]
            if not validate_any_token(token):
                return JSONResponse(
                    {"error": "unauthorized", "detail": "Invalid token"},
                    status_code=401,
                )
            return await call_next(request)

    app = mcp.http_app(path="/mcp")
    app.add_middleware(_BearerAuthMiddleware)
    return app


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        import uvicorn
        port = int(os.getenv("PORT", "8000"))
        uvicorn.run(_make_asgi_app(), host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
