from deploy_orchestrator_mcp.supabase_provider import supabase_generate_project_plan, supabase_validate_request


def test_supabase_validate_request_allows_staging_by_default(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_PROVIDERS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    result = supabase_validate_request(environment="staging")

    assert result["provider"] == "supabase"
    assert result["environment"] == "staging"
    assert result["valid"] is True
    assert result["mode"] == "dry-run"


def test_supabase_validate_request_blocks_disallowed_environment(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_ENVIRONMENTS", "preview,staging")

    result = supabase_validate_request(environment="production")

    assert result["valid"] is False
    assert result["errors"]


def test_supabase_project_plan_is_dry_run(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_PROVIDERS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    plan = supabase_generate_project_plan(
        project_name="deploy-orchestrator-mcp",
        environment="staging",
        needs_auth=True,
        needs_storage=True,
    )

    assert plan["provider"] == "supabase"
    assert plan["mode"] == "dry-run"
    assert plan["needs_auth"] is True
    assert plan["needs_storage"] is True
    assert "apply migrations" in plan["approval_required"]
    assert plan["validation"]["valid"] is True
    assert plan["secrets_policy"]
