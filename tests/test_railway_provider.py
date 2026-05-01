from deploy_orchestrator_mcp.railway_provider import (
    railway_generate_postgres_plan,
    railway_generate_service_plan,
    railway_validate_request,
)


def test_railway_validate_request_allows_staging_by_default(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_PROVIDERS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    result = railway_validate_request(environment="staging")

    assert result["provider"] == "railway"
    assert result["environment"] == "staging"
    assert result["valid"] is True
    assert result["mode"] == "dry-run"


def test_railway_service_plan_with_postgres_is_dry_run(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_PROVIDERS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    plan = railway_generate_service_plan(
        repo_full_name="vinicius-ssantos/deploy-orchestrator-mcp",
        service_name="deploy-orchestrator-mcp",
        environment="staging",
        needs_postgres=True,
    )

    assert plan["provider"] == "railway"
    assert plan["needs_postgres"] is True
    assert plan["mode"] == "dry-run"
    assert "create postgres service" in plan["approval_required"]
    assert plan["validation"]["valid"] is True


def test_railway_postgres_plan_is_dry_run(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_PROVIDERS", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_ENVIRONMENTS", raising=False)

    plan = railway_generate_postgres_plan(
        project_name="deploy-orchestrator-mcp",
        environment="staging",
    )

    assert plan["provider"] == "railway"
    assert plan["database"] == "postgres"
    assert plan["mode"] == "dry-run"
    assert "apply migrations" in plan["approval_required"]
