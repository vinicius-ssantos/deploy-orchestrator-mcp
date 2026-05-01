from deploy_orchestrator_mcp.recommender import recommend_app_provider, recommend_database_provider


def generate_deployment_plan(analysis, environment="staging"):
    app_provider = recommend_app_provider(analysis)
    database_provider = recommend_database_provider(analysis)

    steps = [
        "Review repository analysis",
        "Confirm selected environment",
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
        steps.insert(3, "Provision database or backend provider")
        approval_required.append("create database")

    risks = []
    if environment == "production":
        risks.append("Production deployment requires explicit approval")
    if analysis.get("runtime") == "unknown":
        risks.append("Runtime could not be detected with confidence")

    return {
        "environment": environment,
        "app_provider": app_provider,
        "database_provider": database_provider,
        "steps": steps,
        "approval_required": approval_required,
        "risks": risks,
        "mode": "dry-run",
    }
