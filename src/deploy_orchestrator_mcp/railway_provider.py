from deploy_orchestrator_mcp.config import is_environment_allowed, is_provider_allowed


PROVIDER_NAME = "railway"


def railway_validate_request(environment="staging"):
    errors = []

    if not is_provider_allowed(PROVIDER_NAME):
        errors.append("Railway provider is not allowed by MCP_ALLOWED_PROVIDERS")

    if not is_environment_allowed(environment):
        errors.append(f"Environment '{environment}' is not allowed")

    return {
        "provider": PROVIDER_NAME,
        "environment": environment,
        "valid": len(errors) == 0,
        "errors": errors,
        "mode": "dry-run",
    }


def railway_generate_service_plan(repo_full_name, service_name, environment="staging", needs_postgres=False):
    validation = railway_validate_request(environment=environment)

    planned_actions = [
        "create or link Railway project",
        "create or link Railway service",
        "connect GitHub repository branch",
        "configure environment variables",
        "trigger deploy after approval",
        "read deployment status and logs",
        "run healthcheck",
    ]

    approval_required = [
        "create project or service",
        "set environment variables",
        "trigger deployment",
    ]

    if needs_postgres:
        planned_actions.insert(2, "provision Railway Postgres service")
        approval_required.append("create postgres service")

    return {
        "provider": PROVIDER_NAME,
        "repo_full_name": repo_full_name,
        "service_name": service_name,
        "environment": environment,
        "needs_postgres": needs_postgres,
        "validation": validation,
        "planned_actions": planned_actions,
        "approval_required": approval_required,
        "mode": "dry-run",
    }


def railway_generate_postgres_plan(project_name, environment="staging"):
    validation = railway_validate_request(environment=environment)

    return {
        "provider": PROVIDER_NAME,
        "project_name": project_name,
        "database": "postgres",
        "environment": environment,
        "validation": validation,
        "planned_actions": [
            "create Railway Postgres service",
            "link DATABASE_URL to app service",
            "run migrations after approval",
            "run database healthcheck",
        ],
        "approval_required": [
            "create postgres service",
            "set DATABASE_URL",
            "apply migrations",
        ],
        "mode": "dry-run",
    }
