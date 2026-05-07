"""OAuth 2.0 Authorization Code flow with optional PKCE (S256).

Supports ChatGPT custom connector and any OAuth 2.0-compatible client.

Access token design — stateless HMAC-SHA256 signed tokens:
  - Format: mcp.<b64url(json_payload)>.<b64url(hmac_sha256_signature)>
  - Payload fields: client_id, scope, iat, exp
  - Signing key: MCP_OAUTH_SIGNING_KEY env var
  - No token store needed — tokens survive redeploys with the same key

Auth code store backend is selected at startup:
  - REDIS_URL set   → RedisAuthCodeStore  (atomic GETDEL, multi-instance safe)
  - REDIS_URL unset → AuthCodeStore       (in-memory, local / stdio / test)
"""

import base64
import hashlib
import hmac as hmac_mod
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class OAuthConfig:
    client_id: str
    client_secret: str
    redirect_uris: list[str]
    scopes: list[str]
    token_ttl: int  # seconds

    @classmethod
    def from_env(cls) -> Optional["OAuthConfig"]:
        client_id = os.getenv("OAUTH_CLIENT_ID", "").strip()
        if not client_id:
            return None
        raw_uris = os.getenv("OAUTH_REDIRECT_URIS", "").strip()
        redirect_uris = [u.strip() for u in raw_uris.split(",") if u.strip()]
        raw_scopes = os.getenv("OAUTH_SCOPES", "mcp").strip()
        scopes = [s.strip() for s in raw_scopes.split() if s.strip()]
        return cls(
            client_id=client_id,
            client_secret=os.getenv("OAUTH_CLIENT_SECRET", "").strip(),
            redirect_uris=redirect_uris,
            scopes=scopes,
            token_ttl=int(os.getenv("OAUTH_TOKEN_TTL_SECONDS", "3600")),
        )


def get_oauth_config() -> Optional[OAuthConfig]:
    return OAuthConfig.from_env()


def is_oauth_enabled() -> bool:
    return bool(os.getenv("OAUTH_CLIENT_ID", "").strip())


def oauth_signing_key() -> str:
    return os.getenv("MCP_OAUTH_SIGNING_KEY", "").strip()


