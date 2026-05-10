from deploy_orchestrator_mcp.analyzer import analyze_file_list


# ---------------------------------------------------------------------------
# Runtime detection
# ---------------------------------------------------------------------------


def test_detects_python_from_pyproject():
    result = analyze_file_list(["pyproject.toml", "src/main.py"])
    assert result["runtime"] == "python"


def test_detects_python_from_requirements():
    result = analyze_file_list(["requirements.txt", "app.py"])
    assert result["runtime"] == "python"


def test_detects_node_from_package_json():
    result = analyze_file_list(["package.json", "index.js"])
    assert result["runtime"] == "node"


def test_detects_java_from_pom():
    result = analyze_file_list(["pom.xml", "src/Main.java"])
    assert result["runtime"] == "java"


def test_detects_java_from_gradle():
    result = analyze_file_list(["build.gradle", "src/Main.java"])
    assert result["runtime"] == "java"


def test_detects_go_from_go_mod():
    result = analyze_file_list(["go.mod", "main.go"])
    assert result["runtime"] == "go"


def test_unknown_runtime_for_unrecognized_files():
    result = analyze_file_list(["README.md", "Makefile"])
    assert result["runtime"] == "unknown"


# ---------------------------------------------------------------------------
# Dockerfile and database detection
# ---------------------------------------------------------------------------


def test_detects_dockerfile():
    result = analyze_file_list(["Dockerfile", "package.json"])
    assert result["has_dockerfile"] is True


def test_no_dockerfile():
    result = analyze_file_list(["pyproject.toml"])
    assert result["has_dockerfile"] is False


def test_detects_database_from_prisma():
    result = analyze_file_list(["package.json", "prisma/schema.prisma"])
    assert result["needs_database"] is True


def test_detects_database_from_alembic():
    result = analyze_file_list(["pyproject.toml", "alembic.ini"])
    assert result["needs_database"] is True


def test_detects_supabase_from_config():
    result = analyze_file_list(["package.json", "supabase/config.toml"])
    assert result["needs_supabase"] is True


def test_detects_supabase_from_any_supabase_dir():
    result = analyze_file_list(["package.json", "supabase/migrations/001.sql"])
    assert result["needs_supabase"] is True


def test_no_database_needed():
    result = analyze_file_list(["pyproject.toml", "README.md"])
    assert result["needs_database"] is False
    assert result["needs_supabase"] is False


# ---------------------------------------------------------------------------
# Frontend detection — not a frontend
# ---------------------------------------------------------------------------


def test_non_frontend_python_project():
    result = analyze_file_list(["pyproject.toml", "src/main.py"])
    assert result["frontend"]["is_frontend"] is False
    assert result["frontend"]["framework"] is None


def test_node_without_vite_or_next_not_frontend():
    result = analyze_file_list(["package.json", "index.js"])
    assert result["frontend"]["is_frontend"] is False


def test_no_package_json_not_frontend():
    result = analyze_file_list(["go.mod", "main.go"])
    assert result["frontend"]["is_frontend"] is False


# ---------------------------------------------------------------------------
# Frontend detection — Vite
# ---------------------------------------------------------------------------


def test_detects_vite_ts_config():
    result = analyze_file_list(["package.json", "vite.config.ts", "src/main.tsx"])
    fe = result["frontend"]
    assert fe["is_frontend"] is True
    assert fe["framework"] == "vite"
    assert fe["build_command"] == "npm run build"
    assert fe["output_dir"] == "dist"
    assert "vercel" in fe["recommended_providers"]


def test_detects_vite_js_config():
    result = analyze_file_list(["package.json", "vite.config.js", "src/main.jsx"])
    fe = result["frontend"]
    assert fe["is_frontend"] is True
    assert fe["framework"] == "vite"


def test_vite_recommended_providers_include_netlify_and_cf():
    result = analyze_file_list(["package.json", "vite.config.ts"])
    providers = result["frontend"]["recommended_providers"]
    assert "vercel" in providers
    assert "netlify" in providers
    assert "cloudflare_pages" in providers


# ---------------------------------------------------------------------------
# Frontend detection — Next.js
# ---------------------------------------------------------------------------


def test_detects_nextjs_js_config():
    result = analyze_file_list(["package.json", "next.config.js", "pages/index.tsx"])
    fe = result["frontend"]
    assert fe["is_frontend"] is True
    assert fe["framework"] == "nextjs"
    assert fe["build_command"] == "npm run build"
    assert fe["output_dir"] is None
    assert "vercel" in fe["recommended_providers"]


def test_detects_nextjs_ts_config():
    result = analyze_file_list(["package.json", "next.config.ts"])
    fe = result["frontend"]
    assert fe["is_frontend"] is True
    assert fe["framework"] == "nextjs"


def test_detects_nextjs_mjs_config():
    result = analyze_file_list(["package.json", "next.config.mjs"])
    fe = result["frontend"]
    assert fe["is_frontend"] is True
    assert fe["framework"] == "nextjs"


def test_nextjs_recommended_providers_only_vercel():
    result = analyze_file_list(["package.json", "next.config.js"])
    providers = result["frontend"]["recommended_providers"]
    assert "vercel" in providers


# ---------------------------------------------------------------------------
# Vite takes precedence over Next.js if both configs present
# ---------------------------------------------------------------------------


def test_vite_takes_precedence_over_nextjs():
    result = analyze_file_list(["package.json", "vite.config.ts", "next.config.js"])
    assert result["frontend"]["framework"] == "vite"


# ---------------------------------------------------------------------------
# Output structure completeness
# ---------------------------------------------------------------------------


def test_frontend_key_always_present():
    for files in [
        ["pyproject.toml"],
        ["package.json"],
        ["package.json", "vite.config.ts"],
        ["go.mod"],
    ]:
        result = analyze_file_list(files)
        assert "frontend" in result
        assert "is_frontend" in result["frontend"]
        assert "framework" in result["frontend"]
        assert "recommended_providers" in result["frontend"]


def test_detected_files_sorted():
    files = ["z.txt", "a.txt", "m.txt"]
    result = analyze_file_list(files)
    assert result["detected_files"] == sorted(files)
