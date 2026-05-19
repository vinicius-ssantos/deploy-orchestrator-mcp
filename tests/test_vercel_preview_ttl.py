"""Tests for Vercel preview TTL and retention metadata."""

from deploy_orchestrator_mcp import server
from deploy_orchestrator_mcp.vercel_api import vercel_deploy_preview


DEFAULT_ARGS = {
    "project_name": "github-unified-mcp-frontend",
    "repo": "vinicius-ssantos/github-unified-mcp-frontend",
    "repo_id": "1233024010",
    "branch": "main",
}


def _call(**overrides):
    args = {**DEFAULT_ARGS}
    args.update(overrides)
    return server.vercel_deploy_preview(**args)


def test_vercel_preview_blocks_invalid_cleanup_policy():
    result = _call(
        approval="APPROVED",
        ci_gate_allowed=True,
        deployment_protection="vercel_auth",
        cleanup_policy="hibernate",
    )

    assert result["ok"] is False
    assert result["triggered"] is False
    assert any("cleanup_policy" in error for error in result["errors"])


def test_vercel_preview_blocks_non_positive_ttl():
    result = _call(
        approval="APPROVED",
        ci_gate_allowed=True,
        deployment_protection="vercel_auth",
        ttl_hours=0,
    )

    assert result["ok"] is False
    assert result["triggered"] is False
    assert any("ttl_hours" in error for error in result["errors"])


def test_vercel_preview_defaults_bypass_ci_ttl_to_24_hours(monkeypatch):
    captured = {}

    def fake_deploy_preview(**args):
        captured.update(args)
        return {
            "ok": True,
            "triggered": True,
            "deployment_id": "dpl_ttl",
            "ttl_hours": args["ttl_hours"],
            "cleanup_policy": args["cleanup_policy"],
        }

    monkeypatch.setattr(server, "vercel_api_deploy_preview", fake_deploy_preview)

    result = _call(
        approval="APPROVED",
        ci_gate_allowed=True,
        ci_gate_reason="APPROVED BYPASS_CI for private review",
        deployment_protection="vercel_auth",
    )

    assert result["ok"] is True
    assert captured["ttl_hours"] == 24
    assert captured["cleanup_policy"] == "warn"


def test_vercel_preview_delete_after_ttl_defaults_to_168_hours(monkeypatch):
    captured = {}

    def fake_deploy_preview(**args):
        captured.update(args)
        return {"ok": True, "triggered": True, "ttl_hours": args["ttl_hours"]}

    monkeypatch.setattr(server, "vercel_api_deploy_preview", fake_deploy_preview)

    result = _call(
        approval="APPROVED",
        ci_gate_allowed=True,
        deployment_protection="vercel_auth",
        cleanup_policy="delete_after_ttl",
    )

    assert result["ok"] is True
    assert captured["ttl_hours"] == 168


def test_vercel_api_returns_ttl_metadata(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok")

    class DummyResponse:
        status_code = 200
        is_error = False

        def json(self):
            return {
                "id": "dpl_ttl",
                "url": "preview.example.vercel.app",
                "readyState": "INITIALIZING",
            }

    class DummyClient:
        def post(self, *args, **kwargs):
            return DummyResponse()

    result = vercel_deploy_preview(
        project_name="github-unified-mcp-frontend",
        repo="vinicius-ssantos/github-unified-mcp-frontend",
        repo_id="1233024010",
        branch="main",
        deployment_protection="vercel_auth",
        ttl_hours=24,
        cleanup_policy="warn",
        requested_by="operator",
        client=DummyClient(),
    )

    assert result["ok"] is True
    assert result["ttl_hours"] == 24
    assert result["expires_at"] is not None
    assert result["cleanup_policy"] == "warn"
    assert result["requested_by"] == "operator"
