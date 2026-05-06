import pytest

from deploy_orchestrator_mcp.credentials import (
    CredentialStore,
    clear_credential,
    credential_status,
    get_credential,
    known_providers,
    set_credential,
)


def test_store_loads_from_env(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "rnd_test123")
    store = CredentialStore()
    assert store.get("render") == "rnd_test123"


def test_store_lazy_env_fallback(monkeypatch):
    store = CredentialStore()
    monkeypatch.setenv("RENDER_API_KEY", "lazy_token")
    assert store.get("render") == "lazy_token"


def test_store_set_and_get(monkeypatch):
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    store = CredentialStore()
    store.set("render", "my_token")
    assert store.get("render") == "my_token"


def test_store_clear(monkeypatch):
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    store = CredentialStore()
    store.set("render", "my_token")
    store.clear("render")
    assert store.get("render") is None


def test_store_clear_missing_is_noop():
    store = CredentialStore()
    store.clear("nonexistent")  # must not raise


def test_store_set_rejects_empty():
    store = CredentialStore()
    with pytest.raises(ValueError):
        store.set("render", "")
    with pytest.raises(ValueError):
        store.set("render", "   ")


def test_store_status_all_false_when_empty(monkeypatch):
    for env_var in ["RENDER_API_KEY", "RAILWAY_TOKEN", "FLY_API_TOKEN",
                    "KOYEB_API_TOKEN", "COOLIFY_API_TOKEN", "SUPABASE_ACCESS_TOKEN"]:
        monkeypatch.delenv(env_var, raising=False)
    store = CredentialStore()
    status = store.status()
    assert all(not v for v in status.values())


def test_store_status_reflects_set():
    store = CredentialStore()
    store.set("railway", "tok_abc")
    assert store.status()["railway"] is True


def test_store_set_strips_whitespace():
    store = CredentialStore()
    store.set("render", "  tok_abc  ")
    assert store.get("render") == "tok_abc"


def test_module_level_functions(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", "")
    set_credential("render", "direct_tok")
    assert get_credential("render") == "direct_tok"
    clear_credential("render")
    # After clear, falls back to nothing (module store is shared, but token was cleared)
    # Just verify no exception
    status = credential_status()
    assert isinstance(status, dict)


def test_known_providers_contains_expected():
    providers = known_providers()
    for p in ["render", "railway", "fly", "koyeb", "coolify", "supabase"]:
        assert p in providers
