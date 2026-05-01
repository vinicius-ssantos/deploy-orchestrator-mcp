from fastmcp import FastMCP

from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.planner import generate_deployment_plan

mcp = FastMCP("deploy-orchestrator-mcp")


@mcp.tool()
def provider_list():
    """List supported app and database providers."""
    return {
        "app_providers": ["render", "railway", "fly", "koyeb", "coolify"],
        "database_providers": [
            "supabase",
            "railway-postgres",
            "render-postgres",
            "koyeb-database",
            "coolify-postgres",
        ],
        "mode": "dry-run",
    }


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
