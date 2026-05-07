"""Tests for OAuth 2.0 Authorization Code flow (oauth.py + server routes)."""

import base64
import hashlib
import time

import pytest
from starlette.testclient import TestClient

from deploy_orchestrator_mcp.oauth import (
    AuthCodeStore,
    OAuthError,
    authorize,
    discovery_document,
    exchange_code,
    is_oauth_enabled,
    sign_access_token,
    validate_oauth_token,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def oauth_env(monkeypatch):
    monkeypatch.setenv("OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OAUTH_REDIRECT_URIS", "https://chatgpt.com/aip/callback,https://example.com/cb")
    monkeypatch.setenv("OAUTH_SCOPES", "mcp")
    monkeypatch.setenv("OAUTH_TOKEN_TTL_SECONDS", "3600")
    monkeypatch.setenv("MCP_OAUTH_SIGNING_KEY", "test-signing-key-0000000000000000")
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)


@pytest.fixture()
def fresh_stores(monkeypatch):
    """Replace module-level singletons with fresh instances for test isolation."""
    from deploy_orchestrator_mcp import oauth as oauth_mod

    code_store = AuthCodeStore(ttl=600)
    monkeypatch.setattr(oauth_mod, "_auth_code_store", code_store)
    return code_store


@pytest.fixture()
def http_client(oauth_env, fresh_stores):
    from deploy_orchestrator_mcp.server import _make_asgi_app

    app = _make_asgi_app()
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# is_oauth_enabled
# ---------------------------------------------------------------------------


def test_oauth_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    assert is_oauth_enabled() is False


def test_oauth_enabled_when_client_id_set(monkeypatch):
    monkeypatch.setenv("OAUTH_CLIENT_ID", "some-client")
    assert is_oauth_enabled() is True


# ---------------------------------------------------------------------------
# discovery_document
# ---------------------------------------------------------------------------


def test_discovery_document_structure():
    doc = discovery_document("https://deploy-orchestrator-mcp.onrender.com")
    assert doc["issuer"] == "https://deploy-orchestrator-mcp.onrender.com"
    assert "/oauth/authorize" in doc["authorization_endpoint"]
    assert "/oauth/token" in doc["token_endpoint"]
    assert "code" in doc["response_types_supported"]
    assert "S256" in doc["code_challenge_methods_supported"]


def test_discovery_endpoint_when_disabled(monkeypatch):
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("MCP_SERVER_API_KEY", raising=False)
    from deploy_orchestrator_mcp.server import _make_asgi_app

    client = TestClient(_make_asgi_app(), raise_server_exceptions=True)
    resp = client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 404


def test_discovery_endpoint_when_enabled(http_client):
    resp = http_client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    doc = resp.json()
    assert "authorization_endpoint" in doc
    assert "token_endpoint" in doc


# ---------------------------------------------------------------------------
# authorize()
# ---------------------------------------------------------------------------


def test_authorize_happy_path(oauth_env, fresh_stores):
    result = authorize(
        client_id="test-client-id",
        redirect_uri="https://chatgpt.com/aip/callback",
        response_type="code",
        scope="mcp",
        state="xyz",
    )
    assert "code" in result
    assert result["state"] == "xyz"
    assert len(result["code"]) > 20


def test_authorize_missing_redirect_uri(oauth_env, fresh_stores):
    with pytest.raises(OAuthError) as exc_info:
        authorize(
            client_id="test-client-id",
            redirect_uri="https://attacker.com/steal",
            response_type="code",
        )
    assert exc_info.value.error == "invalid_request"


def test_authorize_unknown_client(oauth_env, fresh_stores):
    with pytest.raises(OAuthError) as exc_info:
        authorize(
            client_id="unknown-client",
            redirect_uri="https://chatgpt.com/aip/callback",
            response_type="code",
        )
    assert exc_info.value.error == "invalid_client"


def test_authorize_wrong_response_type(oauth_env, fresh_stores):
    with pytest.raises(OAuthError) as exc_info:
        authorize(
            client_id="test-client-id",
            redirect_uri="https://chatgpt.com/aip/callback",
            response_type="token",
        )
    assert exc_info.value.error == "unsupported_response_type"


def test_authorize_unsupported_pkce_method(oauth_env, fresh_stores):
    with pytest.raises(OAuthError) as exc_info:
        authorize(
            client_id="test-client-id",
            redirect_uri="https://chatgpt.com/aip/callback",
            response_type="code",
            code_challenge="abc123",
            code_challenge_method="RS256",
        )
    assert exc_info.value.error == "invalid_request"


# ---------------------------------------------------------------------------
# exchange_code()
# ---------------------------------------------------------------------------


