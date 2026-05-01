from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.planner import generate_deployment_plan
from deploy_orchestrator_mcp.providers import get_provider_capability, list_provider_capabilities
from deploy_orchestrator_mcp.render_provider import render_generate_service_plan


def main():
    files = [
        "pyproject.toml",
        "README.md",
        "render.yaml",
        "src/deploy_orchestrator_mcp/server.py",
    ]

    analysis = analyze_file_list(files)
    plan = generate_deployment_plan(analysis, environment="staging")
    capabilities = list_provider_capabilities()
    render = get_provider_capability("render")
    render_plan = render_generate_service_plan(
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        service_name="deploy-orchestrator-mcp",
        environment="staging",
    )

    assert analysis["runtime"] == "python"
    assert plan["mode"] == "dry-run"
    assert plan["app_provider"]["provider"] == "render"
    assert "render" in capabilities["app_providers"]
    assert render["supports_git_deploy"] is True
    assert render_plan["provider"] == "render"
    assert render_plan["mode"] == "dry-run"
    assert render_plan["validation"]["valid"] is True

    print("smoke test passed")
    print(plan)
    print(render_plan)


if __name__ == "__main__":
    main()
