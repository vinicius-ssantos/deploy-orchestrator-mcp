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

    return {
        "runtime": runtime,
        "framework": framework,
        "has_dockerfile": has_dockerfile,
        "needs_database": needs_database,
        "needs_supabase": needs_supabase,
        "detected_files": sorted(files),
    }
