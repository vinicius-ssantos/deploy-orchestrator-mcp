DEFAULT_POLICY = {
    "version": 1,
    "allowed_environments": ["preview", "staging"],
    "allowed_app_providers": ["render", "railway", "fly", "koyeb", "coolify"],
    "allowed_database_providers": ["supabase", "same-provider-postgres"],
    "production": {
        "allowed": False,
        "requires_approval": True,
    },
    "rules": {
        "require_dry_run_first": True,
        "require_healthcheck": True,
        "never_return_secret_values": True,
        "redact_logs": True,
    },
}


def get_policy_value(policy, key):
    if policy is None:
        policy = DEFAULT_POLICY
    return policy.get(key, DEFAULT_POLICY.get(key))


def is_environment_allowed_by_policy(policy, environment):
    allowed = get_policy_value(policy, "allowed_environments") or []
    if environment == "production":
        production = get_policy_value(policy, "production") or {}
        return production.get("allowed", False) is True
    return environment in allowed


def is_app_provider_allowed_by_policy(policy, provider):
    allowed = get_policy_value(policy, "allowed_app_providers") or []
    return provider in allowed


def is_database_provider_allowed_by_policy(policy, provider):
    allowed = get_policy_value(policy, "allowed_database_providers") or []
    return provider in allowed


def production_requires_approval(policy):
    production = get_policy_value(policy, "production") or {}
    return production.get("requires_approval", True) is True


def evaluate_policy(policy, environment, app_provider, database_provider=None):
    errors = []

    if not is_environment_allowed_by_policy(policy, environment):
        errors.append(f"Environment '{environment}' is not allowed by repository policy")

    if not is_app_provider_allowed_by_policy(policy, app_provider):
        errors.append(f"App provider '{app_provider}' is not allowed by repository policy")

    if database_provider and not is_database_provider_allowed_by_policy(policy, database_provider):
        errors.append(f"Database provider '{database_provider}' is not allowed by repository policy")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "environment": environment,
        "app_provider": app_provider,
        "database_provider": database_provider,
        "production_requires_approval": production_requires_approval(policy),
    }
