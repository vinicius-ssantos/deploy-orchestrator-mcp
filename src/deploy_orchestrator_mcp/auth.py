import os
import secrets

_SERVER_API_KEY_ENV = "MCP_SERVER_API_KEY"


def get_server_api_key() -> str | None:
    return os.getenv(_SERVER_API_KEY_ENV)


def is_auth_enabled() -> bool:
    from deploy_orchestrator_mcp.oauth import is_oauth_enabled
    return bool(get_server_api_key()) or is_oauth_enabled()


def validate_bearer_token(token: str) -> bool:
    """Validate a Bearer token against MCP_SERVER_API_KEY."""
    server_key = get_server_api_key()
    if not server_key:
        return False
    return secrets.compare_digest(token.strip(), server_key.strip())


def validate_any_token(token: str) -> bool:
    """Accept a static Bearer API key or a valid OAuth access token.

    Returns True when no auth method is configured (stdio/local usage).
    """
    if not is_auth_enabled():
        return True
    if get_server_api_key() and validate_bearer_token(token):
        return True
    from deploy_orchestrator_mcp.oauth import is_oauth_enabled, validate_oauth_token
    if is_oauth_enabled() and validate_oauth_token(token):
        return True
    return False


def auth_status() -> dict:
    from deploy_orchestrator_mcp.oauth import is_oauth_enabled
    bearer_enabled = bool(get_server_api_key())
    oauth_enabled = is_oauth_enabled()
    if bearer_enabled and oauth_enabled:
        method = "bearer_api_key+oauth"
    elif bearer_enabled:
        method = "bearer_api_key"
    elif oauth_enabled:
        method = "oauth"
    else:
        method = "none"
    return {
        "auth_enabled": bearer_enabled or oauth_enabled,
        "method": method,
        "bearer_api_key_enabled": bearer_enabled,
        "oauth_enabled": oauth_enabled,
    }
