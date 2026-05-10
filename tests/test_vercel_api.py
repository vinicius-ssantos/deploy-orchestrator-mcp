"""Tests for Vercel API integration (all HTTP mocked)."""

import httpx
import pytest

from deploy_orchestrator_mcp.vercel_api import (
    check_public_env_vars,
    vercel_deploy_preview,
    vercel_get_deploy_status,
    vercel_project_plan,
    vercel_validate_credentials,
)


def _mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="https://api.vercel.com", transport=transport)


# ---------------------------------------------------------------------------
# check_public_env_vars
# ---------------------------------------------------------------------------


def test_check_public_env_vars_clean():
    result = check_public_env_vars(["VITE_TITLE", "VITE_APP_NAME", "NODE_ENV"])
    assert result["ok"] is True
    assert result["exposed_candidates"] == []


def test_check_public_env_vars_detects_sensitive():
    result = check_public_env_vars(["VITE_API_KEY", "VITE_TITLE", "NEXT_PUBLIC_SECRET"])
    assert result["ok"] is False
    assert "VITE_API_KEY" in result["exposed_candidates"]
    assert "NEXT_PUBLIC_SECRET" in result["exposed_candidates"]
    assert "VITE_TITLE" not in result["exposed_candidates"]


def test_check_public_env_vars_non_public_sensitive_ignored():
    result = check_public_env_vars(["DB_PASSWORD", "API_SECRET", "JWT_SECRET"])
    assert result["ok"] is True


def test_check_public_env_vars_all_prefixes():
    result = check_public_env_vars([
        "VITE_TOKEN",
        "NEXT_PUBLIC_PASSWORD",
        "REACT_APP_SECRET",
        "PUBLIC_KEY",
    ])
    assert result["ok"] is False
    assert len(result["exposed_candidates"]) == 4


def test_check_public_env_vars_empty():
    result = check_public_env_vars([])
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# vercel_validate_credentials
# ---------------------------------------------------------------------------


def test_validate_credentials_missing_token(monkeypatch):
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    result = vercel_validate_credentials()
    assert result["ok"] is False
    assert result["configured"] is False
    assert any("not configured" in e for e in result["errors"])


def test_validate_credentials_valid(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "test_vercel_token")

    def handler(request):
        assert request.headers["Authorization"] == "Bearer test_vercel_token"
        assert "/v2/user" in str(request.url)
        return httpx.Response(200, json={"user": {"username": "vinicius", "email": "v@test.com"}})

    with _mock_client(handler) as client:
        result = vercel_validate_credentials(client=client)

    assert result["ok"] is True
    assert result["valid"] is True
    assert result["username"] == "vinicius"
    assert "audit_event" in result


