"""Tests for Redis-backed OAuth auth code store.

No real Redis instance required — the Redis client is fully mocked.
Access tokens are now stateless HMAC-signed (no Redis token store needed).
"""

import base64
import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

from deploy_orchestrator_mcp.oauth import (
    OAuthError,
    RedisAuthCodeStore,
    _REDIS_CODE_PREFIX,
    exchange_code,
    reset_stores,
    validate_oauth_token,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_client():
    """Return a MagicMock that mimics the redis.Redis interface."""
    return MagicMock()


def _pkce_pair():
    verifier = base64.urlsafe_b64encode(b"y" * 32).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    """Isolate module-level store singletons for every test."""
    reset_stores()
    yield
    reset_stores()


@pytest.fixture()
def oauth_env(monkeypatch):
    monkeypatch.setenv("OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URIS", "https://chatgpt.com/aip/callback")
    monkeypatch.setenv("OAUTH_SCOPES", "mcp")
    monkeypatch.setenv("OAUTH_TOKEN_TTL_SECONDS", "3600")
    monkeypatch.setenv("MCP_OAUTH_SIGNING_KEY", "test-signing-key-0000000000000000")
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)


# ---------------------------------------------------------------------------
# RedisAuthCodeStore unit tests
# ---------------------------------------------------------------------------


def test_redis_code_store_issue_sets_key_with_ttl():
    r = _make_redis_client()
    store = RedisAuthCodeStore(r, ttl=600)
    code = store.issue(
        client_id="cid",
        redirect_uri="https://chatgpt.com/aip/callback",
        scope="mcp",
    )
    assert len(code) > 20
    r.set.assert_called_once()
    call_kwargs = r.set.call_args
    assert call_kwargs.kwargs.get("ex") == 600 or (len(call_kwargs.args) > 2 and call_kwargs.args[2] == 600)


def test_redis_code_store_consume_happy_path():
    r = _make_redis_client()
    store = RedisAuthCodeStore(r, ttl=600)

    payload = json.dumps({
        "client_id": "cid",
        "redirect_uri": "https://chatgpt.com/aip/callback",
        "scope": "mcp",
        "code_challenge": None,
        "code_challenge_method": None,
    })
    r.getdel.return_value = payload

    entry = store.consume("some-code")
    assert entry is not None
    assert entry.client_id == "cid"
    assert entry.scope == "mcp"
    r.getdel.assert_called_once_with(f"{_REDIS_CODE_PREFIX}some-code")


def test_redis_code_store_consume_returns_none_when_missing():
    r = _make_redis_client()
    r.getdel.return_value = None
    store = RedisAuthCodeStore(r, ttl=600)
    assert store.consume("nonexistent") is None


def test_redis_code_store_single_use_via_getdel():
    """getdel atomically removes the key — second consume returns None."""
    r = _make_redis_client()
    payload = json.dumps({
        "client_id": "cid",
        "redirect_uri": "https://chatgpt.com/aip/callback",
        "scope": "mcp",
        "code_challenge": None,
        "code_challenge_method": None,
    })
    r.getdel.side_effect = [payload, None]
    store = RedisAuthCodeStore(r, ttl=600)

    assert store.consume("code") is not None
    assert store.consume("code") is None


def test_redis_code_store_preserves_pkce_fields():
    r = _make_redis_client()
    store = RedisAuthCodeStore(r, ttl=600)
    store.issue(
        client_id="cid",
        redirect_uri="https://chatgpt.com/aip/callback",
        scope="mcp",
        code_challenge="abc123",
        code_challenge_method="S256",
    )
    raw_payload = r.set.call_args.args[1]
    data = json.loads(raw_payload)
    assert data["code_challenge"] == "abc123"
    assert data["code_challenge_method"] == "S256"


# ---------------------------------------------------------------------------
# Factory: get_auth_code_store with REDIS_URL
# ---------------------------------------------------------------------------


def test_factory_uses_redis_when_redis_url_set(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    mock_client = _make_redis_client()

    with patch("deploy_orchestrator_mcp.oauth.redis") as mock_redis_mod:
        mock_redis_mod.from_url.return_value = mock_client
        mock_client.ping.return_value = True

        from deploy_orchestrator_mcp.oauth import get_auth_code_store

        code_store = get_auth_code_store()

    assert isinstance(code_store, RedisAuthCodeStore)


def test_factory_uses_memory_when_no_redis_url(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    from deploy_orchestrator_mcp.oauth import AuthCodeStore, get_auth_code_store

    assert isinstance(get_auth_code_store(), AuthCodeStore)


def test_factory_raises_on_redis_connection_failure(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://unreachable:6379/0")
    import redis as redis_lib

    with patch("deploy_orchestrator_mcp.oauth.redis") as mock_redis_mod:
        mock_client = _make_redis_client()
        mock_redis_mod.from_url.return_value = mock_client
        mock_client.ping.side_effect = redis_lib.ConnectionError("refused")

        from deploy_orchestrator_mcp.oauth import get_auth_code_store

        with pytest.raises(redis_lib.ConnectionError):
            get_auth_code_store()


# ---------------------------------------------------------------------------
# End-to-end OAuth flow with mocked Redis code store + stateless tokens
# ---------------------------------------------------------------------------


def test_full_oauth_flow_with_redis_store(oauth_env, monkeypatch):
    """authorize() + exchange_code() work correctly with Redis-backed code store."""
    r = _make_redis_client()
    code_store = RedisAuthCodeStore(r, ttl=600)

    import deploy_orchestrator_mcp.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "_auth_code_store", code_store)

    from deploy_orchestrator_mcp.oauth import authorize

    result = authorize(
        client_id="test-client-id",
        redirect_uri="https://chatgpt.com/aip/callback",
        response_type="code",
        scope="mcp",
    )
    code = result["code"]

    payload = json.dumps({
        "client_id": "test-client-id",
        "redirect_uri": "https://chatgpt.com/aip/callback",
        "scope": "mcp",
        "code_challenge": None,
        "code_challenge_method": None,
    })
    r.getdel.return_value = payload

    token_resp = exchange_code(
        grant_type="authorization_code",
        code=code,
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="https://chatgpt.com/aip/callback",
    )
    assert "access_token" in token_resp
    assert token_resp["token_type"] == "Bearer"
    assert token_resp["access_token"].startswith("mcp.")

    # Stateless token validated locally — no Redis call needed
    assert validate_oauth_token(token_resp["access_token"]) is True


def test_pkce_flow_with_redis_store(oauth_env, monkeypatch):
    r = _make_redis_client()
    verifier, challenge = _pkce_pair()

    code_store = RedisAuthCodeStore(r, ttl=600)

    import deploy_orchestrator_mcp.oauth as oauth_mod

    monkeypatch.setattr(oauth_mod, "_auth_code_store", code_store)

    from deploy_orchestrator_mcp.oauth import authorize

    authorize(
        client_id="test-client-id",
        redirect_uri="https://chatgpt.com/aip/callback",
        response_type="code",
        scope="mcp",
        code_challenge=challenge,
        code_challenge_method="S256",
    )

    payload = json.dumps({
        "client_id": "test-client-id",
        "redirect_uri": "https://chatgpt.com/aip/callback",
        "scope": "mcp",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    r.getdel.return_value = payload

    token_resp = exchange_code(
        grant_type="authorization_code",
        code="any-code",
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="https://chatgpt.com/aip/callback",
        code_verifier=verifier,
    )
    assert "access_token" in token_resp
    assert validate_oauth_token(token_resp["access_token"]) is True
