from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.planner import generate_deployment_plan


def main():
    files = [
        "pyproject.toml",
        "README.md",
        "render.yaml",
        "src/deploy_orchestrator_mcp/server.py",
    ]

    analysis = analyze_file_list(files)
    plan = generate_deployment_plan(analysis, environment="staging")

    assert analysis["runtime"] == "python"
    assert plan["mode"] == "dry-run"
    assert plan["app_provider"]["provider"] == "render"

    print("smoke test passed")
    print(plan)


if __name__ == "__main__":
    main()
