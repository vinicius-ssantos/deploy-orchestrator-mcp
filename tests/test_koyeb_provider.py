from deploy_orchestrator_mcp.koyeb_provider import koyeb_generate_service_plan, koyeb_validate_request


def test_koyeb_validate_request_blocks_when_provider_not_allowed(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PROVIDERS", "render,railway,supabase")

    result = koyeb_validate_request(environment="staging")

    assert result["provider"] == "koyeb"
    assert result["valid"] is False
    assert result["errors"]


def test_koyeb_web_service_plan_is_dry_run(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PROVIDERS", "render,railway,supabase,koyeb")
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    plan = koyeb_generate_service_plan(
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        app_name="deploy-orchestrator-mcp",
        service_name="api",
        environment="staging",
        service_type="web",
        source="github",
    )

    assert plan["provider"] == "koyeb"
    assert plan["service_type"] == "web"
    assert plan["source"] == "github"
    assert plan["mode"] == "dry-run"
    assert plan["validation"]["valid"] is True


def test_koyeb_worker_service_plan_changes_readiness_check(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PROVIDERS", "render,railway,supabase,koyeb")
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    plan = koyeb_generate_service_plan(
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        app_name="deploy-orchestrator-mcp",
        service_name="worker",
        environment="staging",
        service_type="worker",
        source="container-image",
    )

    assert plan["provider"] == "koyeb"
    assert plan["service_type"] == "worker"
    assert plan["source"] == "container-image"
    assert "run worker readiness check" in plan["planned_actions"]
