from deploy_orchestrator_mcp.config import is_environment_allowed, is_provider_allowed


PROVIDER_NAME = "render"


def render_validate_request(environment="staging"):
    errors = []

    if not is_provider_allowed(PROVIDER_NAME):
        errors.append("Render provider is not allowed by MCP_ALLOWED_PROVIDERS")

    if not is_environment_allowed(environment):
        errors.append(f"Environment '{environment}' is not allowed")

    return {
        "provider": PROVIDER_NAME,
        "environment": environment,
        "valid": len(errors) == 0,
        "errors": errors,
        "mode": "dry-run",
    }


def render_generate_service_plan(repo_full_name, service_name, environment="staging"):
    validation = render_validate_request(environment=environment)

    return {
        "provider": PROVIDER_NAME,
        "repo_full_name": repo_full_name,
        "service_name": service_name,
        "environment": environment,
        "validation": validation,
        "planned_actions": [
            "create or link Render web service",
            "configure environment variables",
            "connect GitHub repository branch",
            "trigger deploy after approval",
            "read deploy status and logs",
            "run healthcheck",
        ],
        "approval_required": [
            "create service",
            "set environment variables",
            "trigger deployment",
        ],
        "mode": "dry-run",
    }
