def recommend_app_provider(analysis):
    runtime = analysis.get("runtime", "unknown")
    has_dockerfile = analysis.get("has_dockerfile", False)

    if has_dockerfile:
        return {
            "provider": "fly",
            "score": 85,
            "reasons": ["Dockerfile detected", "Fly.io is strong for container workloads"],
        }

    if runtime == "python":
        return {
            "provider": "render",
            "score": 88,
            "reasons": ["Python service detected", "Render is a good fit for HTTP MCP services"],
        }

    if runtime == "node":
        return {
            "provider": "railway",
            "score": 84,
            "reasons": ["Node app detected", "Railway is a good fit for fast app deployments"],
        }

    if runtime == "java":
        return {
            "provider": "railway",
            "score": 80,
            "reasons": ["Java app detected", "Railway is a good first target for JVM APIs"],
        }

    return {
        "provider": "render",
        "score": 60,
        "reasons": ["Unknown runtime", "Render is selected as conservative default"],
    }


def recommend_database_provider(analysis):
    if analysis.get("needs_supabase", False):
        return {
            "provider": "supabase",
            "score": 92,
            "reasons": ["Supabase-specific needs detected", "Auth, Storage, Realtime or RLS may be needed"],
        }

    if analysis.get("needs_database", False):
        return {
            "provider": "same-provider-postgres",
            "score": 78,
            "reasons": ["Database need detected", "Same-provider Postgres is simple for MVP deployments"],
        }

    return None
