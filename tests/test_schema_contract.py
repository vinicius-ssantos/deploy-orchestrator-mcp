"""Schema contract tests: verify MCP inputSchema matches tool signatures.

These tests guard against the class of regression where a Python type change
(e.g. adding a dict param) does not propagate to the MCP manifest exposed to
clients. Bare dict/object params with no declared properties are unusable by
MCP clients and must never appear in public tools.
"""

import asyncio

import pytest

from deploy_orchestrator_mcp.server import mcp


@pytest.fixture(scope="module")
def mcp_tools():
    tools = asyncio.run(mcp.list_tools())
    return {t.name: t.to_mcp_tool() for t in tools}


# ---------------------------------------------------------------------------
# Guard: no bare dict params
# ---------------------------------------------------------------------------


def test_no_bare_object_params(mcp_tools):
    """No tool may expose a bare {type: object} param without declared properties.

    FastMCP generates this for Python `dict` params. It gives MCP clients no
    schema to fill, making the parameter unusable. All structured inputs must
    either use primitive fields or accept a JSON string.
    """
    violations = []
    for tool_name, tool in mcp_tools.items():
        for param_name, prop in (tool.inputSchema.get("properties") or {}).items():
            is_bare_object = (
                prop.get("type") == "object"
                and not prop.get("properties")
                and not prop.get("additionalProperties")
            )
            # anyOf variants: {"anyOf": [{"type": "object"}, {"type": "null"}]}
            for variant in prop.get("anyOf", []):
                if (
                    variant.get("type") == "object"
                    and not variant.get("properties")
                    and not variant.get("additionalProperties")
                ):
                    is_bare_object = True
            if is_bare_object:
                violations.append(f"{tool_name}.{param_name}")

    assert violations == [], (
        f"Bare dict/object params found in MCP schema (unusable by clients): {violations}\n"
        "Fix: expose primitive fields or use a JSON string param instead."
    )


# ---------------------------------------------------------------------------
# Specific contract assertions per tool
# ---------------------------------------------------------------------------


def test_render_deploy_staging_ci_gate_fields(mcp_tools):
    """render_deploy_staging must expose primitive ci_gate fields, not ci_gate: dict."""
    props = mcp_tools["render_deploy_staging"].inputSchema.get("properties", {})
    assert "ci_gate_allowed" in props, "ci_gate_allowed missing from render_deploy_staging"
    assert "ci_gate_head_sha" in props, "ci_gate_head_sha missing from render_deploy_staging"
    assert "ci_gate" not in props, "bare ci_gate dict must not appear in render_deploy_staging"


def test_run_staging_migration_ci_gate_fields(mcp_tools):
    """run_staging_migration must expose primitive ci_gate fields, not ci_gate: dict."""
    props = mcp_tools["run_staging_migration"].inputSchema.get("properties", {})
    assert "ci_gate_allowed" in props, "ci_gate_allowed missing from run_staging_migration"
    assert "ci_gate_head_sha" in props, "ci_gate_head_sha missing from run_staging_migration"
    assert "ci_gate_reason" in props, "ci_gate_reason missing from run_staging_migration"
    assert "ci_gate_checked_at" in props, "ci_gate_checked_at missing from run_staging_migration"
    assert "ci_gate" not in props, "bare ci_gate dict must not appear in run_staging_migration"


def test_policy_evaluate_no_dict_param(mcp_tools):
    """policy_evaluate must not expose policy: dict — use policy_json: str instead."""
    props = mcp_tools["policy_evaluate"].inputSchema.get("properties", {})
    assert "policy" not in props, "bare policy dict must not appear in policy_evaluate"
    assert "policy_json" in props, "policy_json string param missing from policy_evaluate"


def test_render_run_task_no_dict_param(mcp_tools):
    """render_run_task must not expose input_data: dict|list — use input_data_json: str."""
    props = mcp_tools["render_run_task"].inputSchema.get("properties", {})
    assert "input_data" not in props, "bare input_data dict must not appear in render_run_task"
    assert "input_data_json" in props, "input_data_json string param missing from render_run_task"


def test_run_staging_migration_no_dict_params(mcp_tools):
    """run_staging_migration must not expose policy: dict or input_data: dict|list."""
    props = mcp_tools["run_staging_migration"].inputSchema.get("properties", {})
    assert "policy" not in props, "bare policy dict must not appear in run_staging_migration"
    assert "input_data" not in props, "bare input_data must not appear in run_staging_migration"
    assert "policy_json" in props, "policy_json missing from run_staging_migration"
    assert "input_data_json" in props, "input_data_json missing from run_staging_migration"


def test_vercel_deploy_preview_ci_gate_fields(mcp_tools):
    """vercel_deploy_preview must expose primitive ci_gate fields, not ci_gate: dict|bool."""
    props = mcp_tools["vercel_deploy_preview"].inputSchema.get("properties", {})
    assert "ci_gate" not in props, "bare/union ci_gate must not appear in vercel_deploy_preview"
    assert "ci_gate_allowed" in props, "ci_gate_allowed missing from vercel_deploy_preview"
    assert "ci_gate_head_sha" in props, "ci_gate_head_sha missing from vercel_deploy_preview"
    assert "ci_gate_reason" in props, "ci_gate_reason missing from vercel_deploy_preview"


def test_supabase_create_project_ci_gate_fields(mcp_tools):
    """supabase_create_project must expose primitive ci_gate fields, not ci_gate: dict."""
    props = mcp_tools["supabase_create_project"].inputSchema.get("properties", {})
    assert "ci_gate" not in props, "bare ci_gate dict must not appear in supabase_create_project"
    assert "ci_gate_allowed" in props, "ci_gate_allowed missing from supabase_create_project"
    assert "ci_gate_head_sha" in props, "ci_gate_head_sha missing from supabase_create_project"
    assert "policy_json" in props, "policy_json missing from supabase_create_project"


def test_supabase_apply_migration_ci_gate_fields(mcp_tools):
    """supabase_apply_migration must expose primitive ci_gate fields, not ci_gate: dict."""
    props = mcp_tools["supabase_apply_migration"].inputSchema.get("properties", {})
    assert "ci_gate" not in props, "bare ci_gate dict must not appear in supabase_apply_migration"
    assert "ci_gate_allowed" in props, "ci_gate_allowed missing from supabase_apply_migration"
    assert "ci_gate_head_sha" in props, "ci_gate_head_sha missing from supabase_apply_migration"
    assert "policy_json" in props, "policy_json missing from supabase_apply_migration"


# ---------------------------------------------------------------------------
# Sanity: required tools are present in the manifest
# ---------------------------------------------------------------------------


EXPECTED_TOOLS = [
    "render_deploy_staging",
    "render_get_deploy_status",
    "render_list_services",
    "render_rollback_staging",
    "render_get_build_logs",
    "render_get_runtime_logs",
    "render_healthcheck",
    "render_run_task",
    "run_staging_migration",
    "audit_log_status",
    "audit_log_list",
    "policy_evaluate",
    "policy_load",
    "github_prepare_plan_report",
    "server_auth_status",
    "credentials_status",
    "supabase_create_project",
    "supabase_apply_migration",
    "vercel_validate_credentials",
    "vercel_project_plan",
    "vercel_deploy_preview",
    "vercel_get_deploy_status",
]


def test_expected_tools_present(mcp_tools):
    """All known public tools must appear in the MCP manifest."""
    missing = [name for name in EXPECTED_TOOLS if name not in mcp_tools]
    assert missing == [], f"Tools missing from MCP manifest: {missing}"
