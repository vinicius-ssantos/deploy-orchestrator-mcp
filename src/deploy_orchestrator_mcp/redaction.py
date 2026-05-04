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


def is_sensitive_key(key):
    """Return True when a key name likely contains a secret."""
    normalized = str(key).strip().lower().replace("-", "_")
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
            if is_sensitive_key(key):
                redacted[key] = REDACTED
            else:
                redacted[key] = redact(value)
        return redacted

    if isinstance(data, list):
        return [redact(item) for item in data]

    if isinstance(data, tuple):
        return tuple(redact(item) for item in data)

    return redact_value(data)
