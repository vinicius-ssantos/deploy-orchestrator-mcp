from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.planner import generate_deployment_plan
from deploy_orchestrator_mcp.providers import get_provider_capability, list_provider_capabilities
from deploy_orchestrator_mcp.railway_provider import railway_generate_postgres_plan, railway_generate_service_plan
from deploy_orchestrator_mcp.render_provider import render_generate_service_plan
from deploy_orchestrator_mcp.supabase_provider import supabase_generate_project_plan


def main():
    files = [
        "pyproject.toml",
        "README.md",
        "render.yaml",
        "src/deploy_orchestrator_mcp/server.py",
        "supabase/config.toml",
    ]

    analysis = analyze_file_list(files)
    plan = generate_deployment_plan(analysis, environment="staging")
    capabilities = list_provider_capabilities()
    render = get_provider_capability("render")
    railway = get_provider_capability("railway")
    supabase = get_provider_capability("supabase")
    render_plan = render_generate_service_plan(
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        service_name="deploy-orchestrator-mcp",
        environment="staging",
    )
    railway_plan = railway_generate_service_plan(
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        service_name="deploy-orchestrator-mcp",
        environment="staging",
        needs_postgres=True,
    )
    railway_postgres_plan = railway_generate_postgres_plan(
        project_name="deploy-orchestrator-mcp",
        environment="staging",
    )
    supabase_plan = supabase_generate_project_plan(
        project_name="deploy-orchestrator-mcp",
        environment="staging",
        needs_auth=True,
        needs_storage=True,
    )

    assert analysis["runtime"] == "python"
    assert analysis["needs_supabase"] is True
    assert plan["mode"] == "dry-run"
    assert plan["app_provider"]["provider"] == "render"
    assert plan["database_provider"]["provider"] == "supabase"
    assert "render" in capabilities["app_providers"]
    assert "railway" in capabilities["app_providers"]
    assert "supabase" in capabilities["database_providers"]
    assert render["supports_git_deploy"] is True
    assert railway["supports_logs"] is True
    assert supabase["supports_auth"] is True
    assert render_plan["provider"] == "render"
    assert render_plan["mode"] == "dry-run"
    assert render_plan["validation"]["valid"] is True
    assert railway_plan["provider"] == "railway"
    assert railway_plan["mode"] == "dry-run"
    assert railway_plan["needs_postgres"] is True
    assert railway_postgres_plan["database"] == "postgres"
    assert supabase_plan["provider"] == "supabase"
    assert supabase_plan["mode"] == "dry-run"
    assert supabase_plan["validation"]["valid"] is True

    print("smoke test passed")
    print(plan)
    print(render_plan)
    print(railway_plan)
    print(railway_postgres_plan)
    print(supabase_plan)


if __name__ == "__main__":
    main()
