"""Tests for Vercel preview protection policy gates."""

from deploy_orchestrator_mcp import server


DEFAULT_ARGS = {
    "project_name": "deploy-orchestrator-mcp-frontend",
    "repo": "vinicius-ssantos/deploy-orchestrator-mcp-frontend",
    "repo_id": "1234007615",
    "branch": "scaffold/deploy-readiness-console",
}


def _call(**overrides):
    args = {**DEFAULT_ARGS}
    args.update(overrides)
    return server.vercel_deploy_preview(**args)


def test_vercel_deploy_preview_blocks_invalid_protection_mode():
    result = _call(
        approval="APPROVED",
        ci_gate_allowed=True,
        deployment_protection="magic_link",
    )
    assert result["ok"] is False
    assert result["triggered"] is False
    assert any("deployment_protection" in error for error in result["errors"])


def test_vercel_deploy_preview_blocks_when_protection_required_but_none():
    result = _call(
        approval="APPROVED",
        ci_gate_allowed=True,
        require_protection=True,
        deployment_protection="none",
    )
    assert result["ok"] is False
    assert result["triggered"] is False
    assert result["publicly_accessible"] is True
    assert result["protection_enabled"] is False


def test_vercel_deploy_preview_blocks_bypass_ci_without_protection():
    result = _call(
        approval="APPROVED",
        ci_gate_allowed=True,
        ci_gate_reason="APPROVED BYPASS_CI for urgent preview",
        deployment_protection="none",
    )
    assert result["ok"] is False
    assert result["triggered"] is False
    assert any("BYPASS_CI" in error for error in result["errors"])


def test_vercel_deploy_preview_passes_protection_metadata_to_api(monkeypatch):
    captured = {}

    def fake_deploy_preview(**args):
        captured.update(args)
        return {
            "ok": True,
            "triggered": True,
            "deployment_id": "dpl_123",
            "protection_enabled": True,
            "protection_mode": args["deployment_protection"],
            "publicly_accessible": False,
        }

    monkeypatch.setattr(server, "vercel_api_deploy_preview", fake_deploy_preview)

    result = _call(
        approval="APPROVED",
        ci_gate_allowed=True,
        deployment_protection="vercel_auth",
        require_protection=True,
        protection_reason="review private preview",
    )

    assert result["ok"] is True
    assert result["triggered"] is True
    assert captured["deployment_protection"] == "vercel_auth"
    assert captured["require_protection"] is True
    assert captured["protection_reason"] == "review private preview"
