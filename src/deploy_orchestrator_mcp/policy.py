import copy

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

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


def parse_repo_policy(yaml_str: str) -> dict:
    """Parse a YAML policy string and deep-merge it with DEFAULT_POLICY.

    Returns a policy dict with all DEFAULT_POLICY keys present, overridden
    by any keys specified in the YAML content.

    Raises ValueError if YAML is invalid or yaml package is not installed.
    """
    if not _YAML_AVAILABLE:
        raise ValueError("PyYAML is not installed; cannot parse policy YAML")
    try:
        parsed = _yaml.safe_load(yaml_str)
    except Exception as exc:
        raise ValueError(f"Invalid policy YAML: {exc}") from exc

    if parsed is None:
        return copy.deepcopy(DEFAULT_POLICY)
    if not isinstance(parsed, dict):
        raise ValueError("Policy YAML must be a mapping at the top level")

    merged = copy.deepcopy(DEFAULT_POLICY)
    for key, value in parsed.items():
        if key in ("production", "rules") and isinstance(value, dict):
            merged[key] = {**merged.get(key, {}), **value}
        else:
            merged[key] = value
    return merged


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
