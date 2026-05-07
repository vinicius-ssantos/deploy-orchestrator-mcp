"""OAuth 2.0 Authorization Code flow with optional PKCE (S256).

Supports ChatGPT custom connector and any OAuth 2.0-compatible client.

Store backend is selected at startup:
  - REDIS_URL set → RedisAuthCodeStore + RedisTokenStore (survives redeploys,
    supports horizontal scale)
  - REDIS_URL unset → in-memory stores (local / stdio / test usage)
"""

import base64
import hashlib
import json
import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional


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


# ---------------------------------------------------------------------------
# In-memory stores
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


@dataclass
class _TokenEntry:
    client_id: str
    scope: str
    expires_at: float


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


class TokenStore:
    def __init__(self) -> None:
        self._store: dict[str, _TokenEntry] = {}

    def issue(self, client_id: str, scope: str, ttl: int) -> str:
        token = secrets.token_urlsafe(40)
        self._store[token] = _TokenEntry(
            client_id=client_id,
            scope=scope,
            expires_at=time.monotonic() + ttl,
        )
        return token

    def validate(self, token: str) -> bool:
        entry = self._store.get(token)
        if entry is None:
            return False
        if time.monotonic() > entry.expires_at:
            del self._store[token]
            return False
        return True

    def _purge_expired(self) -> None:
        now = time.monotonic()
        self._store = {k: v for k, v in self._store.items() if now <= v.expires_at}


# ---------------------------------------------------------------------------
# Redis-backed stores
# ---------------------------------------------------------------------------

_REDIS_CODE_PREFIX = "mcp:oauth:code:"
_REDIS_TOKEN_PREFIX = "mcp:oauth:token:"


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


class RedisTokenStore:
    """Token store backed by Redis. TTL enforced server-side."""

    def __init__(self, client):
        self._r = client

    def issue(self, client_id: str, scope: str, ttl: int) -> str:
        token = secrets.token_urlsafe(40)
        payload = json.dumps({"client_id": client_id, "scope": scope})
        self._r.set(f"{_REDIS_TOKEN_PREFIX}{token}", payload, ex=ttl)
        return token

    def validate(self, token: str) -> bool:
        return bool(self._r.exists(f"{_REDIS_TOKEN_PREFIX}{token}"))


# ---------------------------------------------------------------------------
# Store factory — selects Redis or in-memory based on REDIS_URL
# ---------------------------------------------------------------------------

_auth_code_store: "AuthCodeStore | RedisAuthCodeStore | None" = None
_token_store: "TokenStore | RedisTokenStore | None" = None


try:
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore[assignment]


def _build_stores() -> tuple:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        if redis is None:  # pragma: no cover
            raise RuntimeError("redis package is not installed; add 'redis[hiredis]>=5' to dependencies")
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()  # fail fast if Redis is unreachable
        return RedisAuthCodeStore(client, ttl=600), RedisTokenStore(client)
    return AuthCodeStore(ttl=600), TokenStore()


def get_auth_code_store():
    global _auth_code_store, _token_store
    if _auth_code_store is None:
        _auth_code_store, _token_store = _build_stores()
    return _auth_code_store


def get_token_store():
    global _auth_code_store, _token_store
    if _token_store is None:
        _auth_code_store, _token_store = _build_stores()
    return _token_store


def reset_stores() -> None:
    """Force re-initialisation of stores — used in tests."""
    global _auth_code_store, _token_store
    _auth_code_store = None
    _token_store = None


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
    """Validate params and issue an auth code.  Returns dict with 'code' (and 'state')."""
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
    """Exchange an auth code for an access token."""
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

    token = get_token_store().issue(
        client_id=client_id,
        scope=entry.scope,
        ttl=config.token_ttl,
    )

    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": config.token_ttl,
        "scope": entry.scope,
    }


def validate_oauth_token(token: str) -> bool:
    return get_token_store().validate(token)


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
