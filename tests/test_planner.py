from deploy_orchestrator_mcp.planner import generate_deployment_plan
from deploy_orchestrator_mcp.stack_detector import detect_stack


def test_python_project_prefers_render():
    analysis = detect_stack(["pyproject.toml", "README.md"])
    plan = generate_deployment_plan(analysis)

    assert analysis["runtime"] == "python"
    assert plan["app_provider"]["provider"] == "render"
    assert plan["provider_plan"]["provider"] == "render"
    assert plan["policy_result"]["valid"] is True
    assert plan["approval_required"] is True
    assert "create service" in plan["approval_required_actions"]
    assert "trigger deployment" in plan["approval_required_actions"]
    assert plan["mode"] == "dry-run"


def test_dockerfile_prefers_fly():
    analysis = detect_stack(["Dockerfile", "package.json"])
    plan = generate_deployment_plan(analysis)

    assert analysis["has_dockerfile"] is True
    assert plan["app_provider"]["provider"] == "fly"
    assert plan["provider_plan"]["provider"] == "fly"
    assert plan["provider_plan"]["mode"] == "dry-run"
    assert plan["policy_result"]["valid"] is True


def test_node_project_prefers_railway_without_database():
    analysis = detect_stack(["package.json", "index.js"])
    plan = generate_deployment_plan(analysis)

    assert analysis["runtime"] == "node"
    assert plan["app_provider"]["provider"] == "railway"
    assert plan["provider_plan"]["provider"] == "railway"
    assert plan["database_provider"] is None
    assert plan["database_plan"] is None


def test_java_project_prefers_railway_without_database():
    analysis = detect_stack(["pom.xml", "src/Main.java"])
    plan = generate_deployment_plan(analysis)

    assert analysis["runtime"] == "java"
    assert plan["app_provider"]["provider"] == "railway"
    assert plan["provider_plan"]["provider"] == "railway"
    assert plan["database_provider"] is None
    assert plan["database_plan"] is None


def test_supabase_project_prefers_supabase_database():
    analysis = detect_stack(["package.json", "supabase/config.toml"])
    plan = generate_deployment_plan(analysis)

    assert analysis["needs_supabase"] is True
    assert plan["database_provider"]["provider"] == "supabase"
    assert plan["database_plan"]["provider"] == "supabase"
    assert plan["database_plan"]["mode"] == "dry-run"
    assert plan["policy_result"]["valid"] is True
    assert plan["approval_required"] is True
    assert "create database" in plan["approval_required_actions"]


def test_policy_failure_is_reported_in_plan():
    analysis = detect_stack(["Dockerfile", "package.json"])
    policy = {
        "allowed_environments": ["staging"],
        "allowed_app_providers": ["render"],
        "allowed_database_providers": ["supabase"],
        "production": {"allowed": False, "requires_approval": True},
    }

    plan = generate_deployment_plan(analysis, environment="staging", policy=policy)

    assert plan["app_provider"]["provider"] == "fly"
    assert plan["policy_result"]["valid"] is False
    assert plan["approval_required"] is True
    assert "create service" in plan["approval_required_actions"]
    assert "production deployment" not in plan["approval_required_actions"]
    assert plan["policy_result"]["errors"]
    assert "Repository policy validation failed" in plan["risks"]


def test_valid_policy_can_still_require_approval():
    analysis = detect_stack(["pyproject.toml", "README.md"])
    policy = {
        "allowed_environments": ["staging"],
        "allowed_app_providers": ["render"],
        "allowed_database_providers": ["supabase"],
        "production": {"allowed": False, "requires_approval": True},
    }

    plan = generate_deployment_plan(analysis, environment="staging", policy=policy)

    assert plan["policy_result"]["valid"] is True
    assert plan["approval_required"] is True
    assert plan["approval_required_actions"]
    assert "Repository policy validation failed" not in plan["risks"]


def test_production_policy_failure_is_reported_in_plan():
    analysis = detect_stack(["pyproject.toml", "README.md"])

    plan = generate_deployment_plan(analysis, environment="production")

    assert plan["policy_result"]["valid"] is False
    assert plan["approval_required"] is True
    assert "create service" in plan["approval_required_actions"]
    assert "Production deployment requires explicit approval" in plan["risks"]
    assert "Repository policy validation failed" in plan["risks"]


def test_plan_mode_reflects_caller_intent_not_gate_decision():
    analysis = detect_stack(["Dockerfile", "package.json"])
    policy = {
        "allowed_environments": ["staging"],
        "allowed_app_providers": ["render"],
        "allowed_database_providers": ["supabase"],
        "production": {"allowed": False, "requires_approval": True},
    }

    plan = generate_deployment_plan(
        analysis,
        environment="staging",
        policy=policy,
        mode="execute",
    )

    assert plan["policy_result"]["valid"] is False
    assert plan["mode"] == "execute"
