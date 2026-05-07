"""Tests for render_get_build_logs and render_get_runtime_logs."""

import httpx
import pytest

from deploy_orchestrator_mcp.render_api import render_get_build_logs, render_get_runtime_logs


def _mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="https://api.render.com/v1", transport=transport)


# ---------------------------------------------------------------------------
# render_get_build_logs
# ---------------------------------------------------------------------------


def test_build_logs_missing_api_key(monkeypatch):
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    result = render_get_build_logs(deploy_id="dep-123")
    assert "errors" in result


def test_build_logs_happy_path(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        assert request.url.path == "/v1/deploys/dep-123/logs"
        assert request.url.params.get("limit") == "100"
        return httpx.Response(200, json=[
            {"timestamp": "2026-05-07T10:00:00Z", "message": "Building..."},
            {"timestamp": "2026-05-07T10:00:05Z", "message": "Build complete"},
        ])

    with _mock_client(handler) as client:
        result = render_get_build_logs(deploy_id="dep-123", client=client)

    assert result["deploy_id"] == "dep-123"
    assert len(result["lines"]) == 2
    assert result["lines"][0]["message"] == "Building..."
    assert result["truncated"] is False
    assert "audit_event" in result


def test_build_logs_truncated_when_at_tail_limit(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        return httpx.Response(200, json=[
            {"timestamp": f"2026-05-07T10:00:0{i}Z", "message": f"line {i}"}
            for i in range(3)
        ])

    with _mock_client(handler) as client:
        result = render_get_build_logs(deploy_id="dep-123", tail=3, client=client)

    assert result["truncated"] is True


def test_build_logs_tail_capped_at_500(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    captured_params = {}

    def handler(request):
        captured_params["limit"] = request.url.params.get("limit")
        return httpx.Response(200, json=[])

    with _mock_client(handler) as client:
        render_get_build_logs(deploy_id="dep-123", tail=9999, client=client)

    assert int(captured_params["limit"]) <= 500


def test_build_logs_404(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        return httpx.Response(404, json={"message": "deploy not found"})

    with _mock_client(handler) as client:
        result = render_get_build_logs(deploy_id="bad-dep", client=client)

    assert result["lines"] == []
    assert "errors" in result


def test_build_logs_logs_key_format(monkeypatch):
    """Support API returning {logs: [...]} instead of a bare list."""
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        return httpx.Response(200, json={"logs": [
            {"timestamp": "2026-05-07T10:00:00Z", "message": "Hello"},
        ]})

    with _mock_client(handler) as client:
        result = render_get_build_logs(deploy_id="dep-123", client=client)

    assert len(result["lines"]) == 1
    assert result["lines"][0]["message"] == "Hello"


# ---------------------------------------------------------------------------
# render_get_runtime_logs
# ---------------------------------------------------------------------------


def test_runtime_logs_missing_api_key(monkeypatch):
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    result = render_get_runtime_logs(service_id="srv-123")
    assert "errors" in result


def test_runtime_logs_happy_path(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        assert request.url.path == "/v1/services/srv-123/logs"
        assert request.url.params.get("limit") == "100"
        return httpx.Response(200, json=[
            {"timestamp": "2026-05-07T10:01:00Z", "message": "Server started"},
            {"timestamp": "2026-05-07T10:01:01Z", "message": "Listening on :8000"},
        ])

    with _mock_client(handler) as client:
        result = render_get_runtime_logs(service_id="srv-123", client=client)

    assert result["service_id"] == "srv-123"
    assert len(result["lines"]) == 2
    assert result["lines"][1]["message"] == "Listening on :8000"
    assert result["truncated"] is False
    assert "audit_event" in result


def test_runtime_logs_tail_capped_at_500(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    captured_params = {}

    def handler(request):
        captured_params["limit"] = request.url.params.get("limit")
        return httpx.Response(200, json=[])

    with _mock_client(handler) as client:
        render_get_runtime_logs(service_id="srv-123", tail=9999, client=client)

    assert int(captured_params["limit"]) <= 500


def test_runtime_logs_404(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        return httpx.Response(404, json={"message": "service not found"})

    with _mock_client(handler) as client:
        result = render_get_runtime_logs(service_id="bad-srv", client=client)

    assert result["lines"] == []
    assert "errors" in result
