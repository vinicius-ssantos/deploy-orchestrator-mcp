from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.planner import generate_deployment_plan


def test_python_project_prefers_render():
    analysis = analyze_file_list(["pyproject.toml", "README.md"])
    plan = generate_deployment_plan(analysis)

    assert analysis["runtime"] == "python"
    assert plan["app_provider"]["provider"] == "render"
    assert plan["provider_plan"]["provider"] == "render"
    assert plan["mode"] == "dry-run"


def test_dockerfile_prefers_fly():
    analysis = analyze_file_list(["Dockerfile", "package.json"])
    plan = generate_deployment_plan(analysis)

    assert analysis["has_dockerfile"] is True
    assert plan["app_provider"]["provider"] == "fly"
    assert plan["provider_plan"]["provider"] == "fly"
    assert plan["provider_plan"]["mode"] == "dry-run"


def test_supabase_project_prefers_supabase_database():
    analysis = analyze_file_list(["package.json", "supabase/config.toml"])
    plan = generate_deployment_plan(analysis)

    assert analysis["needs_supabase"] is True
    assert plan["database_provider"]["provider"] == "supabase"
    assert plan["database_plan"]["provider"] == "supabase"
    assert plan["database_plan"]["mode"] == "dry-run"
