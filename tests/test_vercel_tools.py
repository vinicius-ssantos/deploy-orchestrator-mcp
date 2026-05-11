"""Tests for Vercel MCP tool gates."""

from deploy_orchestrator_mcp import server as server


DEFAULT_ARGS = {
    "project_name": "deploy-orchestrator-mcp-frontend",
    "repo": "vinicius-ssantos/deploy-orchestrator-mcp-frontend",
    "repo_id": "1234007615",
    "branch": "scaffold/deploy-readiness-console",
}


def _call(***coverrides):
    args = {**DEFAULT_ARGS, }
    args.update(overrides)
    return server.vercel_deploy_preview(**args)


def test_vercel_deploy_preview_blocks_without_approval():
    result = _call(approval="NO", ci_gate_allowed=True)
    assert result["ok"] is False
    assert result["triggered"] is False
    assert "approval" in result["missing_fields"]



def test_vercel_deploy_preview_blocks_when_ci_gate_fails():
    result = _call(approval="APPROVED", ci_gate_allowed=False, ci_gate_reason="checks failed")
    assert result["ok"] is False
    assert result["triggered"] is False
    assert "ci_gate" in result["missing_fields"]
    assert any("CI gate" in error for error in result["errors"])



def test_vercel_deploy_preview_blocks_sensitive_public_env_vars():
    result = _call(
        approval="APPROVED",
        ci_gate_allowed=True,
        env_var_names=["VITE_DEFAULT_MCP_URL", "VITE_MCP_TOKEN"],
    )
    assert result["ok"] is False
    assert result["triggered"] is False
    assert result["public_env_check"]["ok"] is False
    assert "VITE_MCP_TOKEN" in result["public_env_check"]["exposed_candidates"]


def test_vercel_deploy_preview_blocks_when_provider_policy_denies(monkeypatch):
    monkeypatch.setattr(
        server,
        "is_frontend_provider_allowed_by_policy",
        lambda policy, provider: False,
        raising=False,
    )
    result = _call(approval="APPROVED", ci_gate_allowed=True)
    assert result["ok"] is False
    assert result["triggered"] is False
    assert any("vercel" in error for error in result["errors"])


def test_vercel_deploy_preview_calls_api_when_gates_pass(monkeypatch):
    captured = {}

    def fake_deploy_preview(**args):
        captured.update(args)
        return {"ok": True, "triggered": True, "deployment_id": "dpl_123"}

    monkeypatch.setattr(server, "vercel_api_deploy_preview", fake_deploy_preview)

    result = _call(
        approval="APPROVED",
        ci_gate_allowed=True,
        ci_gate_head_sha="abc123",
        env_var_names=["VITE_DEFAULT_MCP_URL"],
    )
    assert result["ok"] is True
    assert captured["project_name"] == DEFAULT_ARGS["project_name"]
    assert captured["repo_id"] == DEFAULT_ARGS["repo_id"]
    assert captured["branch"] == DEFAULT_ARGS["branch"]
