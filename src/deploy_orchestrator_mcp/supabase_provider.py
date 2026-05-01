from deploy_orchestrator_mcp.config import is_environment_allowed, is_provider_allowed


PROVIDER_NAME = "supabase"


def supabase_validate_request(environment="staging"):
    errors = []

    if not is_provider_allowed(PROVIDER_NAME):
        errors.append("Supabase provider is not allowed by MCP_ALLOWED_PROVIDERS")

    if not is_environment_allowed(environment):
        errors.append(f"Environment '{environment}' is not allowed")

    return {
        "provider": PROVIDER_NAME,
        "environment": environment,
        "valid": len(errors) == 0,
        "errors": errors,
        "mode": "dry-run",
    }


def supabase_generate_project_plan(project_name, environment="staging", needs_auth=False, needs_storage=False):
    validation = supabase_validate_request(environment=environment)

    planned_actions = [
        "create or link Supabase project",
        "configure database connection",
        "apply migrations after approval",
        "configure application environment variables",
        "run database healthcheck",
    ]

    if needs_auth:
        planned_actions.append("review and configure Supabase Auth settings")

    if needs_storage:
        planned_actions.append("review and configure Supabase Storage buckets")

    return {
        "provider": PROVIDER_NAME,
        "project_name": project_name,
        "environment": environment,
        "needs_auth": needs_auth,
        "needs_storage": needs_storage,
        "validation": validation,
        "planned_actions": planned_actions,
        "approval_required": [
            "create project",
            "apply migrations",
            "set application environment variables",
            "configure auth or storage",
        ],
        "secrets_policy": [
            "never expose service role key",
            "only return public project URL and anon key metadata",
            "redact connection strings in logs",
        ],
        "mode": "dry-run",
    }
