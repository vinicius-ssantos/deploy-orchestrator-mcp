"""Tests for Supabase real API integration (all HTTP mocked)."""

import httpx
import pytest

from deploy_orchestrator_mcp.supabase_api import (
    supabase_apply_migration,
    supabase_create_project,
    supabase_get_connection_info,
    supabase_get_project_status,
    supabase_healthcheck,
    supabase_list_organizations,
    supabase_list_projects,
    supabase_validate_credentials,
)


def _mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="https://api.supabase.com/v1", transport=transport)


def valid_ci_gate(head_sha="abc123"):
    return {
        "allowed": True,
        "blocking_checks": [],
        "summary": "All workflows succeeded",
        "head_sha": head_sha,
    }


# ---------------------------------------------------------------------------
# supabase_validate_credentials
# ---------------------------------------------------------------------------


def test_validate_credentials_missing_token(monkeypatch):
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    result = supabase_validate_credentials()
    assert result["valid"] is False
    assert "errors" in result


def test_validate_credentials_valid(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        assert "Authorization" in request.headers
        return httpx.Response(200, json=[{"id": "org-1", "name": "My Org"}])

    with _mock_client(handler) as client:
        result = supabase_validate_credentials(client=client)

    assert result["valid"] is True
    assert result["organization_count"] == 1
    assert "audit_event" in result


def test_validate_credentials_api_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        return httpx.Response(401, json={"message": "Invalid token"})

    with _mock_client(handler) as client:
        result = supabase_validate_credentials(client=client)

    assert result["valid"] is False
    assert "errors" in result


# ---------------------------------------------------------------------------
# supabase_list_organizations
# ---------------------------------------------------------------------------


def test_list_organizations_missing_token(monkeypatch):
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    result = supabase_list_organizations()
    assert "errors" in result


def test_list_organizations_happy_path(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        assert request.url.path == "/v1/organizations"
        return httpx.Response(200, json=[
            {"id": "org-1", "name": "Acme Corp"},
            {"id": "org-2", "name": "Personal"},
        ])

    with _mock_client(handler) as client:
        result = supabase_list_organizations(client=client)

    assert result["count"] == 2
    assert result["organizations"][0]["id"] == "org-1"
    assert result["organizations"][1]["name"] == "Personal"
    assert "audit_event" in result


def test_list_organizations_empty(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        return httpx.Response(200, json=[])

    with _mock_client(handler) as client:
        result = supabase_list_organizations(client=client)

    assert result["count"] == 0
    assert result["organizations"] == []


# ---------------------------------------------------------------------------
# supabase_list_projects
# ---------------------------------------------------------------------------


def test_list_projects_missing_token(monkeypatch):
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    result = supabase_list_projects()
    assert "errors" in result


def test_list_projects_happy_path(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        assert request.url.path == "/v1/projects"
        return httpx.Response(200, json=[
            {"id": "proj-abc", "name": "my-app", "organization_id": "org-1",
             "region": "us-east-1", "status": "ACTIVE_HEALTHY"},
        ])

    with _mock_client(handler) as client:
        result = supabase_list_projects(client=client)

    assert result["count"] == 1
    assert result["projects"][0]["id"] == "proj-abc"
    assert result["projects"][0]["status"] == "ACTIVE_HEALTHY"
    assert "audit_event" in result


# ---------------------------------------------------------------------------
# supabase_get_project_status
# ---------------------------------------------------------------------------


def test_get_project_status_missing_token(monkeypatch):
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    result = supabase_get_project_status("proj-abc")
    assert "errors" in result


def test_get_project_status_happy_path(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        assert request.url.path == "/v1/projects/proj-abc"
        return httpx.Response(200, json={
            "id": "proj-abc",
            "name": "my-app",
            "status": "ACTIVE_HEALTHY",
            "region": "us-east-1",
            "organization_id": "org-1",
        })

    with _mock_client(handler) as client:
        result = supabase_get_project_status("proj-abc", client=client)

    assert result["project_id"] == "proj-abc"
    assert result["status"] == "ACTIVE_HEALTHY"
    assert result["region"] == "us-east-1"
    assert "audit_event" in result


def test_get_project_status_404(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        return httpx.Response(404, json={"message": "project not found"})

    with _mock_client(handler) as client:
        result = supabase_get_project_status("bad-proj", client=client)

    assert result["status"] is None
    assert "errors" in result


# ---------------------------------------------------------------------------
# supabase_get_connection_info
# ---------------------------------------------------------------------------


def test_get_connection_info_missing_token(monkeypatch):
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    result = supabase_get_connection_info("proj-abc")
    assert "errors" in result


def test_get_connection_info_never_returns_service_role(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        return httpx.Response(200, json=[
            {"name": "anon", "role": "anon", "api_key": "secret-anon-key"},
            {"name": "service_role", "role": "service_role", "api_key": "secret-service-key"},
        ])

    with _mock_client(handler) as client:
        result = supabase_get_connection_info("proj-abc", client=client)

    # service_role must not appear in the result
    result_str = str(result)
    assert "service_role" not in result_str or "key_roles" in result
    # api_key values must not be present
    assert "secret-anon-key" not in result_str
    assert "secret-service-key" not in result_str
    # Only anon role exposed
    assert any(k["role"] == "anon" for k in result.get("key_roles", []))
    assert not any(k.get("role") == "service_role" for k in result.get("key_roles", []))


def test_get_connection_info_includes_project_url(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        return httpx.Response(200, json=[])

    with _mock_client(handler) as client:
        result = supabase_get_connection_info("proj-abc", client=client)

    assert "proj-abc.supabase.co" in result.get("project_url", "")


# ---------------------------------------------------------------------------
# supabase_healthcheck
# ---------------------------------------------------------------------------


def test_healthcheck_missing_token(monkeypatch):
    monkeypatch.delenv("SUPABASE_ACCESS_TOKEN", raising=False)
    result = supabase_healthcheck("proj-abc")
    assert "errors" in result


def test_healthcheck_healthy_project(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def api_handler(request):
        return httpx.Response(200, json={
            "id": "proj-abc", "status": "ACTIVE_HEALTHY",
        })

    def ping_handler(request):
        return httpx.Response(401)  # 401 = reachable but unauthenticated

    with _mock_client(api_handler) as client:
        ping_transport = httpx.MockTransport(ping_handler)
        ping_client = httpx.Client(transport=ping_transport)
        result = supabase_healthcheck("proj-abc", client=client, http_client=ping_client)
        ping_client.close()

    assert result["healthy"] is True
    assert result["project_status"] == "ACTIVE_HEALTHY"
    assert result["reachable"] is True


def test_healthcheck_unhealthy_project(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def api_handler(request):
        return httpx.Response(200, json={"id": "proj-abc", "status": "INACTIVE"})

    def ping_handler(request):
        return httpx.Response(503)

    with _mock_client(api_handler) as client:
        ping_transport = httpx.MockTransport(ping_handler)
        ping_client = httpx.Client(transport=ping_transport)
        result = supabase_healthcheck("proj-abc", client=client, http_client=ping_client)
        ping_client.close()

    assert result["healthy"] is False
    assert result["project_status"] == "INACTIVE"


def test_healthcheck_api_error(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        return httpx.Response(404, json={"message": "not found"})

    with _mock_client(handler) as client:
        result = supabase_healthcheck("bad-proj", client=client)

    assert result["healthy"] is False
    assert "errors" in result


# ---------------------------------------------------------------------------
# Supabase write actions (approval + CI gate)
# ---------------------------------------------------------------------------


def test_create_project_blocks_without_gate():
    result = supabase_create_project(
        "my-app",
        "org-1",
        approval="NO",
        ci_gate=None,
    )
    assert result["created"] is False
    assert result["gate"]["allowed"] is False


def test_create_project_happy_path(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        assert request.url.path == "/v1/projects"
        payload = request.read().decode("utf-8")
        assert "my-app" in payload
        return httpx.Response(201, json={
            "id": "proj-1",
            "name": "my-app",
            "organization_id": "org-1",
            "region": "us-east-1",
            "status": "INACTIVE",
        })

    with _mock_client(handler) as client:
        result = supabase_create_project(
            "my-app",
            "org-1",
            approval="APPROVED",
            ci_gate=valid_ci_gate(),
            client=client,
        )

    assert result["created"] is True
    assert result["project_id"] == "proj-1"


def test_apply_migration_blocks_when_sql_missing():
    result = supabase_apply_migration(
        "proj-1",
        "m1",
        "",
        approval="APPROVED",
        ci_gate=valid_ci_gate(),
    )
    assert result["applied"] is False
    assert "sql is required" in result["errors"]


def test_apply_migration_happy_path(monkeypatch):
    monkeypatch.setenv("SUPABASE_ACCESS_TOKEN", "sbp_test_token_0000000000000000")

    def handler(request):
        assert request.url.path == "/v1/projects/proj-1/database/query"
        payload = request.read().decode("utf-8")
        assert "create table" in payload.lower()
        return httpx.Response(200, json={"ok": True})

    with _mock_client(handler) as client:
        result = supabase_apply_migration(
            "proj-1",
            "m1",
            "create table test(id int);",
            approval="APPROVED",
            ci_gate=valid_ci_gate(),
            client=client,
        )

    assert result["applied"] is True
    assert result["result"]["ok"] is True