def _make_code(oauth_env, fresh_stores, pkce_challenge=None, pkce_method=None):
    result = authorize(
        client_id="test-client-id",
        redirect_uri="https://chatgpt.com/aip/callback",
        response_type="code",
        scope="mcp",
        code_challenge=pkce_challenge,
        code_challenge_method=pkce_method,
    )
    return result["code"]


def test_exchange_happy_path(oauth_env, fresh_stores):
    code = _make_code(oauth_env, fresh_stores)
    resp = exchange_code(
        grant_type="authorization_code",
        code=code,
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="https://chatgpt.com/aip/callback",
    )
    assert resp["token_type"] == "Bearer"
    assert "access_token" in resp
    assert resp["access_token"].startswith("mcp.")
    assert resp["expires_in"] == 3600
    assert resp["scope"] == "mcp"


def test_exchange_invalid_code(oauth_env, fresh_stores):
    with pytest.raises(OAuthError) as exc_info:
        exchange_code(
            grant_type="authorization_code",
            code="bogus-code",
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://chatgpt.com/aip/callback",
        )
    assert exc_info.value.error == "invalid_grant"


def test_exchange_code_reuse_rejected(oauth_env, fresh_stores):
    code = _make_code(oauth_env, fresh_stores)
    exchange_code(
        grant_type="authorization_code",
        code=code,
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="https://chatgpt.com/aip/callback",
    )
    with pytest.raises(OAuthError) as exc_info:
        exchange_code(
            grant_type="authorization_code",
            code=code,
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://chatgpt.com/aip/callback",
        )
    assert exc_info.value.error == "invalid_grant"


def test_exchange_expired_code(oauth_env, fresh_stores, monkeypatch):
    code_store = fresh_stores
    code = code_store.issue(
        client_id="test-client-id",
        redirect_uri="https://chatgpt.com/aip/callback",
        scope="mcp",
    )
    code_store._store[code].expires_at = time.monotonic() - 1

    with pytest.raises(OAuthError) as exc_info:
        exchange_code(
            grant_type="authorization_code",
            code=code,
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://chatgpt.com/aip/callback",
        )
    assert exc_info.value.error == "invalid_grant"


def test_exchange_wrong_secret(oauth_env, fresh_stores):
    code = _make_code(oauth_env, fresh_stores)
    with pytest.raises(OAuthError) as exc_info:
        exchange_code(
            grant_type="authorization_code",
            code=code,
            client_id="test-client-id",
            client_secret="wrong-secret",
            redirect_uri="https://chatgpt.com/aip/callback",
        )
    assert exc_info.value.error == "invalid_client"


def test_exchange_redirect_uri_mismatch(oauth_env, fresh_stores):
    code = _make_code(oauth_env, fresh_stores)
    with pytest.raises(OAuthError) as exc_info:
        exchange_code(
            grant_type="authorization_code",
            code=code,
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://example.com/cb",
        )
    assert exc_info.value.error == "invalid_grant"


def test_exchange_unsupported_grant_type(oauth_env, fresh_stores):
    with pytest.raises(OAuthError) as exc_info:
        exchange_code(
            grant_type="client_credentials",
            code="x",
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://chatgpt.com/aip/callback",
        )
    assert exc_info.value.error == "unsupported_grant_type"


# ---------------------------------------------------------------------------
# PKCE S256
# ---------------------------------------------------------------------------


def _pkce_pair():
    verifier = base64.urlsafe_b64encode(b"x" * 32).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def test_pkce_s256_happy_path(oauth_env, fresh_stores):
    verifier, challenge = _pkce_pair()
    code = _make_code(oauth_env, fresh_stores, pkce_challenge=challenge, pkce_method="S256")
    resp = exchange_code(
        grant_type="authorization_code",
        code=code,
        client_id="test-client-id",
        client_secret="test-client-secret",
        redirect_uri="https://chatgpt.com/aip/callback",
        code_verifier=verifier,
    )
    assert "access_token" in resp


def test_pkce_s256_wrong_verifier(oauth_env, fresh_stores):
    _, challenge = _pkce_pair()
    code = _make_code(oauth_env, fresh_stores, pkce_challenge=challenge, pkce_method="S256")
    with pytest.raises(OAuthError) as exc_info:
        exchange_code(
            grant_type="authorization_code",
            code=code,
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://chatgpt.com/aip/callback",
            code_verifier="wrong-verifier",
        )
    assert exc_info.value.error == "invalid_grant"


def test_pkce_verifier_required_when_challenge_set(oauth_env, fresh_stores):
    _, challenge = _pkce_pair()
    code = _make_code(oauth_env, fresh_stores, pkce_challenge=challenge, pkce_method="S256")
    with pytest.raises(OAuthError) as exc_info:
        exchange_code(
            grant_type="authorization_code",
            code=code,
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="https://chatgpt.com/aip/callback",
            code_verifier=None,
        )
    assert exc_info.value.error == "invalid_grant"