# ---------------------------------------------------------------------------
# Signed access token helpers
# ---------------------------------------------------------------------------


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _json_b64url(payload: dict[str, Any]) -> str:
    return _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _hmac_sign(message: str) -> str:
    key = oauth_signing_key()
    if not key:
        raise RuntimeError("MCP_OAUTH_SIGNING_KEY is required when OAuth is enabled")
    digest = hmac_mod.new(key.encode("utf-8"), message.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def sign_access_token(*, client_id: str, scope: str, ttl: int) -> str:
    """Issue a self-contained HMAC-signed access token.

    Format: mcp.<b64url(payload)>.<b64url(hmac)>
    Survives redeploys as long as MCP_OAUTH_SIGNING_KEY stays the same.
    """
    now = int(time.time())
    payload = {"client_id": client_id, "scope": scope, "iat": now, "exp": now + ttl}
    encoded_payload = _json_b64url(payload)
    encoded_sig = _hmac_sign(encoded_payload)
    return f"mcp.{encoded_payload}.{encoded_sig}"


def validate_access_token(token: str) -> Optional[dict[str, Any]]:
    """Verify token signature and expiry. Returns payload dict or None."""
    key = oauth_signing_key()
    if not key or not token.startswith("mcp."):
        return None

    parts = token.split(".")
    if len(parts) != 3:
        return None

    _, encoded_payload, encoded_sig = parts
    try:
        expected_sig = _hmac_sign(encoded_payload)
    except RuntimeError:
        return None

    if not hmac_mod.compare_digest(encoded_sig, expected_sig):
        return None

    try:
        payload = json.loads(_b64url_decode(encoded_payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None

    return payload


def validate_oauth_token(token: str) -> bool:
    return validate_access_token(token) is not None


# ---------------------------------------------------------------------------
# In-memory auth code store
# ---------------------------------------------------------------------------


@dataclass
class _AuthCodeEntry:
    client_id: str
    redirect_uri: str
    scope: str
    code_challenge: Optional[str]
    code_challenge_method: Optional[str]
    expires_at: float
    used: bool = False


class AuthCodeStore:
    def __init__(self, ttl: int = 600):
        self._ttl = ttl
        self._store: dict[str, _AuthCodeEntry] = {}

    def issue(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str,
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None,
    ) -> str:
        code = secrets.token_urlsafe(32)
        self._store[code] = _AuthCodeEntry(
            client_id=client_id,
            redirect_uri=redirect_uri,
            scope=scope,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=time.monotonic() + self._ttl,
        )
        return code

    def consume(self, code: str) -> Optional[_AuthCodeEntry]:
        """Return and invalidate the entry, or None if absent/expired/used."""
        entry = self._store.get(code)
        if entry is None:
            return None
        if entry.used or time.monotonic() > entry.expires_at:
            self._store.pop(code, None)
            return None
        entry.used = True
        return entry

    def _purge_expired(self) -> None:
        now = time.monotonic()
        self._store = {k: v for k, v in self._store.items() if now <= v.expires_at and not v.used}


# ---------------------------------------------------------------------------
# Redis-backed auth code store
# ---------------------------------------------------------------------------

_REDIS_CODE_PREFIX = "mcp:oauth:code:"


class RedisAuthCodeStore:
    """Auth code store backed by Redis. TTL and single-use enforced server-side."""

    def __init__(self, client, ttl: int = 600):
        self._r = client
        self._ttl = ttl

    def issue(
        self,
        client_id: str,
        redirect_uri: str,
        scope: str,
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None,
    ) -> str:
        code = secrets.token_urlsafe(32)
        payload = json.dumps({
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
        })
        self._r.set(f"{_REDIS_CODE_PREFIX}{code}", payload, ex=self._ttl)
        return code

    def consume(self, code: str) -> Optional[_AuthCodeEntry]:
        key = f"{_REDIS_CODE_PREFIX}{code}"
        # Atomic get-and-delete: only the first caller succeeds.
        raw = self._r.getdel(key)
        if raw is None:
            return None
        data = json.loads(raw)
        return _AuthCodeEntry(
            client_id=data["client_id"],
            redirect_uri=data["redirect_uri"],
            scope=data["scope"],
            code_challenge=data.get("code_challenge"),
            code_challenge_method=data.get("code_challenge_method"),
            expires_at=0.0,  # TTL enforced by Redis; entry is already consumed
        )


# ---------------------------------------------------------------------------
# Auth code store factory
# ---------------------------------------------------------------------------

try:
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore[assignment]

_auth_code_store: "AuthCodeStore | RedisAuthCodeStore | None" = None


def _build_auth_code_store():
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        if redis is None:  # pragma: no cover
            raise RuntimeError("redis package is not installed; add 'redis[hiredis]>=5' to dependencies")
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()  # fail fast if Redis is unreachable
        return RedisAuthCodeStore(client, ttl=600)
    return AuthCodeStore(ttl=600)


def get_auth_code_store():
    global _auth_code_store
    if _auth_code_store is None:
        _auth_code_store = _build_auth_code_store()
    return _auth_code_store


def reset_stores() -> None:
    """Force re-initialisation of the auth code store — used in tests."""
    global _auth_code_store
    _auth_code_store = None


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------


def _verify_pkce_s256(code_verifier: str, code_challenge: str) -> bool:
    digest = hashlib.sha256(code_verifier.encode()).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return secrets.compare_digest(expected, code_challenge)


# ---------------------------------------------------------------------------
# Core OAuth operations
# ---------------------------------------------------------------------------


class OAuthError(Exception):
    def __init__(self, error: str, description: str, status: int = 400):
        self.error = error
        self.description = description
        self.status = status
        super().__init__(description)


def authorize(
    client_id: str,
    redirect_uri: str,
    response_type: str,
    scope: str = "mcp",
    state: Optional[str] = None,
    code_challenge: Optional[str] = None,
    code_challenge_method: Optional[str] = None,
) -> dict:
    """Validate params and issue an auth code. Returns dict with 'code' (and 'state')."""
    config = get_oauth_config()
    if config is None:
        raise OAuthError("server_error", "OAuth is not configured", status=500)

    if response_type != "code":
        raise OAuthError("unsupported_response_type", f"response_type '{response_type}' not supported")

    if client_id != config.client_id:
        raise OAuthError("invalid_client", "Unknown client_id")

    if redirect_uri not in config.redirect_uris:
        raise OAuthError("invalid_request", "redirect_uri not in allowlist")

    if code_challenge_method and code_challenge_method not in ("S256", "plain"):
        raise OAuthError("invalid_request", "Unsupported code_challenge_method; use S256")

    code = get_auth_code_store().issue(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )

    result: dict = {"code": code}
    if state:
        result["state"] = state
    return result


def exchange_code(
    grant_type: str,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code_verifier: Optional[str] = None,
) -> dict:
    """Exchange an auth code for a signed access token."""
    config = get_oauth_config()
    if config is None:
        raise OAuthError("server_error", "OAuth is not configured", status=500)

    if grant_type != "authorization_code":
        raise OAuthError("unsupported_grant_type", f"grant_type '{grant_type}' not supported")

    if client_id != config.client_id:
        raise OAuthError("invalid_client", "Unknown client_id", status=401)

    if not secrets.compare_digest(client_secret, config.client_secret):
        raise OAuthError("invalid_client", "Invalid client_secret", status=401)

    entry = get_auth_code_store().consume(code)
    if entry is None:
        raise OAuthError("invalid_grant", "Authorization code is invalid, expired, or already used")

    if entry.client_id != client_id:
        raise OAuthError("invalid_grant", "client_id mismatch")

    if entry.redirect_uri != redirect_uri:
        raise OAuthError("invalid_grant", "redirect_uri mismatch")

    # PKCE verification
    if entry.code_challenge:
        if not code_verifier:
            raise OAuthError("invalid_grant", "code_verifier required for PKCE")
        method = entry.code_challenge_method or "S256"
        if method == "S256":
            if not _verify_pkce_s256(code_verifier, entry.code_challenge):
                raise OAuthError("invalid_grant", "PKCE code_verifier verification failed")
        elif method == "plain":
            if not secrets.compare_digest(code_verifier, entry.code_challenge):
                raise OAuthError("invalid_grant", "PKCE code_verifier verification failed")
        else:
            raise OAuthError("invalid_grant", "Unsupported PKCE method")

    access_token = sign_access_token(
        client_id=client_id,
        scope=entry.scope,
        ttl=config.token_ttl,
    )

    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": config.token_ttl,
        "scope": entry.scope,
    }


def discovery_document(base_url: str) -> dict:
    """RFC 8414 authorization server metadata."""
    base_url = base_url.rstrip("/")
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256", "plain"],
        "token_endpoint_auth_methods_supported": ["client_secret_post"],
    }
