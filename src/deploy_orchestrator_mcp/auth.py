import os
import secrets

_SERVER_API_KEY_ENV = "MCP_SERVER_API_KEY"


def get_server_api_key() -> str | None:
    return os.getenv(_SERVER_API_KEY_ENV)


def is_auth_enabled() -> bool:
    return bool(get_server_api_key())


def validate_bearer_token(token: str) -> bool:
    """Validate a Bearer token against MCP_SERVER_API_KEY.

    Returns True when auth is disabled (no key configured) so stdio/local
    usage works without configuration.
    """
    server_key = get_server_api_key()
    if not server_key:
        return True
    return secrets.compare_digest(token.strip(), server_key.strip())


def auth_status() -> dict:
    return {
        "auth_enabled": is_auth_enabled(),
        "method": "bearer_api_key" if is_auth_enabled() else "none",
    }
