import httpx
import pytest

from deploy_orchestrator_mcp.railway_api import (
    railway_deploy,
    railway_get_deploy_status,
    railway_get_postgres_status,
    railway_get_project,
    railway_healthcheck,
    railway_list_deployments,
    railway_list_projects,
    railway_provision_postgres,
    railway_validate_credentials,
)


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# validate_credentials
# ---------------------------------------------------------------------------


def test_validate_credentials_ok(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        body = request.read()
        assert b"me" in body
        return httpx.Response(200, json={"data": {"me": {"id": "u1", "name": "Vinicius", "email": "v@test.com"}}})

    with _mock_client(handler) as client:
        result = railway_validate_credentials(client=client)

    assert result["valid"] is True
    assert result["user"] == "Vinicius"


def test_validate_credentials_missing_token(monkeypatch):
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    result = railway_validate_credentials()
    assert result["valid"] is False
    assert any("not configured" in e for e in result["errors"])


def test_validate_credentials_graphql_error(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_bad")

    def handler(request):
        return httpx.Response(200, json={"errors": [{"message": "Unauthorized"}]})

    with _mock_client(handler) as client:
        result = railway_validate_credentials(client=client)

    assert result["valid"] is False


# ---------------------------------------------------------------------------
# list_projects
# ---------------------------------------------------------------------------


def test_list_projects_ok(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={
            "data": {
                "projects": {
                    "edges": [
                        {"node": {"id": "proj-1", "name": "my-app", "description": None, "createdAt": "2024-01-01"}},
                        {"node": {"id": "proj-2", "name": "other-app", "description": "desc", "createdAt": "2024-02-01"}},
                    ]
                }
            }
        })

    with _mock_client(handler) as client:
        result = railway_list_projects(client=client)

    assert result["ok"] is True
    assert result["count"] == 2
    assert result["projects"][0]["name"] == "my-app"


def test_list_projects_missing_token(monkeypatch):
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    result = railway_list_projects()
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# get_project
# ---------------------------------------------------------------------------


def test_get_project_ok(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={
            "data": {
                "project": {
                    "id": "proj-1",
                    "name": "my-app",
                    "description": None,
                    "services": {
                        "edges": [
                            {
                                "node": {
                                    "id": "svc-1",
                                    "name": "web",
                                    "createdAt": "2024-01-01",
                                    "serviceInstances": {"edges": []},
                                }
                            }
                        ]
                    },
                    "environments": {
                        "edges": [
                            {"node": {"id": "env-1", "name": "production"}},
                            {"node": {"id": "env-2", "name": "staging"}},
                        ]
                    },
                }
            }
        })

    with _mock_client(handler) as client:
        result = railway_get_project("proj-1", client=client)

    assert result["ok"] is True
    assert result["project"]["name"] == "my-app"
    assert len(result["project"]["services"]) == 1
    assert len(result["project"]["environments"]) == 2


# ---------------------------------------------------------------------------
# list_deployments
# ---------------------------------------------------------------------------


def test_list_deployments_ok(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={
            "data": {
                "deployments": {
                    "edges": [
                        {"node": {"id": "dep-1", "status": "SUCCESS", "url": "https://app.up.railway.app", "createdAt": "2024-01-01", "updatedAt": "2024-01-01"}},
                        {"node": {"id": "dep-2", "status": "FAILED", "url": None, "createdAt": "2024-01-02", "updatedAt": "2024-01-02"}},
                    ]
                }
            }
        })

    with _mock_client(handler) as client:
        result = railway_list_deployments("svc-1", "env-1", client=client)

    assert result["ok"] is True
    assert len(result["deployments"]) == 2
    assert result["deployments"][0]["status"] == "SUCCESS"


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------


def test_deploy_blocked_without_approval(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")
    result = railway_deploy("svc-1", "env-1", approval=None)
    assert result["triggered"] is False
    assert result["gate"]["allowed"] is False


def test_deploy_triggers_when_approved(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={"data": {"serviceInstanceRedeploy": True}})

    with _mock_client(handler) as client:
        result = railway_deploy("svc-1", "env-1", approval="APPROVED", client=client,
                                ci_gate={"allowed": True, "blocking_checks": [], "summary": "All workflows succeeded", "head_sha": "abc123"})

    assert result["triggered"] is True
    assert result["gate"]["allowed"] is True


def test_deploy_missing_token(monkeypatch):
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    result = railway_deploy("svc-1", "env-1", approval="APPROVED",
                            ci_gate={"allowed": True, "blocking_checks": [], "summary": "All workflows succeeded", "head_sha": "abc123"})
    assert result["triggered"] is False
    assert any("not configured" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# get_deploy_status
# ---------------------------------------------------------------------------


def test_get_deploy_status_ok(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={
            "data": {
                "deployment": {
                    "id": "dep-1",
                    "status": "SUCCESS",
                    "url": "https://app.up.railway.app",
                    "createdAt": "2024-01-01",
                    "updatedAt": "2024-01-01",
                }
            }
        })

    with _mock_client(handler) as client:
        result = railway_get_deploy_status("dep-1", client=client)

    assert result["ok"] is True
    assert result["status"] == "SUCCESS"
    assert result["complete"] is True
    assert result["attempts"] == 1


def test_get_deploy_status_in_progress(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={
            "data": {
                "deployment": {
                    "id": "dep-2",
                    "status": "BUILDING",
                    "url": None,
                    "createdAt": "2024-01-01",
                    "updatedAt": "2024-01-01",
                }
            }
        })

    with _mock_client(handler) as client:
        result = railway_get_deploy_status("dep-2", client=client)

    assert result["ok"] is True
    assert result["complete"] is False


def test_get_deploy_status_missing_token(monkeypatch):
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    result = railway_get_deploy_status("dep-1")
    assert result["valid"] is False


def test_get_deploy_status_api_error(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={"errors": [{"message": "not found"}]})

    with _mock_client(handler) as client:
        result = railway_get_deploy_status("dep-bad", client=client)

    assert result["ok"] is False


# ---------------------------------------------------------------------------
# healthcheck
# ---------------------------------------------------------------------------


def test_healthcheck_healthy(monkeypatch):
    def handler(request):
        return httpx.Response(200)

    with _mock_client(handler) as client:
        result = railway_healthcheck("https://app.up.railway.app", client=client)

    assert result["healthy"] is True
    assert result["status_code"] == 200


def test_healthcheck_unhealthy(monkeypatch):
    def handler(request):
        return httpx.Response(503)

    with _mock_client(handler) as client:
        result = railway_healthcheck("https://app.up.railway.app", client=client)

    assert result["healthy"] is False
    assert result["status_code"] == 503


def test_healthcheck_custom_expected_status(monkeypatch):
    def handler(request):
        return httpx.Response(302)

    with _mock_client(handler) as client:
        result = railway_healthcheck("https://app.up.railway.app", expected_status=302, client=client)

    assert result["healthy"] is True


def test_healthcheck_invalid_url():
    result = railway_healthcheck("not-a-url")
    assert result["healthy"] is False
    assert "http" in result["errors"][0]


def test_healthcheck_connection_error():
    def handler(request):
        raise httpx.ConnectError("connection refused")

    with _mock_client(handler) as client:
        result = railway_healthcheck("https://app.up.railway.app", client=client)

    assert result["healthy"] is False
    assert len(result["errors"]) > 0


# ---------------------------------------------------------------------------
# provision_postgres
# ---------------------------------------------------------------------------


def test_provision_postgres_blocked_without_approval(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")
    result = railway_provision_postgres("proj-1", "env-1", approval=None)
    assert result["provisioned"] is False
    assert result["gate"]["allowed"] is False


def test_provision_postgres_ok(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={
            "data": {
                "databaseCreate": {
                    "id": "db-123",
                    "name": "postgres",
                    "databaseType": "POSTGRES",
                    "projectId": "proj-1",
                }
            }
        })

    with _mock_client(handler) as client:
        result = railway_provision_postgres("proj-1", "env-1", approval="APPROVED", client=client,
                                            ci_gate={"allowed": True, "blocking_checks": [], "summary": "All workflows succeeded", "head_sha": "abc123"})

    assert result["provisioned"] is True
    assert result["database_id"] == "db-123"
    assert result["database_type"] == "POSTGRES"
    assert result["gate"]["allowed"] is True


def test_provision_postgres_missing_token(monkeypatch):
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    result = railway_provision_postgres("proj-1", "env-1", approval="APPROVED",
                                        ci_gate={"allowed": True, "head_sha": "abc123"})
    assert result["provisioned"] is False
    assert any("not configured" in e for e in result["errors"])


def test_provision_postgres_api_error(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={"errors": [{"message": "project not found"}]})

    with _mock_client(handler) as client:
        result = railway_provision_postgres("bad-proj", "env-1", approval="APPROVED", client=client,
                                            ci_gate={"allowed": True, "head_sha": "abc123"})

    assert result["provisioned"] is False
    assert "errors" in result


# ---------------------------------------------------------------------------
# get_postgres_status
# ---------------------------------------------------------------------------


def test_get_postgres_status_connection_configured(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={
            "data": {
                "variables": {
                    "DATABASE_URL": "postgresql://user:secret@host:5432/db",
                    "PGPASSWORD": "secret",
                    "PGHOST": "roundhouse.proxy.rlwy.net",
                    "PGPORT": "12345",
                    "PGDATABASE": "railway",
                }
            }
        })

    with _mock_client(handler) as client:
        result = railway_get_postgres_status("proj-1", "env-1", "svc-1", client=client)

    assert result["ok"] is True
    assert result["connection_configured"] is True
    # Secret keys are listed but values must not appear
    assert "DATABASE_URL" in result["connection_keys_found"]
    assert "PGPASSWORD" in result["connection_keys_found"]
    # Safe vars are returned
    assert result["variables"].get("PGHOST") == "roundhouse.proxy.rlwy.net"
    assert result["variables"].get("PGPORT") == "12345"
    # Secret values must not leak anywhere in result
    assert "secret" not in str(result)
    assert "postgresql://" not in str(result)


def test_get_postgres_status_not_configured(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={"data": {"variables": {}}})

    with _mock_client(handler) as client:
        result = railway_get_postgres_status("proj-1", "env-1", "svc-1", client=client)

    assert result["ok"] is True
    assert result["connection_configured"] is False
    assert result["connection_keys_found"] == []


def test_get_postgres_status_missing_token(monkeypatch):
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    result = railway_get_postgres_status("proj-1", "env-1", "svc-1")
    assert result["valid"] is False


def test_get_postgres_status_api_error(monkeypatch):
    monkeypatch.setenv("RAILWAY_TOKEN", "tok_test")

    def handler(request):
        return httpx.Response(200, json={"errors": [{"message": "not found"}]})

    with _mock_client(handler) as client:
        result = railway_get_postgres_status("bad-proj", "env-1", "svc-1", client=client)

    assert result["ok"] is False
