from deploy_orchestrator_mcp.policy import (
    DEFAULT_POLICY,
    evaluate_policy,
    is_app_provider_allowed_by_policy,
    is_database_provider_allowed_by_policy,
    is_environment_allowed_by_policy,
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
