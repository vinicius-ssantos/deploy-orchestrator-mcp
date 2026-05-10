import pytest

from deploy_orchestrator_mcp.policy import (
    DEFAULT_POLICY,
    evaluate_policy,
    is_app_provider_allowed_by_policy,
    is_database_provider_allowed_by_policy,
    is_environment_allowed_by_policy,
    is_frontend_environment_allowed_by_policy,
    is_frontend_provider_allowed_by_policy,
    parse_repo_policy,
    production_requires_approval,
)


def test_default_policy_allows_staging():
    assert is_environment_allowed_by_policy(DEFAULT_POLICY, "staging") is True


def test_default_policy_blocks_production():
    assert is_environment_allowed_by_policy(DEFAULT_POLICY, "production") is False
    assert production_requires_approval(DEFAULT_POLICY) is True


def test_default_policy_allows_core_providers():
    assert is_app_provider_allowed_by_policy(DEFAULT_POLICY, "render") is True
    assert is_app_provider_allowed_by_policy(DEFAULT_POLICY, "railway") is True
    assert is_database_provider_allowed_by_policy(DEFAULT_POLICY, "supabase") is True


def test_evaluate_policy_valid_plan():
    result = evaluate_policy(
        policy=DEFAULT_POLICY,
        environment="staging",
        app_provider="render",
        database_provider="supabase",
    )

    assert result["valid"] is True
    assert result["errors"] == []


def test_evaluate_policy_blocks_disallowed_provider():
    policy = {
        **DEFAULT_POLICY,
        "allowed_app_providers": ["render"],
    }

    result = evaluate_policy(
        policy=policy,
        environment="staging",
        app_provider="fly",
        database_provider=None,
    )

    assert result["valid"] is False
    assert result["errors"]


def test_evaluate_policy_blocks_disallowed_database_provider():
    policy = {
        **DEFAULT_POLICY,
        "allowed_database_providers": ["supabase"],
    }

    result = evaluate_policy(
        policy=policy,
        environment="staging",
        app_provider="render",
        database_provider="same-provider-postgres",
    )

    assert result["valid"] is False
    assert result["errors"]


# ---------------------------------------------------------------------------
# parse_repo_policy tests
# ---------------------------------------------------------------------------


def test_parse_repo_policy_empty_yaml_returns_default():
    policy = parse_repo_policy("")
    assert policy["allowed_environments"] == DEFAULT_POLICY["allowed_environments"]
    assert policy["production"]["allowed"] is False


def test_parse_repo_policy_override_allowed_environments():
    yaml_str = "allowed_environments:\n  - preview\n  - staging\n  - production\n"
    policy = parse_repo_policy(yaml_str)
    assert "production" in policy["allowed_environments"]


def test_parse_repo_policy_production_allowed_override():
    yaml_str = "production:\n  allowed: true\n  requires_approval: true\n"
    policy = parse_repo_policy(yaml_str)
    assert policy["production"]["allowed"] is True
    assert policy["production"]["requires_approval"] is True


def test_parse_repo_policy_partial_production_keeps_defaults():
    yaml_str = "production:\n  allowed: true\n"
    policy = parse_repo_policy(yaml_str)
    assert policy["production"]["allowed"] is True
    assert "requires_approval" in policy["production"]


def test_parse_repo_policy_restrict_providers():
    yaml_str = "allowed_app_providers:\n  - render\n"
    policy = parse_repo_policy(yaml_str)
    assert policy["allowed_app_providers"] == ["render"]
    assert is_app_provider_allowed_by_policy(policy, "render") is True
    assert is_app_provider_allowed_by_policy(policy, "railway") is False


def test_parse_repo_policy_unknown_provider_blocked():
    yaml_str = "allowed_app_providers:\n  - render\n  - railway\n"
    policy = parse_repo_policy(yaml_str)
    assert is_app_provider_allowed_by_policy(policy, "fly") is False


def test_parse_repo_policy_preserves_unset_defaults():
    yaml_str = "version: 2\n"
    policy = parse_repo_policy(yaml_str)
    assert policy["rules"]["require_dry_run_first"] is True
    assert policy["rules"]["never_return_secret_values"] is True


def test_parse_repo_policy_invalid_yaml_raises():
    with pytest.raises(ValueError, match="Invalid policy YAML"):
        parse_repo_policy("{\ninvalid: yaml: content\n  bad")


def test_parse_repo_policy_non_mapping_raises():
    with pytest.raises(ValueError, match="mapping"):
        parse_repo_policy("- item1\n- item2\n")


def test_parse_repo_policy_preview_allowed():
    yaml_str = "allowed_environments:\n  - preview\n"
    policy = parse_repo_policy(yaml_str)
    assert is_environment_allowed_by_policy(policy, "preview") is True
    assert is_environment_allowed_by_policy(policy, "staging") is False


def test_evaluate_policy_with_parsed_yaml():
    yaml_str = (
        "allowed_environments:\n  - staging\n  - preview\n"
        "allowed_app_providers:\n  - render\n"
        "allowed_database_providers:\n  - supabase\n"
    )
    policy = parse_repo_policy(yaml_str)
    result = evaluate_policy(policy, "staging", "render", "supabase")
    assert result["valid"] is True

    result_blocked = evaluate_policy(policy, "production", "render")
    assert result_blocked["valid"] is False


def test_evaluate_policy_production_allowed_when_policy_permits():
    yaml_str = "production:\n  allowed: true\n  requires_approval: true\n"
    policy = parse_repo_policy(yaml_str)
    result = evaluate_policy(policy, "production", "render")
    assert result["valid"] is True
    assert result["production_requires_approval"] is True


# ---------------------------------------------------------------------------
# Frontend policy tests
# ---------------------------------------------------------------------------


def test_frontend_provider_allowed_by_default():
    assert is_frontend_provider_allowed_by_policy(DEFAULT_POLICY, "vercel") is True
    assert is_frontend_provider_allowed_by_policy(DEFAULT_POLICY, "netlify") is True
    assert is_frontend_provider_allowed_by_policy(DEFAULT_POLICY, "cloudflare_pages") is True


def test_unknown_frontend_provider_blocked():
    assert is_frontend_provider_allowed_by_policy(DEFAULT_POLICY, "unknown-static") is False


def test_frontend_preview_allowed_by_default():
    assert is_frontend_environment_allowed_by_policy(DEFAULT_POLICY, "preview") is True


def test_frontend_staging_allowed_by_default():
    assert is_frontend_environment_allowed_by_policy(DEFAULT_POLICY, "staging") is True


def test_frontend_production_blocked_by_default():
    assert is_frontend_environment_allowed_by_policy(DEFAULT_POLICY, "production") is False


def test_frontend_production_allowed_via_custom_policy():
    custom_policy = {
        **DEFAULT_POLICY,
        "frontend": {
            "production_allowed": True,
            "require_approval": True,
            "allowed_environments": ["preview", "staging", "production"],
        },
    }
    assert is_frontend_environment_allowed_by_policy(custom_policy, "production") is True
