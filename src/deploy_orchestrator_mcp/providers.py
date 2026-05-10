APP_PROVIDERS = {
    "render": {
        "kind": "app",
        "supports_docker": True,
        "supports_git_deploy": True,
        "supports_env_vars": True,
        "supports_logs": True,
        "supports_rollback": True,
        "best_for": ["python", "fastmcp", "http-api", "mvp"],
    },
    "railway": {
        "kind": "app",
        "supports_docker": True,
        "supports_git_deploy": True,
        "supports_env_vars": True,
        "supports_logs": True,
        "supports_rollback": True,
        "best_for": ["node", "python", "java", "postgres", "mvp"],
    },
    "fly": {
        "kind": "app",
        "supports_docker": True,
        "supports_git_deploy": False,
        "supports_env_vars": True,
        "supports_logs": True,
        "supports_rollback": True,
        "best_for": ["docker", "sensitive-workloads", "private-networking"],
    },
    "koyeb": {
        "kind": "app",
        "supports_docker": True,
        "supports_git_deploy": True,
        "supports_env_vars": True,
        "supports_logs": True,
        "supports_rollback": True,
        "best_for": ["docker", "api", "worker", "autoscaling"],
    },
    "coolify": {
        "kind": "app",
        "supports_docker": True,
        "supports_git_deploy": True,
        "supports_env_vars": True,
        "supports_logs": True,
        "supports_rollback": True,
        "best_for": ["vps", "self-hosted", "docker-compose"],
    },
}

DATABASE_PROVIDERS = {
    "supabase": {
        "kind": "database-backend",
        "engine": "postgres",
        "supports_auth": True,
        "supports_storage": True,
        "supports_realtime": True,
        "supports_rls": True,
        "best_for": ["auth", "storage", "realtime", "rls", "managed-backend"],
    },
    "same-provider-postgres": {
        "kind": "database",
        "engine": "postgres",
        "supports_auth": False,
        "supports_storage": False,
        "supports_realtime": False,
        "supports_rls": False,
        "best_for": ["mvp", "simple-postgres"],
    },
}

FRONTEND_PROVIDERS = {
    "vercel": {
        "kind": "frontend-static",
        "supports_git_deploy": True,
        "supports_preview_deployments": True,
        "supports_staging_deployments": True,
        "supports_production_deployments": True,
        "supports_env_vars": True,
        "supports_build_logs": True,
        "best_for": ["vite", "react", "static-site", "preview", "dogfooding"],
    },
}


def list_provider_capabilities():
    return {
        "app_providers": APP_PROVIDERS,
        "database_providers": DATABASE_PROVIDERS,
        "frontend_providers": FRONTEND_PROVIDERS,
        "mode": "dry-run",
    }


def get_provider_capability(provider):
    if provider in APP_PROVIDERS:
        return APP_PROVIDERS[provider]
    if provider in DATABASE_PROVIDERS:
        return DATABASE_PROVIDERS[provider]
    if provider in FRONTEND_PROVIDERS:
        return FRONTEND_PROVIDERS[provider]
    return None
