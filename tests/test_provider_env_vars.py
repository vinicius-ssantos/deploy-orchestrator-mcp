import json

import httpx

from deploy_orchestrator_mcp.provider_env_vars import validate_variables
from deploy_orchestrator_mcp.railway_env_vars import railway_set_env_vars
from deploy_orchestrator_mcp.render_env_vars import render_set_env_vars


CI_GATE = {
    "allowed": True,
    "blocking_checks": [],
    "summary": "All workflows succeeded",
    "head_sha": "abc123",
    "checked_at": "2026-05-24T00:00:00Z",
}


def _render_client(handler):
    return httpx.Client(
        base_url="https://api.render.com/v1",
        transport=httpx.MockTransport(handler),
    )


def _railway_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_validate_variables_blocks_empty_and_invalid_names():
    assert validate_variables({}) == ["variables must contain at least one key"]
    assert validate_variables({"INVALID-NAME": "x"}) == ["invalid variable names: INVALID-NAME"]
    assert validate_variables({"DATABASE_URL": "x", "JWT_SECRET": "y"}) == []


def test_render_set_env_vars_success_never_returns_values():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "PUT"
        assert request.url.path in {
            "/v1/services/srv-123/env-vars/DATABASE_URL",
            "/v1/services/srv-123/env-vars/JWT_SECRET",
        }
        body = json.loads(request.content)
        assert "value" in body
        return httpx.Response(200, json={"ok": True})

    with _render_client(handler) as client:
        result = render_set_env_vars(
            service_id="srv-123",
            variables={"JWT_SECRET": "super-secret", "DATABASE_URL": "postgres://secret"},
            approval="APPROVED",
            ci_gate=CI_GATE,
            api_key="render_secret_token_123",
            client=client,
        )

    assert len(requests) == 2
    assert result["ok"] is True
    assert result["updated"] is True
    assert result["variable_names"] == ["DATABASE_URL", "JWT_SECRET"]
    assert result["count"] == 2
    assert "super-secret" not in str(result)
    assert "postgres://secret" not in str(result)
    assert "render_secret_token" not in str(result)


def test_render_set_env_vars_requires_approval_and_ci_gate():
    result = render_set_env_vars(
        service_id="srv-123",
        variables={"JWT_SECRET": "super-secret"},
        approval=None,
        ci_gate=None,
        api_key="render_secret_token_123",
    )

    assert result["ok"] is False
    assert result["updated"] is False
    assert "approval" in result["missing_fields"]
    assert "ci_gate" in result["missing_fields"]
    assert "super-secret" not in str(result)


def test_render_set_env_vars_blocks_invalid_variables_before_provider_call():
    called = {"value": False}

    def handler(request):
        called["value"] = True
        return httpx.Response(200, json={})

    with _render_client(handler) as client:
        result = render_set_env_vars(
            service_id="srv-123",
            variables={"BAD-NAME": "secret"},
            approval="APPROVED",
            ci_gate=CI_GATE,
            api_key="render_secret_token_123",
            client=client,
        )

    assert called["value"] is False
    assert result["ok"] is False
    assert result["variable_names"] == ["BAD-NAME"]
    assert "secret" not in str(result)


def test_render_set_env_vars_provider_error_is_safe():
    def handler(request):
        return httpx.Response(500, json={"message": "bad secret value"})

    with _render_client(handler) as client:
        result = render_set_env_vars(
            service_id="srv-123",
            variables={"JWT_SECRET": "super-secret"},
            approval="APPROVED",
            ci_gate=CI_GATE,
            api_key="render_secret_token_123",
            client=client,
        )

    assert result["ok"] is False
    assert result["updated"] is False
    assert result["errors"] == ["Render API returned status 500"]
    assert "super-secret" not in str(result)
    assert "bad secret value" not in str(result)


def test_railway_set_env_vars_success_never_returns_values():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["variables"]["input"]["projectId"] == "proj-123"
        assert body["variables"]["input"]["environmentId"] == "env-123"
        assert body["variables"]["input"]["serviceId"] == "srv-123"
        assert body["variables"]["input"]["name"] in {"DATABASE_URL", "JWT_SECRET"}
        assert "value" in body["variables"]["input"]
        return httpx.Response(200, json={"data": {"variableUpsert": True}})

    with _railway_client(handler) as client:
        result = railway_set_env_vars(
            project_id="proj-123",
            service_id="srv-123",
            environment_id="env-123",
            variables={"DATABASE_URL": "postgres://secret", "JWT_SECRET": "super-secret"},
            approval="APPROVED",
            ci_gate=CI_GATE,
            token="railway_secret_token_123",
            client=client,
        )

    assert len(requests) == 2
    assert result["ok"] is True
    assert result["updated"] is True
    assert result["project_id"] == "proj-123"
    assert result["environment_id"] == "env-123"
    assert result["variable_names"] == ["DATABASE_URL", "JWT_SECRET"]
    assert "super-secret" not in str(result)
    assert "postgres://secret" not in str(result)
    assert "railway_secret_token" not in str(result)


def test_railway_set_env_vars_blocks_failing_ci_gate():
    failing_gate = {
        "allowed": False,
        "blocking_checks": ["tests failed"],
        "summary": "tests failed",
    }

    result = railway_set_env_vars(
        project_id="proj-123",
        service_id="srv-123",
        environment_id="env-123",
        variables={"JWT_SECRET": "super-secret"},
        approval="APPROVED",
        ci_gate=failing_gate,
        token="railway_secret_token_123",
    )

    assert result["ok"] is False
    assert result["updated"] is False
    assert result["errors"] == ["CI gate blocked: tests failed"]
    assert result["variable_names"] == ["JWT_SECRET"]
    assert "super-secret" not in str(result)


def test_railway_set_env_vars_graphql_error_is_safe():
    def handler(request):
        return httpx.Response(200, json={"errors": [{"message": "secret leaked"}]})

    with _railway_client(handler) as client:
        result = railway_set_env_vars(
            project_id="proj-123",
            service_id="srv-123",
            environment_id="env-123",
            variables={"JWT_SECRET": "super-secret"},
            approval="APPROVED",
            ci_gate=CI_GATE,
            token="railway_secret_token_123",
            client=client,
        )

    assert result["ok"] is False
    assert result["updated"] is False
    assert result["errors"] == ["Railway GraphQL returned errors"]
    assert "super-secret" not in str(result)
    assert "secret leaked" not in str(result)
