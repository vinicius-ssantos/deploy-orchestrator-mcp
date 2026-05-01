from deploy_orchestrator_mcp.render_provider import render_generate_service_plan, render_validate_request


def test_render_validate_request_allows_staging_by_default(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_PROVIDERS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    result = render_validate_request(environment="staging")

    assert result["provider"] == "render"
    assert result["environment"] == "staging"
    assert result["valid"] is True
    assert result["mode"] == "dry-run"


def test_render_validate_request_blocks_disallowed_environment(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_ENVIRONMENTS", "preview,staging")

    result = render_validate_request(environment="production")

    assert result["valid"] is False
    assert result["errors"]


def test_render_service_plan_is_dry_run(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_PROVIDERS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    plan = render_generate_service_plan(
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        service_name="deploy-orchestrator-mcp",
        environment="staging",
    )

    assert plan["provider"] == "render"
    assert plan["mode"] == "dry-run"
    assert "trigger deployment" in plan["approval_required"]
    assert plan["validation"]["valid"] is True
