from deploy_orchestrator_mcp.coolify_provider import (
    coolify_generate_app_plan,
    coolify_generate_database_plan,
    coolify_validate_request,
)


def test_coolify_validate_request_blocks_when_provider_not_allowed(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PROVIDERS", "render,railway,supabase")

    result = coolify_validate_request(environment="staging")

    assert result["provider"] == "coolify"
    assert result["valid"] is False
    assert result["errors"]


def test_coolify_app_plan_with_preview_is_dry_run(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PROVIDERS", "render,railway,supabase,coolify")
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    plan = coolify_generate_app_plan(
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        project_name="mcp-hub",
        app_name="deploy-orchestrator-mcp",
        environment="staging",
        deployment_method="github-app",
        needs_database=True,
        enable_preview=True,
    )

    assert plan["provider"] == "coolify"
    assert plan["needs_database"] is True
    assert plan["enable_preview"] is True
    assert plan["mode"] == "dry-run"
    assert "enable preview deployments" in plan["approval_required"]
    assert plan["validation"]["valid"] is True


def test_coolify_database_plan_is_dry_run(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PROVIDERS", "render,railway,supabase,coolify")
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    plan = coolify_generate_database_plan(
        project_name="mcp-hub",
        database_name="deploy-orchestrator-db",
        engine="postgres",
        environment="staging",
    )

    assert plan["provider"] == "coolify"
    assert plan["engine"] == "postgres"
    assert plan["mode"] == "dry-run"
    assert "apply migrations" in plan["approval_required"]
