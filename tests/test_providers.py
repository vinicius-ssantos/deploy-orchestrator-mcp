from deploy_orchestrator_mcp.providers import get_provider_capability, list_provider_capabilities


def test_list_provider_capabilities_contains_core_providers():
    capabilities = list_provider_capabilities()

    assert "render" in capabilities["app_providers"]
    assert "railway" in capabilities["app_providers"]
    assert "supabase" in capabilities["database_providers"]
    assert capabilities["mode"] == "dry-run"


def test_list_provider_capabilities_contains_frontend_providers():
    capabilities = list_provider_capabilities()
    assert "frontend_providers" in capabilities
    assert "vercel" in capabilities["frontend_providers"]


def test_vercel_provider_capabilities():
    vercel = get_provider_capability("vercel")
    assert vercel is not None
    assert vercel["kind"] == "frontend-static"
    assert vercel["supports_git_deploy"] is True
    assert vercel["supports_preview_deployments"] is True
    assert "vite" in vercel["best_for"]


def test_get_render_capabilities():
    render = get_provider_capability("render")

    assert render["kind"] == "app"
    assert render["supports_git_deploy"] is True
    assert "python" in render["best_for"]


def test_get_unknown_provider_returns_none():
    assert get_provider_capability("unknown-provider") is None

