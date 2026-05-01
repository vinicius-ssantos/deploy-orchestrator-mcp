from deploy_orchestrator_mcp.config import is_environment_allowed, is_provider_allowed


PROVIDER_NAME = "fly"


def fly_validate_request(environment="staging"):
    errors = []

    if not is_provider_allowed(PROVIDER_NAME):
        errors.append("Fly provider is not allowed by MCP_ALLOWED_PROVIDERS")

    if not is_environment_allowed(environment):
        errors.append(f"Environment '{environment}' is not allowed")

    return {
        "provider": PROVIDER_NAME,
        "environment": environment,
        "valid": len(errors) == 0,
        "errors": errors,
        "mode": "dry-run",
    }


def fly_generate_app_plan(repo_full_name, app_name, environment="staging", needs_volume=False):
    validation = fly_validate_request(environment=environment)

    planned_actions = [
        "create or link Fly app",
        "validate Dockerfile or fly.toml",
        "configure runtime variables",
        "deploy app after approval",
        "read app status and logs",
        "run healthcheck",
    ]

    approval_required = [
        "create app",
        "configure runtime variables",
        "deploy app",
    ]

    if needs_volume:
        planned_actions.insert(2, "create Fly volume")
        approval_required.append("create volume")

    return {
        "provider": PROVIDER_NAME,
        "repo_full_name": repo_full_name,
        "app_name": app_name,
        "environment": environment,
        "needs_volume": needs_volume,
        "validation": validation,
        "planned_actions": planned_actions,
        "approval_required": approval_required,
        "mode": "dry-run",
    }
