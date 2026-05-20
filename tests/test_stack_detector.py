from deploy_orchestrator_mcp.stack_detector import detect_stack


# ---------------------------------------------------------------------------
# Runtime detection
# ---------------------------------------------------------------------------


def test_detects_python_from_pyproject():
    result = detect_stack(["pyproject.toml", "src/main.py"])
    assert result["runtime"] == "python"


def test_detects_python_from_requirements():
    result = detect_stack(["requirements.txt", "app.py"])
    assert result["runtime"] == "python"


def test_detects_node_from_package_json():
    result = detect_stack(["package.json", "index.js"])
    assert result["runtime"] == "node"


def test_detects_java_from_pom():
    result = detect_stack(["pom.xml", "src/Main.java"])
    assert result["runtime"] == "java"


def test_detects_java_from_gradle():
    result = detect_stack(["build.gradle", "src/Main.java"])
    assert result["runtime"] == "java"


def test_detects_go_from_go_mod():
    result = detect_stack(["go.mod", "main.go"])
    assert result["runtime"] == "go"


# ---------------------------------------------------------------------------
# Stack flags
# ---------------------------------------------------------------------------


def test_detects_dockerfile():
    result = detect_stack(["Dockerfile", "package.json"])
    assert result["has_dockerfile"] is True


def test_detects_database_from_prisma():
    result = detect_stack(["package.json", "prisma/schema.prisma"])
    assert result["needs_database"] is True


def test_detects_database_from_alembic():
    result = detect_stack(["pyproject.toml", "alembic.ini"])
    assert result["needs_database"] is True


def test_detects_supabase_from_config():
    result = detect_stack(["package.json", "supabase/config.toml"])
    assert result["needs_supabase"] is True
    assert result["needs_database"] is True


def test_detects_supabase_from_any_supabase_dir():
    result = detect_stack(["package.json", "supabase/migrations/001.sql"])
    assert result["needs_supabase"] is True


def test_preserves_repo_full_name():
    result = detect_stack(["pyproject.toml"], repo_full_name="owner/repo")
    assert result["repo_full_name"] == "owner/repo"


# ---------------------------------------------------------------------------
# Frontend detection
# ---------------------------------------------------------------------------


def test_detects_vite_frontend():
    result = detect_stack(["package.json", "vite.config.ts", "src/main.tsx"])
    assert result["is_frontend"] is True
    assert result["frontend_framework"] == "vite"
    assert result["frontend"]["framework"] == "vite"
    assert result["frontend"]["output_dir"] == "dist"
    assert "vercel" in result["frontend"]["recommended_providers"]


def test_detects_nextjs_frontend():
    result = detect_stack(["package.json", "next.config.mjs", "pages/index.tsx"])
    assert result["is_frontend"] is True
    assert result["frontend_framework"] == "nextjs"
    assert result["frontend"]["framework"] == "nextjs"
    assert result["frontend"]["output_dir"] is None
    assert result["frontend"]["recommended_providers"] == ["vercel"]


def test_node_without_frontend_config_is_not_frontend():
    result = detect_stack(["package.json", "index.js"])
    assert result["is_frontend"] is False
    assert result["frontend_framework"] is None


def test_vite_takes_precedence_over_nextjs():
    result = detect_stack(["package.json", "vite.config.ts", "next.config.js"])
    assert result["frontend_framework"] == "vite"


# ---------------------------------------------------------------------------
# Framework detection
# ---------------------------------------------------------------------------


def test_detects_python_http_service_framework():
    result = detect_stack(["pyproject.toml", "render.yaml"])
    assert result["framework"] == "python-http-service"
