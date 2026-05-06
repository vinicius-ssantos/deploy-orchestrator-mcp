import os

_PROVIDER_ENV_VARS: dict[str, str] = {
    "render": "RENDER_API_KEY",
    "railway": "RAILWAY_TOKEN",
    "fly": "FLY_API_TOKEN",
    "koyeb": "KOYEB_API_TOKEN",
    "coolify": "COOLIFY_API_TOKEN",
    "supabase": "SUPABASE_ACCESS_TOKEN",
}

_EXTRA_ENV_VARS: dict[str, str] = {
    "coolify_base_url": "COOLIFY_BASE_URL",
    "supabase_org_id": "SUPABASE_ORG_ID",
}

_ALL_ENV_VARS = {**_PROVIDER_ENV_VARS, **_EXTRA_ENV_VARS}


class CredentialStore:
    """In-memory credential store with lazy env var fallback.

    set() overrides the env var for a key at runtime.
    clear() removes the runtime override; the env var fallback is restored.
    Credentials can be updated at runtime via MCP tools without restarting.
    """

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        if key in self._store:
            return self._store[key]
        # Lazy fallback: check current env var value
        env_var = _ALL_ENV_VARS.get(key)
        return os.getenv(env_var) if env_var else None

    def set(self, key: str, value: str) -> None:
        if not value or not value.strip():
            raise ValueError(f"Credential value for '{key}' must not be empty")
        self._store[key] = value.strip()

    def clear(self, key: str) -> None:
        self._store.pop(key, None)

    def status(self) -> dict[str, bool]:
        """Return which known providers have a credential configured."""
        return {provider: self.get(provider) is not None for provider in _PROVIDER_ENV_VARS}

    def configured_keys(self) -> list[str]:
        return [k for k in _ALL_ENV_VARS if self.get(k) is not None]


_store = CredentialStore()


def get_credential(key: str) -> str | None:
    return _store.get(key)


def set_credential(key: str, value: str) -> None:
    _store.set(key, value)


def clear_credential(key: str) -> None:
    _store.clear(key)


def credential_status() -> dict[str, bool]:
    return _store.status()


def known_providers() -> list[str]:
    return list(_PROVIDER_ENV_VARS.keys())
