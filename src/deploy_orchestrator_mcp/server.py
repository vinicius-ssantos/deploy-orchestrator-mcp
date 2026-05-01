from fastmcp import FastMCP

from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.config import get_settings
from deploy_orchestrator_mcp.planner import generate_deployment_plan
from deploy_orchestrator_mcp.providers import get_provider_capability, list_provider_capabilities

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


if __name__ == "__main__":
    mcp.run(transport="stdio")
