import os


def _split_csv(value):
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def get_settings():
    return {
        "read_only": os.getenv("MCP_READ_ONLY", "true").lower() == "true",
        "require_confirmation": os.getenv("MCP_REQUIRE_CONFIRMATION", "true").lower() == "true",
        "allowed_repos": _split_csv(os.getenv("MCP_ALLOWED_REPOS", "")),
        "allowed_environments": _split_csv(os.getenv("MCP_ALLOWED_ENVIRONMENTS", "preview,staging")),
        "allowed_providers": _split_csv(os.getenv("MCP_ALLOWED_PROVIDERS", "render,railway,supabase")),
    }


def is_repo_allowed(repo_full_name):
    settings = get_settings()
    allowed = settings["allowed_repos"]
    return not allowed or repo_full_name in allowed


def is_environment_allowed(environment):
    return environment in get_settings()["allowed_environments"]


def is_provider_allowed(provider):
    return provider in get_settings()["allowed_providers"]
