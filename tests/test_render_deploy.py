import httpx

from deploy_orchestrator_mcp.render_deploy import (
    fetch_logs,
    poll_deploy_status,
    run_healthcheck,
    trigger_deploy,
)


def _client(handler):
    return httpx.Client(
        base_url="https://api.render.com/v1",
        transport=httpx.MockTransport(handler),
    )


def test_trigger_deploy_success():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/services/srv-123/deploys"
        return httpx.Response(201, json={"id": "dep-123", "status": "build_in_progress"})

    with _client(handler) as client:
        result = trigger_deploy(
            {"service_id": "srv-123"},
            {"api_key": "render_test_secret_token_1234567890"},
            client=client,
        )

    assert result["triggered"] is True
    assert result["deploy_id"] == "dep-123"
    assert result["status"] == "build_in_progress"
    assert "render_test_secret_token" not in str(result)


def test_trigger_deploy_api_failure():
    def handler(request):
        return httpx.Response(500, json={"message": "boom"})

    with _client(handler) as client:
        result = trigger_deploy(
            {"service_id": "srv-123"},
            {"api_key": "render_test_secret_token_1234567890"},
            client=client,
        )

    assert result["triggered"] is False
    assert result["deploy_id"] is None
    assert result["errors"]


def test_poll_deploy_status_success():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1/services/srv-123/deploys/dep-123"
        return httpx.Response(200, json={"id": "dep-123", "status": "live"})

    with _client(handler) as client:
        result = poll_deploy_status(
            "dep-123",
            {"api_key": "render_test_secret_token_1234567890"},
            service_id="srv-123",
            timeout_s=0,
            client=client,
        )

    assert result["ok"] is True
    assert result["deploy_id"] == "dep-123"
    assert result["status"] == "live"
    assert result["complete"] is True


def test_fetch_logs_success():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1/deploys/dep-123/logs"
        assert request.url.params["limit"] == "2"
        return httpx.Response(
            200,
            json=[
                {"timestamp": "2026-05-24T00:00:00Z", "message": "Building"},
                {"timestamp": "2026-05-24T00:00:01Z", "message": "Done"},
            ],
        )

    with _client(handler) as client:
        result = fetch_logs(
            "dep-123",
            {"api_key": "render_test_secret_token_1234567890"},
            tail=2,
            client=client,
        )

    assert result["deploy_id"] == "dep-123"
    assert len(result["lines"]) == 2
    assert result["truncated"] is True


def test_run_healthcheck_ok():
    def handler(request):
        assert str(request.url) == "https://app.example.com/healthz"
        return httpx.Response(200)

    with _client(handler) as client:
        result = run_healthcheck("https://app.example.com/healthz", client=client)

    assert result["healthy"] is True
    assert result["status_code"] == 200
    assert result["attempts"] == 1


def test_run_healthcheck_timeout_after_retries():
    attempts = {"count": 0}

    def handler(request):
        attempts["count"] += 1
        raise httpx.ReadTimeout("timed out")

    with _client(handler) as client:
        result = run_healthcheck(
            "https://app.example.com/healthz",
            retries=2,
            client=client,
        )

    assert attempts["count"] == 2
    assert result["healthy"] is False
    assert result["status_code"] is None
    assert result["errors"]
