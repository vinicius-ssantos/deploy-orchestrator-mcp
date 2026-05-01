from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.planner import generate_deployment_plan
from deploy_orchestrator_mcp.providers import get_provider_capability, list_provider_capabilities


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

    assert analysis["runtime"] == "python"
    assert plan["mode"] == "dry-run"
    assert plan["app_provider"]["provider"] == "render"
    assert "render" in capabilities["app_providers"]
    assert render["supports_git_deploy"] is True

    print("smoke test passed")
    print(plan)


if __name__ == "__main__":
    main()