def test_validate_credentials_http_error(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok_bad")

    def handler(request):
        return httpx.Response(401, json={"error": {"code": "forbidden"}})

    with _mock_client(handler) as client:
        result = vercel_validate_credentials(client=client)

    assert result["ok"] is False
    assert result["valid"] is False
    assert "errors" in result


def test_validate_credentials_token_not_in_response(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "secret_token_xyz")

    def handler(request):
        return httpx.Response(200, json={"user": {"username": "user"}})

    with _mock_client(handler) as client:
        result = vercel_validate_credentials(client=client)

    result_str = str(result)
    assert "secret_token_xyz" not in result_str


# ---------------------------------------------------------------------------
# vercel_project_plan
# ---------------------------------------------------------------------------


def test_project_plan_is_dry_run(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok")
    result = vercel_project_plan(
        project_name="my-frontend",
        repo="org/my-frontend",
        branch="main",
    )
    assert result["mode"] == "dry-run"
    assert result["production"] is False
    assert result["environment"] == "preview"
    assert result["approval_required"] is True


def test_project_plan_no_http_calls(monkeypatch):
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    # Even without token, plan should return (dry-run makes no HTTP calls)
    result = vercel_project_plan(
        project_name="test",
        repo="org/test",
        branch="main",
    )
    assert result["mode"] == "dry-run"
    assert result["credentials_configured"] is False


def test_project_plan_env_check_clean(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok")
    result = vercel_project_plan(
        project_name="test",
        repo="org/test",
        branch="main",
        env_var_names=["VITE_TITLE", "NODE_ENV"],
    )
    assert result["public_env_check"]["ok"] is True


def test_project_plan_env_check_flags_sensitive(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok")
    result = vercel_project_plan(
        project_name="test",
        repo="org/test",
        branch="main",
        env_var_names=["VITE_API_KEY", "VITE_TITLE"],
    )
    assert result["public_env_check"]["ok"] is False
    assert "VITE_API_KEY" in result["public_env_check"]["exposed_candidates"]


def test_project_plan_defaults(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok")
    result = vercel_project_plan(project_name="app", repo="org/app", branch="dev")
    assert result["framework"] == "vite"
    assert result["build_command"] == "npm run build"
    assert result["output_dir"] == "dist"


# ---------------------------------------------------------------------------
# vercel_deploy_preview
# ---------------------------------------------------------------------------


def test_deploy_preview_missing_token(monkeypatch):
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    result = vercel_deploy_preview(
        project_name="app",
        repo="org/app",
        repo_id="12345",
        branch="main",
    )
    assert result["ok"] is False
    assert result["triggered"] is False
    assert any("not configured" in e for e in result["errors"])


def test_deploy_preview_success(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok_deploy")

    def handler(request):
        assert "/v13/deployments" in str(request.url)
        import json
        body = json.loads(request.content)
        assert body["gitSource"]["type"] == "github"
        assert body["gitSource"]["ref"] == "feat/new-ui"
        assert "target" not in body  # must never set target: production
        return httpx.Response(200, json={
            "id": "dpl_abc123",
            "url": "my-app-xyz.vercel.app",
            "readyState": "INITIALIZING",
        })

    with _mock_client(handler) as client:
        result = vercel_deploy_preview(
            project_name="my-app",
            repo="org/my-app",
            repo_id="99999",
            branch="feat/new-ui",
            client=client,
        )

    assert result["ok"] is True
    assert result["triggered"] is True
    assert result["deployment_id"] == "dpl_abc123"
    assert result["url"] == "https://my-app-xyz.vercel.app"
    assert result["target"] == "preview"
    assert "audit_event" in result


def test_deploy_preview_api_error(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok_bad")

    def handler(request):
        return httpx.Response(403, json={"error": {"code": "forbidden", "message": "Access denied"}})

    with _mock_client(handler) as client:
        result = vercel_deploy_preview(
            project_name="app",
            repo="org/app",
            repo_id="111",
            branch="main",
            client=client,
        )

    assert result["ok"] is False
    assert result["triggered"] is False
    assert "errors" in result


def test_deploy_preview_url_prefixed(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok")

    def handler(request):
        return httpx.Response(200, json={
            "id": "dpl_xyz",
            "url": "app-preview.vercel.app",
            "readyState": "BUILDING",
        })

    with _mock_client(handler) as client:
        result = vercel_deploy_preview(
            project_name="app", repo="org/app", repo_id="1", branch="main", client=client,
        )

    assert result["url"].startswith("https://")


def test_deploy_preview_token_not_in_response(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "super_secret_vercel_token")

    def handler(request):
        return httpx.Response(200, json={"id": "dpl_1", "url": "app.vercel.app", "readyState": "READY"})

    with _mock_client(handler) as client:
        result = vercel_deploy_preview(
            project_name="app", repo="org/app", repo_id="1", branch="main", client=client,
        )

    assert "super_secret_vercel_token" not in str(result)


# ---------------------------------------------------------------------------
# vercel_get_deploy_status
# ---------------------------------------------------------------------------


def test_get_deploy_status_missing_token(monkeypatch):
    monkeypatch.delenv("VERCEL_TOKEN", raising=False)
    result = vercel_get_deploy_status(deployment_id="dpl_abc")
    assert result["ok"] is False
    assert "errors" in result


def test_get_deploy_status_ready(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok")

    def handler(request):
        assert "dpl_test123" in str(request.url)
        return httpx.Response(200, json={
            "id": "dpl_test123",
            "readyState": "READY",
            "url": "app-final.vercel.app",
            "createdAt": 1700000000000,
            "target": None,
        })

    with _mock_client(handler) as client:
        result = vercel_get_deploy_status(deployment_id="dpl_test123", client=client)

    assert result["ok"] is True
    assert result["status"] == "READY"
    assert result["deployment_id"] == "dpl_test123"
    assert result["url"].startswith("https://")
    assert "audit_event" in result


def test_get_deploy_status_building(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok")

    def handler(request):
        return httpx.Response(200, json={
            "id": "dpl_building",
            "readyState": "BUILDING",
            "url": "app-xxx.vercel.app",
            "createdAt": 1700000000000,
        })

    with _mock_client(handler) as client:
        result = vercel_get_deploy_status(deployment_id="dpl_building", client=client)

    assert result["ok"] is True
    assert result["status"] == "BUILDING"


def test_get_deploy_status_api_error(monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", "tok")

    def handler(request):
        return httpx.Response(404, json={"error": {"code": "not_found"}})

    with _mock_client(handler) as client:
        result = vercel_get_deploy_status(deployment_id="dpl_gone", client=client)

    assert result["ok"] is False
    assert "errors" in result
