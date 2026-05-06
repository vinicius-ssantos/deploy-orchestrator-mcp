import httpx
import pytest

from deploy_orchestrator_mcp.railway_api import (
    railway_deploy,
    railway_get_project,
    railway_list_deployments,
    railway_list_projects,
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
        result = railway_deploy("svc-1", "env-1", approval="APPROVED", client=client)

    assert result["triggered"] is True
    assert result["gate"]["allowed"] is True


def test_deploy_missing_token(monkeypatch):
    monkeypatch.delenv("RAILWAY_TOKEN", raising=False)
    result = railway_deploy("svc-1", "env-1", approval="APPROVED")
    assert result["triggered"] is False
    assert any("not configured" in e for e in result["errors"])
