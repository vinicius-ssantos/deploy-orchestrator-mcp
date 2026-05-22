import httpx

from deploy_orchestrator_mcp.render_api import (
    render_deploy_staging,
    render_get_deploy_status,
    render_healthcheck,
    render_list_services,
    render_validate_credentials,
)


def _client(handler):
    return httpx.Client(
        base_url="https://api.render.com/v1",
        transport=httpx.MockTransport(handler),
    )


def test_render_validate_credentials_uses_owners_endpoint(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1/owners"
        assert request.headers["authorization"].startswith("Bearer ")
        return httpx.Response(200, json=[{"owner": {"name": "Vinicius"}}])

    with _client(handler) as client:
        result = render_validate_credentials(client=client)

    assert result["valid"] is True
    assert result["owner"] == "Vinicius"
    assert "render_test_secret_token" not in str(result)
    assert result["audit_event"]["metadata"]["operation"] == "validate_credentials"


def test_render_list_services_returns_normalized_services(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1/services"
        assert request.url.params["limit"] == "2"
        return httpx.Response(
            200,
            json={
                "nextCursor": "cursor-2",
                "services": [
                    {
                        "service": {
                            "id": "srv-123",
                            "name": "api-staging",
                            "type": "web_service",
                            "serviceDetails": {"url": "https://api-staging.onrender.com"},
                        }
                    }
                ],
            },
        )

    with _client(handler) as client:
        result = render_list_services(limit=2, client=client)

    assert result["ok"] is True
    assert result["next_cursor"] == "cursor-2"
    assert result["services"] == [
        {
            "id": "srv-123",
            "name": "api-staging",
            "type": "web_service",
            "service_type": None,
            "repo": None,
            "branch": None,
            "url": "https://api-staging.onrender.com",
        }
    ]


def test_render_deploy_staging_blocks_without_approval(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")
    called = False

    def handler(request):
        nonlocal called
        called = True
        return httpx.Response(500, json={"unexpected": True})

    with _client(handler) as client:
        result = render_deploy_staging(service_id="srv-123", client=client)

    assert result["triggered"] is False
    assert result["deploy_id"] is None
    assert result["gate"]["allowed"] is False
    assert called is False


def test_render_deploy_staging_triggers_when_approved(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/services/srv-123/deploys"
        return httpx.Response(201, json={"id": "dep-123", "status": "build_in_progress"})

    with _client(handler) as client:
        result = render_deploy_staging(
            service_id="srv-123",
            approval="APPROVED",
            client=client,
            ci_gate={"allowed": True, "blocking_checks": [], "summary": "All workflows succeeded", "head_sha": "abc123"},
        )

    assert result["triggered"] is True
    assert result["deploy_id"] == "dep-123"
    assert result["status"] == "build_in_progress"
    assert result["gate"]["allowed"] is True


def test_render_get_deploy_status_reads_specific_deploy(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1/services/srv-123/deploys/dep-123"
        return httpx.Response(200, json={"id": "dep-123", "status": "live"})

    with _client(handler) as client:
        result = render_get_deploy_status(
            service_id="srv-123",
            deploy_id="dep-123",
            client=client,
        )

    assert result["ok"] is True
    assert result["deploy_id"] == "dep-123"
    assert result["status"] == "live"
    assert result["complete"] is True


def test_render_healthcheck_returns_healthy():
    def handler(request):
        assert str(request.url) == "https://api-staging.onrender.com/health"
        return httpx.Response(200)

    with _client(handler) as client:
        result = render_healthcheck(
            url="https://api-staging.onrender.com/health",
            client=client,
        )

    assert result["healthy"] is True
    assert result["status_code"] == 200


def test_render_healthcheck_blocks_invalid_url():
    result = render_healthcheck(url="ftp://example.com")

    assert result["healthy"] is False
    assert result["status_code"] is None
    assert result["errors"]
