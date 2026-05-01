from deploy_orchestrator_mcp.config import is_environment_allowed, is_provider_allowed


PROVIDER_NAME = "coolify"


def coolify_validate_request(environment="staging"):
    errors = []

    if not is_provider_allowed(PROVIDER_NAME):
        errors.append("Coolify provider is not allowed by MCP_ALLOWED_PROVIDERS")

    if not is_environment_allowed(environment):
        errors.append(f"Environment '{environment}' is not allowed")

    return {
        "provider": PROVIDER_NAME,
        "environment": environment,
        "valid": len(errors) == 0,
        "errors": errors,
        "mode": "dry-run",
    }


def coolify_generate_app_plan(
    repo_full_name,
    project_name,
    app_name,
    environment="staging",
    deployment_method="github-app",
    needs_database=False,
    enable_preview=False,
):
    validation = coolify_validate_request(environment=environment)

    planned_actions = [
        "create or link Coolify project",
        "create or link application resource",
        "configure source repository",
        "configure build and runtime variables",
        "configure domain or generated URL",
        "trigger deployment after approval",
        "read deployment status and logs",
        "run healthcheck",
    ]

    approval_required = [
        "create project or application",
        "configure variables",
        "trigger deployment",
    ]

    if needs_database:
        planned_actions.insert(2, "create or link database/service resource")
        approval_required.append("create database or service resource")

    if enable_preview:
        planned_actions.insert(5, "configure pull request preview deployments")
        approval_required.append("enable preview deployments")

    return {
        "provider": PROVIDER_NAME,
        "repo_full_name": repo_full_name,
        "project_name": project_name,
        "app_name": app_name,
        "environment": environment,
        "deployment_method": deployment_method,
        "needs_database": needs_database,
        "enable_preview": enable_preview,
        "validation": validation,
        "planned_actions": planned_actions,
        "approval_required": approval_required,
        "mode": "dry-run",
    }


def coolify_generate_database_plan(project_name, database_name, engine="postgres", environment="staging"):
    validation = coolify_validate_request(environment=environment)

    return {
        "provider": PROVIDER_NAME,
        "project_name": project_name,
        "database_name": database_name,
        "engine": engine,
        "environment": environment,
        "validation": validation,
        "planned_actions": [
            "create database resource",
            "link database variables to application",
            "configure backup policy",
            "run database healthcheck",
        ],
        "approval_required": [
            "create database resource",
            "link database variables",
            "apply migrations",
        ],
        "mode": "dry-run",
    }
