def _detect_frontend(names: set) -> dict:
    if "package.json" not in names:
        return {"is_frontend": False, "framework": None, "build_command": None, "output_dir": None, "recommended_providers": []}

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

    return {"is_frontend": False, "framework": None, "build_command": None, "output_dir": None, "recommended_providers": []}


def analyze_file_list(files):
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

    has_dockerfile = "Dockerfile" in names

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

    if "pyproject.toml" in names and "render.yaml" in names:
        framework = "python-http-service"

    frontend = _detect_frontend(names)

    return {
        "runtime": runtime,
        "framework": framework,
        "has_dockerfile": has_dockerfile,
        "needs_database": needs_database,
        "needs_supabase": needs_supabase,
        "frontend": frontend,
        "detected_files": sorted(files),
    }
