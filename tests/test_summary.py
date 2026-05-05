from deploy_orchestrator_mcp.analyzer import analyze_file_list
from deploy_orchestrator_mcp.planner import generate_deployment_plan
from deploy_orchestrator_mcp.summary import format_deployment_plan_summary


def test_summary_formats_valid_plan_deterministically():
    analysis = analyze_file_list(["pyproject.toml", "README.md"])
    plan = generate_deployment_plan(analysis)

    first = format_deployment_plan_summary(plan)
    second = format_deployment_plan_summary(plan)

    assert first == second
    assert first.startswith("## Deployment plan summary\n")
    assert "- Environment: staging" in first
    assert "- App provider: render" in first
    assert "- Database provider: None" in first
    assert "- Policy result: pass" in first
    assert "### Approval-required actions" in first
    assert "- create service" in first
    assert "### Risks" in first
    assert "### Steps" in first


def test_summary_formats_policy_blocked_plan_with_errors_and_risks():
    analysis = analyze_file_list(["Dockerfile", "package.json"])
    policy = {
        "allowed_environments": ["staging"],
        "allowed_app_providers": ["render"],
        "allowed_database_providers": ["supabase"],
        "production": {"allowed": False, "requires_approval": True},
    }
    plan = generate_deployment_plan(analysis, environment="production", policy=policy)

    summary = format_deployment_plan_summary(plan)

    assert "- Environment: production" in summary
    assert "- App provider: fly" in summary
    assert "- Policy result: fail" in summary
    assert "Environment 'production' is not allowed by repository policy" in summary
    assert "App provider 'fly' is not allowed by repository policy" in summary
    assert "- production deployment" in summary
    assert "- Repository policy validation failed" in summary
    assert "Production deployment requires explicit approval" in summary


def test_summary_redacts_sensitive_values_before_formatting():
    plan = {
        "environment": "staging",
        "mode": "dry-run",
        "app_provider": {
            "provider": "render",
            "reason": "token=12345678901234567890123456789012",
        },
        "database_provider": {
            "provider": "supabase",
            "reason": "postgres://user:password@example.com/db",
        },
        "policy_result": {"valid": True, "errors": []},
        "approval_required": True,
        "approval_required_actions": ["set environment variables"],
        "risks": [],
        "steps": ["Configure service"],
    }

    summary = format_deployment_plan_summary(plan)

    assert "12345678901234567890123456789012" not in summary
    assert "postgres://user:password@example.com/db" not in summary
    assert "[REDACTED]" in summary
    assert "set environment variables" in summary
