import httpx

from deploy_orchestrator_mcp.render_api import render_rollback_staging
from deploy_orchestrator_mcp.render_deploy import rollback_deploy


def _client(handler):
    return httpx.Client(
        base_url="https://api.render.com/v1",
        transport=httpx.MockTransport(handler),
    )


def test_rollback_deploy_success():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/services/srv-123/rollback"
        assert request.json() == {"deployId": "dep-old"}
        return httpx.Response(200, json={"id": "dep-new", "status": "build_in_progress"})

    with _client(handler) as client:
        result = rollback_deploy(
            "srv-123",
            "dep-old",
            {"api_key": "render_test_secret_token_1234567890"},
            client=client,
        )

    assert result["rolled_back"] is True
    assert result["service_id"] == "srv-123"
    assert result["target_deploy_id"] == "dep-old"
    assert result["rollback_deploy_id"] == "dep-new"
    assert result["status"] == "build_in_progress"
    assert "render_test_secret_token" not in str(result)


def test_rollback_deploy_api_failure():
    def handler(request):
        return httpx.Response(404, json={"message": "deploy not found"})

    with _client(handler) as client:
        result = rollback_deploy(
            "srv-123",
            "dep-missing",
            {"api_key": "render_test_secret_token_1234567890"},
            client=client,
        )

    assert result["rolled_back"] is False
    assert result["service_id"] == "srv-123"
    assert result["target_deploy_id"] == "dep-missing"
    assert result["errors"]


def test_render_rollback_staging_requires_approval():
    result = render_rollback_staging(
        service_id="srv-123",
        target_deploy_id="dep-old",
        approval=None,
        confirm="CONFIRM_DESTRUCTIVE_OPERATION",
        api_key="render_test_secret_token_1234567890",
    )

    assert result["allowed"] is False
    assert result["rolled_back"] is False
    assert "approval" in result["missing_fields"]


def test_render_rollback_staging_requires_confirm():
    result = render_rollback_staging(
        service_id="srv-123",
        target_deploy_id="dep-old",
        approval="APPROVED",
        confirm=None,
        api_key="render_test_secret_token_1234567890",
    )

    assert result["allowed"] is False
    assert result["rolled_back"] is False
    assert "confirm" in result["missing_fields"]


def test_render_rollback_staging_delegates_after_gates():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/services/srv-123/rollback"
        assert request.json() == {"deployId": "dep-old"}
        return httpx.Response(200, json={"id": "dep-new", "status": "build_in_progress"})

    with _client(handler) as client:
        result = render_rollback_staging(
            service_id="srv-123",
            target_deploy_id="dep-old",
            approval="APPROVED",
            confirm="CONFIRM_DESTRUCTIVE_OPERATION",
            api_key="render_test_secret_token_1234567890",
            client=client,
        )

    assert result["rolled_back"] is True
    assert result["rollback_deploy_id"] == "dep-new"
