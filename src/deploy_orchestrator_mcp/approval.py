SENSITIVE_ACTION_KEYWORDS = (
    "create service",
    "create database",
    "provision database",
    "environment variables",
    "trigger deployment",
    "apply migration",
    "rollback",
    "configure domain",
    "scale service",
)

DESTRUCTIVE_ACTION_KEYWORDS = (
    "delete",
    "destroy",
    "reset database",
    "restore backup",
    "expose database publicly",
    "run production write sql",
)


def _normalize_action(action):
    return str(action).strip().lower()


def _plan_environment(plan):
    return str(plan.get("environment", "")).strip().lower()


def _approval_action_metadata(plan):
    explicit_actions = plan.get("approval_required_actions")
    if explicit_actions is not None:
        return list(explicit_actions)

    legacy_actions = plan.get("approval_required")
    if isinstance(legacy_actions, list):
        return list(legacy_actions)

    return []


def approval_required_actions(plan):
    """Return plan actions that require explicit user confirmation."""
    actions = _approval_action_metadata(plan)
    steps = list(plan.get("steps") or [])
    all_actions = actions + steps

    required = []
    for action in all_actions:
        normalized = _normalize_action(action)
        if not normalized:
            continue

        requires_approval = any(
            keyword in normalized for keyword in SENSITIVE_ACTION_KEYWORDS
        )
        destructive = any(
            keyword in normalized for keyword in DESTRUCTIVE_ACTION_KEYWORDS
        )

        if requires_approval or destructive:
            required.append(action)

    if _plan_environment(plan) == "production":
        production_action = "production deployment"
        if production_action not in required:
            required.insert(0, production_action)

    return required


def requires_approval(plan):
    """Return True when a deployment plan requires explicit user confirmation."""
    return len(approval_required_actions(plan)) > 0
