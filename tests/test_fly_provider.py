from deploy_orchestrator_mcp.fly_provider import fly_generate_app_plan, fly_validate_request


def test_fly_validate_request_blocks_when_provider_not_allowed(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PROVIDERS", "render,railway,supabase")

    result = fly_validate_request(environment="staging")

    assert result["provider"] == "fly"
    assert result["valid"] is False
    assert result["errors"]


def test_fly_validate_request_allows_staging_when_provider_allowed(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PROVIDERS", "render,railway,supabase,fly")
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    result = fly_validate_request(environment="staging")

    assert result["provider"] == "fly"
    assert result["valid"] is True
    assert result["mode"] == "dry-run"


def test_fly_app_plan_is_dry_run(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PROVIDERS", "render,railway,supabase,fly")
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    plan = fly_generate_app_plan(
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        app_name="deploy-orchestrator-mcp",
        environment="staging",
        needs_volume=True,
    )

    assert plan["provider"] == "fly"
    assert plan["needs_volume"] is True
    assert plan["mode"] == "dry-run"
    assert "create volume" in plan["approval_required"]
    assert plan["validation"]["valid"] is True
