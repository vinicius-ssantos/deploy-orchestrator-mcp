from deploy_orchestrator_mcp.redaction import redact


def _value(mapping, key, default="None"):
    if not mapping:
        return default
    value = mapping.get(key)
    if value is None:
        return default
    return str(value)


def _provider_label(provider):
    if not provider:
        return "None"
    name = _value(provider, "provider")
    reason = _value(provider, "reason", "")
    if reason:
        return f"{name} - {reason}"
    return name


def _bullet_list(items):
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


def format_deployment_plan_summary(plan):
    """Return a deterministic, redaction-safe Markdown summary for GitHub comments."""
    safe_plan = redact(plan or {})

    policy_result = safe_plan.get("policy_result") or {}
    policy_status = "pass" if policy_result.get("valid") else "fail"
    policy_errors = policy_result.get("errors") or []

    lines = [
        "## Deployment plan summary",
        "",
        f"- Environment: {_value(safe_plan, 'environment')}",
        f"- Mode: {_value(safe_plan, 'mode')}",
        f"- App provider: {_provider_label(safe_plan.get('app_provider'))}",
        f"- Database provider: {_provider_label(safe_plan.get('database_provider'))}",
        f"- Policy result: {policy_status}",
        f"- Approval required: {bool(safe_plan.get('approval_required'))}",
        "",
        "### Approval-required actions",
        _bullet_list(safe_plan.get("approval_required_actions") or []),
        "",
        "### Risks",
        _bullet_list(safe_plan.get("risks") or []),
        "",
        "### Policy errors",
        _bullet_list(policy_errors),
        "",
        "### Steps",
        _bullet_list(safe_plan.get("steps") or []),
    ]

    return "\n".join(lines)


def github_comment_body_for_deployment_plan(plan):
    """Integration point for posting summaries to GitHub issues or PRs."""
    return format_deployment_plan_summary(plan)
