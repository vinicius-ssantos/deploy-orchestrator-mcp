from deploy_orchestrator_mcp.auth import (
    auth_status,
    is_auth_enabled,
    validate_any_token,
    validate_bearer_token,
)


def test_auth_disabled_when_no_key(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    assert is_auth_enabled() is False


def test_auth_enabled_when_key_set(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "secret123")
    assert is_auth_enabled() is True


def test_validate_bearer_returns_false_when_no_key(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)
    assert validate_bearer_token("anything") is False


def test_validate_correct_token(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "correct_key")
    assert validate_bearer_token("correct_key") is True


def test_validate_wrong_token(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "correct_key")
    assert validate_bearer_token("wrong_key") is False


def test_validate_strips_whitespace(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "correct_key")
    assert validate_bearer_token("  correct_key  ") is True


def test_validate_any_token_passthrough_when_no_auth(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    assert validate_any_token("random") is True


def test_validate_any_token_accepts_bearer(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "mykey")
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    assert validate_any_token("mykey") is True


def test_validate_any_token_rejects_wrong_bearer(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "mykey")
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    assert validate_any_token("wrongkey") is False


def test_auth_status_disabled(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    status = auth_status()
    assert status["auth_enabled"] is False
    assert status["method"] == "none"
    assert status["bearer_api_key_enabled"] is False
    assert status["oauth_enabled"] is False


def test_auth_status_bearer_only(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "somekey")
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    status = auth_status()
    assert status["auth_enabled"] is True
    assert status["method"] == "bearer_api_key"
    assert status["bearer_api_key_enabled"] is True
    assert status["oauth_enabled"] is False


def test_auth_status_oauth_only(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)
    monkeypatch.setenv("OAUTH_CLIENT_ID", "chatgpt-app")
    status = auth_status()
    assert status["auth_enabled"] is True
    assert status["method"] == "oauth"
    assert status["bearer_api_key_enabled"] is False
    assert status["oauth_enabled"] is True


def test_auth_status_both_enabled(monkeypatch):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "somekey")
    monkeypatch.setenv("OAUTH_CLIENT_ID", "chatgpt-app")
    status = auth_status()
    assert status["method"] == "bearer_api_key+oauth"
