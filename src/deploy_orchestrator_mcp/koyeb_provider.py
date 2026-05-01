from deploy_orchestrator_mcp.config import is_environment_allowed, is_provider_allowed


PROVIDER_NAME = "koyeb"


def koyeb_validate_request(environment="staging"):
    errors = []

    if not is_provider_allowed(PROVIDER_NAME):
        errors.append("Koyeb provider is not allowed by MCP_ALLOWED_PROVIDERS")

    if not is_environment_allowed(environment):
        errors.append(f"Environment '{environment}' is not allowed")

    return {
        "provider": PROVIDER_NAME,
        "environment": environment,
        "valid": len(errors) == 0,
        "errors": errors,
        "mode": "dry-run",
    }


def koyeb_generate_service_plan(
    repo_full_name,
    app_name,
    service_name,
    environment="staging",
    service_type="web",
    source="github",
):
    validation = koyeb_validate_request(environment=environment)

    planned_actions = [
        "create or link Koyeb app",
        "create or link Koyeb service",
        "configure service source",
        "configure environment variables",
        "create deployment after approval",
        "read deployment status and logs",
        "run healthcheck",
    ]

    if service_type == "worker":
        planned_actions[-1] = "run worker readiness check"

    return {
        "provider": PROVIDER_NAME,
        "repo_full_name": repo_full_name,
        "app_name": app_name,
        "service_name": service_name,
        "service_type": service_type,
        "source": source,
        "environment": environment,
        "validation": validation,
        "planned_actions": planned_actions,
        "approval_required": [
            "create app or service",
            "configure environment variables",
            "create deployment",
        ],
        "mode": "dry-run",
    }