# ---------------------------------------------------------------------------
# validate_oauth_token / sign_access_token
# ---------------------------------------------------------------------------


def test_validate_oauth_token_valid(monkeypatch):
    monkeypatch.setenv("MCP_OAUTH_SIGNING_KEY", "test-signing-key-0000000000000000")
    token = sign_access_token(client_id="test-client-id", scope="mcp", ttl=3600)
    assert token.startswith("mcp.")
    assert validate_oauth_token(token) is True


def test_validate_oauth_token_unknown(monkeypatch):
    monkeypatch.setenv("MCP_OAUTH_SIGNING_KEY", "test-signing-key-0000000000000000")
    assert validate_oauth_token("not-a-real-token") is False


def test_validate_oauth_token_expired(monkeypatch):
    monkeypatch.setenv("MCP_OAUTH_SIGNING_KEY", "test-signing-key-0000000000000000")
    token = sign_access_token(client_id="test-client-id", scope="mcp", ttl=-1)
    assert validate_oauth_token(token) is False


def test_validate_oauth_token_tampered(monkeypatch):
    monkeypatch.setenv("MCP_OAUTH_SIGNING_KEY", "test-signing-key-0000000000000000")
    token = sign_access_token(client_id="test-client-id", scope="mcp", ttl=3600)
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}TAMPERED.{parts[2]}"
    assert validate_oauth_token(tampered) is False


def test_validate_oauth_token_wrong_key(monkeypatch):
    monkeypatch.setenv("MCP_OAUTH_SIGNING_KEY", "key-one-000000000000000000000000")
    token = sign_access_token(client_id="test-client-id", scope="mcp", ttl=3600)
    monkeypatch.setenv("MCP_OAUTH_SIGNING_KEY", "key-two-000000000000000000000000")
    assert validate_oauth_token(token) is False


# ---------------------------------------------------------------------------
# HTTP route integration tests
# ---------------------------------------------------------------------------


def test_authorize_route_redirects(http_client):
    resp = http_client.get(
        "/oauth/authorize",
        params={
            "client_id": "test-client-id",
            "redirect_uri": "https://chatgpt.com/aip/callback",
            "response_type": "code",
            "scope": "mcp",
            "state": "abc",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "code=" in location
    assert "state=abc" in location


def test_authorize_route_invalid_redirect(http_client):
    resp = http_client.get(
        "/oauth/authorize",
        params={
            "client_id": "test-client-id",
            "redirect_uri": "https://attacker.com/steal",
            "response_type": "code",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_request"


def test_token_route_happy_path(http_client):
    auth_resp = http_client.get(
        "/oauth/authorize",
        params={
            "client_id": "test-client-id",
            "redirect_uri": "https://chatgpt.com/aip/callback",
            "response_type": "code",
        },
        follow_redirects=False,
    )
    from urllib.parse import parse_qs, urlparse

    location = auth_resp.headers["location"]
    qs = parse_qs(urlparse(location).query)
    code = qs["code"][0]

    token_resp = http_client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "redirect_uri": "https://chatgpt.com/aip/callback",
        },
    )
    assert token_resp.status_code == 200
    body = token_resp.json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"].startswith("mcp.")


def test_token_route_invalid_code(http_client):
    resp = http_client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": "bogus",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "redirect_uri": "https://chatgpt.com/aip/callback",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_grant"


def test_middleware_accepts_oauth_token(oauth_env, fresh_stores):
    from urllib.parse import parse_qs, urlparse

    from deploy_orchestrator_mcp.server import _make_asgi_app

    app = _make_asgi_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        auth_resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": "test-client-id",
                "redirect_uri": "https://chatgpt.com/aip/callback",
                "response_type": "code",
            },
            follow_redirects=False,
        )
        code = parse_qs(urlparse(auth_resp.headers["location"]).query)["code"][0]

        token_resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
                "redirect_uri": "https://chatgpt.com/aip/callback",
            },
        )
        access_token = token_resp.json()["access_token"]

        mcp_resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert mcp_resp.status_code != 401


def test_middleware_rejects_unknown_token(oauth_env, fresh_stores):
    from deploy_orchestrator_mcp.server import _make_asgi_app

    app = _make_asgi_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Authorization": "Bearer totally-invalid-token"},
        )
        assert resp.status_code == 401


def test_bearer_api_key_still_works(monkeypatch, fresh_stores):
    monkeypatch.setenv("MCP_SERVER_API_KEY", "my-static-key")
    monkeypatch.delenv("OAUTH_CLIENT_ID", raising=False)
    from deploy_orchestrator_mcp.server import _make_asgi_app

    app = _make_asgi_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={"Authorization": "Bearer my-static-key"},
        )
        assert resp.status_code != 401
