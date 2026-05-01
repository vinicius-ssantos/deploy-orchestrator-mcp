from deploy_orchestrator_mcp.fly_provider import fly_generate_app_plan
from deploy_orchestrator_mcp.policy import evaluate_policy
from deploy_orchestrator_mcp.railway_provider import railway_generate_service_plan
from deploy_orchestrator_mcp.render_provider import render_generate_service_plan
from deploy_orchestrator_mcp.recommender import recommend_app_provider, recommend_database_provider
from deploy_orchestrator_mcp.supabase_provider import supabase_generate_project_plan


def _service_name_from_analysis(analysis):
    if analysis.get("runtime") == "python":
        return "python-service"
    if analysis.get("runtime") == "node":
        return "node-service"
    if analysis.get("runtime") == "java":
        return "java-service"
    return "app-service"


def _build_provider_plan(analysis, app_provider, database_provider, environment):
    provider = app_provider["provider"]
    service_name = _service_name_from_analysis(analysis)
    repo_full_name = analysis.get("repo_full_name", "unknown/repository")

    if provider == "render":
        return render_generate_service_plan(
            repo_full_name=repo_full_name,
            service_name=service_name,
            environment=environment,
        )

    if provider == "railway":
        return railway_generate_service_plan(
            repo_full_name=repo_full_name,
            service_name=service_name,
            environment=environment,
            needs_postgres=database_provider is not None,
        )

    if provider == "fly":
        return fly_generate_app_plan(
            repo_full_name=repo_full_name,
            app_name=service_name,
            environment=environment,
            needs_volume=database_provider is not None,
        )

    return None


def _build_database_plan(analysis, database_provider, environment):
    if not database_provider:
        return None

    provider = database_provider["provider"]
    project_name = _service_name_from_analysis(analysis)

    if provider == "supabase":
        return supabase_generate_project_plan(
            project_name=project_name,
            environment=environment,
            needs_auth=True,
            needs_storage=True,
        )

    return None


def generate_deployment_plan(analysis, environment="staging", policy=None):
    app_provider = recommend_app_provider(analysis)
    database_provider = recommend_database_provider(analysis)
    provider_plan = _build_provider_plan(analysis, app_provider, database_provider, environment)
    database_plan = _build_database_plan(analysis, database_provider, environment)
    policy_result = evaluate_policy(
        policy=policy,
        environment=environment,
        app_provider=app_provider["provider"],
        database_provider=database_provider["provider"] if database_provider else None,
    )

    steps = [
        "Review repository analysis",
        "Confirm selected environment",
        "Evaluate repository deployment policy",
        "Prepare provider configuration",
        "Configure required environment variables",
        "Run CI before deployment",
        "Trigger deployment after approval",
        "Run healthcheck after deployment",
    ]

    approval_required = [
        "create service",
        "set environment variables",
        "trigger deployment",
    ]

    if database_provider:
        steps.insert(4, "Provision database or backend provider")
        approval_required.append("create database")

    risks = []
    if environment == "production":
        risks.append("Production deployment requires explicit approval")
    if analysis.get("runtime") == "unknown":
        risks.append("Runtime could not be detected with confidence")
    if not policy_result["valid"]:
        risks.append("Repository policy validation failed")

    return {
        "environment": environment,
        "app_provider": app_provider,
        "database_provider": database_provider,
        "provider_plan": provider_plan,
        "database_plan": database_plan,
        "policy_result": policy_result,
        "steps": steps,
        "approval_required": approval_required,
        "risks": risks,
        "mode": "dry-run",
    }
