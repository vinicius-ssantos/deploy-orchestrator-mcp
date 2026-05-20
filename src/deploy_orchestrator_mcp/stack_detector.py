from typing import TypedDict


class FrontendProfile(TypedDict):
    is_frontend: bool
    framework: str | None
    build_command: str | None
    output_dir: str | None
    recommended_providers: list[str]


class StackProfile(TypedDict):
    runtime: str
    framework: str | None
    has_dockerfile: bool
    needs_database: bool
    needs_supabase: bool
    is_frontend: bool
    frontend_framework: str | None
    repo_full_name: str | None
    frontend: FrontendProfile


def _detect_frontend(names: set[str]) -> FrontendProfile:
    if "package.json" not in names:
        return {
            "is_frontend": False,
            "framework": None,
            "build_command": None,
            "output_dir": None,
            "recommended_providers": [],
        }

    if "vite.config.ts" in names or "vite.config.js" in names:
        return {
            "is_frontend": True,
            "framework": "vite",
            "build_command": "npm run build",
            "output_dir": "dist",
            "recommended_providers": ["vercel", "netlify", "cloudflare_pages"],
        }

    if "next.config.js" in names or "next.config.ts" in names or "next.config.mjs" in names:
        return {
            "is_frontend": True,
            "framework": "nextjs",
            "build_command": "npm run build",
            "output_dir": None,
            "recommended_providers": ["vercel"],
        }

    return {
        "is_frontend": False,
        "framework": None,
        "build_command": None,
        "output_dir": None,
        "recommended_providers": [],
    }


def detect_stack(files: list[str], repo_full_name: str | None = None) -> StackProfile:
    names = set(files)

    runtime = "unknown"
    framework = None

    if "pyproject.toml" in names or "requirements.txt" in names:
        runtime = "python"
    elif "package.json" in names:
        runtime = "node"
    elif "pom.xml" in names or "build.gradle" in names:
        runtime = "java"
    elif "go.mod" in names:
        runtime = "go"

    if "pyproject.toml" in names and "render.yaml" in names:
        framework = "python-http-service"

    needs_database = any(
        name in names
        for name in [
            "prisma/schema.prisma",
            "alembic.ini",
            "supabase/config.toml",
            "docker-compose.yml",
        ]
    )
    needs_supabase = any(name.startswith("supabase/") for name in names)
    frontend = _detect_frontend(names)

    return {
        "runtime": runtime,
        "framework": framework,
        "has_dockerfile": "Dockerfile" in names,
        "needs_database": needs_database,
        "needs_supabase": needs_supabase,
        "is_frontend": frontend["is_frontend"],
        "frontend_framework": frontend["framework"],
        "repo_full_name": repo_full_name,
        "frontend": frontend,
    }
