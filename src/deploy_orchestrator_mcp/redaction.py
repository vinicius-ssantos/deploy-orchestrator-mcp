from urllib.parse import parse_qsl, urlparse


SENSITIVE_KEYWORDS = (
    "api_key",
    "apikey",
    "auth_token",
    "authorization",
    "client_secret",
    "connection_string",
    "database_url",
    "db_url",
    "jwt",
    "password",
    "private_key",
    "secret",
    "service_role",
    "token",
)

REDACTED = "[REDACTED]"

PUBLIC_URL_KEYS = {
    "url",
    "public_url",
    "preview_url",
    "deployment_url",
}

PUBLIC_IDENTIFIER_KEYS = {
    "deployment_id",
    "deploy_id",
}


def _normalized_key(key):
    return str(key).strip().lower().replace("-", "_")


def is_sensitive_key(key):
    """Return True when a key name likely contains a secret."""
    normalized = _normalized_key(key)
    return any(keyword in normalized for keyword in SENSITIVE_KEYWORDS)


def looks_sensitive_value(value):
    """Return True when a string value looks like a secret-bearing value."""
    if not isinstance(value, str):
        return False

    normalized = value.strip().lower()
    if not normalized:
        return False

    secret_prefixes = (
        "postgres://",
        "postgresql://",
        "mysql://",
        "mongodb://",
        "redis://",
        "supabase_service_role",
        "bearer ",
    )
    if normalized.startswith(secret_prefixes):
        return True

    if "://" in normalized and "@" in normalized:
        return True

    if len(value) >= 32 and any(char.isdigit() for char in value):
        return True

    return False


def is_safe_public_url(value):
    """Return True when a URL is public and does not carry credentials/secrets."""
    if not isinstance(value, str):
        return False

    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    if parsed.username or parsed.password or "@" in parsed.netloc:
        return False

    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if is_sensitive_key(key):
            return False

    return True


def is_safe_public_identifier(value):
    """Return True for provider deployment IDs that are operational identifiers, not secrets."""
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    if not normalized:
        return False
    if normalized.startswith(("bearer ", "postgres://", "postgresql://", "mysql://", "mongodb://", "redis://")):
        return False
    return True


def redact_value(value):
    """Redact one value when it looks secret-like."""
    if looks_sensitive_value(value):
        return REDACTED
    return value


def redact(data):
    """Return a redacted copy of nested dictionaries, lists, tuples and strings."""
    if isinstance(data, dict):
        redacted = {}
        for key, value in data.items():
            normalized_key = _normalized_key(key)
            if is_sensitive_key(key):
                redacted[key] = REDACTED
            elif normalized_key in PUBLIC_URL_KEYS and is_safe_public_url(value):
                redacted[key] = value
            elif normalized_key in PUBLIC_IDENTIFIER_KEYS and is_safe_public_identifier(value):
                redacted[key] = value
            else:
                redacted[key] = redact(value)
        return redacted

    if isinstance(data, list):
        return [redact(item) for item in data]

    if isinstance(data, tuple):
        return tuple(redact(item) for item in data)

    return redact_value(data)
