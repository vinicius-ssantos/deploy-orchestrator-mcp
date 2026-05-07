"""Tests for render_rollback_staging."""

import httpx
import pytest

from deploy_orchestrator_mcp.render_api import CONFIRM_DESTRUCTIVE, render_rollback_staging


def _mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="https://api.render.com/v1", transport=transport)


# ---------------------------------------------------------------------------
# Gate enforcement
# ---------------------------------------------------------------------------


def test_rollback_blocked_without_approval(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")
    result = render_rollback_staging(
        service_id="srv-123",
        target_deploy_id="dep-old",
        confirm=CONFIRM_DESTRUCTIVE,
    )
    assert result["rolled_back"] is False
    assert any("approval" in e for e in result["errors"])


def test_rollback_blocked_without_confirm(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")
    result = render_rollback_staging(
        service_id="srv-123",
        target_deploy_id="dep-old",
        approval="APPROVED",
    )
    assert result["rolled_back"] is False
    assert any("CONFIRM_DESTRUCTIVE_OPERATION" in e for e in result["errors"])


def test_rollback_blocked_with_wrong_confirm(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")
    result = render_rollback_staging(
        service_id="srv-123",
        target_deploy_id="dep-old",
        approval="APPROVED",
        confirm="yes please",
    )
    assert result["rolled_back"] is False
    assert any("CONFIRM_DESTRUCTIVE_OPERATION" in e for e in result["errors"])


def test_rollback_blocked_missing_api_key(monkeypatch):
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    result = render_rollback_staging(
        service_id="srv-123",
        target_deploy_id="dep-old",
        approval="APPROVED",
        confirm=CONFIRM_DESTRUCTIVE,
    )
    assert "errors" in result


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_rollback_triggers_correct_endpoint(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/v1/services/srv-123/rollback"
        import json as _json
        assert _json.loads(request.content)["deployId"] == "dep-old"
        return httpx.Response(201, json={
            "id": "dep-new",
            "status": "build_in_progress",
        })

    with _mock_client(handler) as client:
        result = render_rollback_staging(
            service_id="srv-123",
            target_deploy_id="dep-old",
            approval="APPROVED",
            confirm=CONFIRM_DESTRUCTIVE,
            client=client,
        )

    assert result["rolled_back"] is True
    assert result["rollback_deploy_id"] == "dep-new"
    assert result["status"] == "build_in_progress"
    assert result["service_id"] == "srv-123"
    assert result["target_deploy_id"] == "dep-old"
    assert "audit_event" in result
    assert "next_steps" in result


def test_rollback_api_error_propagated(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        return httpx.Response(404, json={"message": "deploy not found"})

    with _mock_client(handler) as client:
        result = render_rollback_staging(
            service_id="srv-123",
            target_deploy_id="bad-dep",
            approval="APPROVED",
            confirm=CONFIRM_DESTRUCTIVE,
            client=client,
        )

    assert result["rolled_back"] is False
    assert "errors" in result


def test_rollback_audit_event_type_on_block(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")
    result = render_rollback_staging(
        service_id="srv-123",
        target_deploy_id="dep-old",
    )
    assert result["audit_event"]["type"] == "render.rollback.blocked"


def test_rollback_next_steps_reference_deploy_id(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "render_test_secret_token_1234567890")

    def handler(request):
        return httpx.Response(201, json={"id": "dep-rollback", "status": "build_in_progress"})

    with _mock_client(handler) as client:
        result = render_rollback_staging(
            service_id="srv-123",
            target_deploy_id="dep-old",
            approval="APPROVED",
            confirm=CONFIRM_DESTRUCTIVE,
            client=client,
        )

    assert any("render_get_deploy_status" in step for step in result["next_steps"])
    assert any("render_healthcheck" in step for step in result["next_steps"])
