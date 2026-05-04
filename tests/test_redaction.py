from deploy_orchestrator_mcp.redaction import REDACTED, is_sensitive_key, redact


def test_sensitive_keys_are_redacted():
    data = {
        "RENDER_API_KEY": "render-secret",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role-secret",
        "normal_name": "deploy-orchestrator-mcp",
    }

    assert redact(data) == {
        "RENDER_API_KEY": REDACTED,
        "SUPABASE_SERVICE_ROLE_KEY": REDACTED,
        "normal_name": "deploy-orchestrator-mcp",
    }


def test_nested_dicts_and_lists_are_redacted():
    data = {
        "provider": "supabase",
        "projects": [
            {
                "name": "staging",
                "database_url": "postgres://user:password@example.com:5432/app",
            },
            {
                "name": "preview",
                "public_url": "https://preview.example.com",
            },
        ],
    }

    redacted = redact(data)

    assert redacted["provider"] == "supabase"
    assert redacted["projects"][0]["database_url"] == REDACTED
    assert redacted["projects"][1]["public_url"] == "https://preview.example.com"


def test_secret_like_string_values_are_redacted_even_without_sensitive_key():
    data = {
        "connection": "postgresql://user:password@example.com:5432/app",
        "authorization_header": "Bearer abc123",
        "public_url": "https://example.com",
    }

    redacted = redact(data)

    assert redacted["connection"] == REDACTED
    assert redacted["authorization_header"] == REDACTED
    assert redacted["public_url"] == "https://example.com"


def test_non_sensitive_values_remain_readable():
    data = {
        "environment": "staging",
        "app_provider": "render",
        "approval_required": True,
        "approval_required_actions": ["create service"],
    }

    assert redact(data) == data


def test_sensitive_key_detection_handles_common_variants():
    assert is_sensitive_key("api-key") is True
    assert is_sensitive_key("DATABASE_URL") is True
    assert is_sensitive_key("service_role_key") is True
    assert is_sensitive_key("public_url") is False
