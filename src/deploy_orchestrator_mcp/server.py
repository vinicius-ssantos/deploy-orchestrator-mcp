from fastmcp import FastMCP

from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.config import get_settings
from deploy_orchestrator_mcp.fly_provider import fly_generate_app_plan, fly_validate_request
from deploy_orchestrator_mcp.planner import generate_deployment_plan
from deploy_orchestrator_mcp.providers import get_provider_capability, list_provider_capabilities
from deploy_orchestrator_mcp.railway_provider import (
    railway_generate_postgres_plan,
    railway_generate_service_plan,
    railway_validate_request,
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
def deploy_generate_plan(files: list[str], environment: str = "staging"):
    """Generate a dry-run deployment plan from repository file paths."""
    analysis = analyze_file_list(files)
    return generate_deployment_plan(analysis, environment=environment)


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
