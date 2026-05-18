import json

from deploy_orchestrator_mcp.server import github_prepare_plan_report


def test_github_prepare_plan_report_returns_comment_body():
    plan = {
        "environment": "staging",
        "mode": "dry-run",
        "app_provider": {"provider": "render"},
        "database_provider": {"provider": "supabase"},
        "policy_result": {"valid": True, "errors": []},
        "approval_required": True,
        "approval_required_actions": ["create service"],
        "steps": ["create service", "trigger deploy"],
        "risks": [],
    }
    result = github_prepare_plan_report(
        plan_json=json.dumps(plan),
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        target_type="issue",
        target_number=1,
    )
    assert result["ok"] is True
    assert "Deployment plan summary" in result["comment_body"]
    assert result["target_type"] == "issue"


def test_github_prepare_plan_report_rejects_invalid_target_type():
    result = github_prepare_plan_report(
        plan_json="{}",
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        target_type="discussion",
    )
    assert result["ok"] is False
    assert "target_type must be" in result["error"]


def test_github_prepare_plan_report_rejects_invalid_json():
    result = github_prepare_plan_report(
        plan_json="{bad json",
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        target_type="pull_request",
        target_number=42,
    )
    assert result["ok"] is False
    assert "invalid plan_json" in result["error"]

