from fastmcp import FastMCP

from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.config import get_settings
from deploy_orchestrator_mcp.coolify_provider import (
    coolify_generate_app_plan,
    coolify_generate_database_plan,
    coolify_validate_request,
)
from deploy_orchestrator_mcp.fly_provider import fly_generate_app_plan, fly_validate_request
from deploy_orchestrator_mcp.koyeb_provider import koyeb_generate_service_plan, koyeb_validate_request
from deploy_orchestrator_mcp.planner import generate_deployment_plan
from deploy_orchestrator_mcp.policy import evaluate_policy
from deploy_orchestrator_mcp.providers import get_provider_capability, list_provider_capabilities
from deploy_orchestrator_mcp.railway_provider import (
    railway_generate_postgres_plan,
    railway_generate_service_plan,
    railway_validate_request,
)
from deploy_orchestrator_mcp.render_api import (
    render_deploy_staging as render_api_deploy_staging,
    render_get_deploy_status as render_api_get_deploy_status,
    render_healthcheck as render_api_healthcheck,
    render_list_services as render_api_list_services,
    render_validate_credentials as render_api_validate_credentials,
)
from deploy_orchestrator_mcp.render_provider import (
    render_generate_service_plan,
    render_validate_request,
)
from deploy_orchestrator_mcp.supabase_provider import (
    supabase_generate_project_plan,
    supabase_validate_request,
)

mcp = FastMCP("deploy-orchestrator-mcp")


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
def railway_postgres_plan(project_name: str, environment: str = "staging"):
    """Generate a dry-run Railway Postgres plan without executing provider writes."""
    return railway_generate_postgres_plan(project_name=project_name, environment=environment)


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


if __name__ == "__main__":
    mcp.run(transport="stdio")
