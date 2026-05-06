import pytest

from deploy_orchestrator_mcp.auth import auth_status, is_auth_enabled, validate_bearer_token


def test_auth_disabled_when_no_key(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)
    assert is_auth_enabled() is False


def test_auth_enabled_when_key_set(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "secret123")
    assert is_auth_enabled() is True


def test_validate_returns_true_when_auth_disabled(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)
    assert validate_bearer_token("anything") is True


def test_validate_correct_token(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "correct_key")
    assert validate_bearer_token("correct_key") is True


def test_validate_wrong_token(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "correct_key")
    assert validate_bearer_token("wrong_key") is False


def test_validate_strips_whitespace(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "correct_key")
    assert validate_bearer_token("  correct_key  ") is True


def test_auth_status_disabled(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)
    status = auth_status()
    assert status["auth_enabled"] is False
    assert status["method"] == "none"


def test_auth_status_enabled(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "somekey")
    status = auth_status()
    assert status["auth_enabled"] is True
    assert status["method"] == "bearer_api_key"
