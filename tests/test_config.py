from deploy_orchestrator_mcp.config import get_settings, is_environment_allowed, is_provider_allowed, is_repo_allowed


def test_default_settings_are_safe(monkeypatch):
    monkeypatch.delenv("MCP_READ_ONLY", raising=False)
    monkeypatch.delenv("MCP_REQUIRE_CONFIRMATION", raising=False)
    monkeypatch.delenv("MCP_ALLOWED_REPOS", raising=False)

    settings = get_settings()

    assert settings["read_only"] is True
    assert settings["require_confirmation"] is True
    assert "staging" in settings["allowed_environments"]


def test_provider_allowlist(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_PROVIDERS", "render,supabase")

    assert is_provider_allowed("render") is True
    assert is_provider_allowed("fly") is False


def test_repo_allowlist_empty_allows_any_repo(monkeypatch):
    monkeypatch.delenv("MCP_ALLOWED_REPOS", raising=False)

    assert is_repo_allowed("vinicius-ssantos/deploy-orchestrator-mcp") is True


def test_environment_allowlist(monkeypatch):
    monkeypatch.setenv("MCP_ALLOWED_ENVIRONMENTS", "preview,staging")

    assert is_environment_allowed("staging") is True
    assert is_environment_allowed("production") is False
