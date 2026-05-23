from unittest.mock import patch

from deploy_orchestrator_mcp.execution import APPROVAL_TOKEN
from deploy_orchestrator_mcp.migrations import run_staging_migration


def valid_ci_gate(head_sha="abc123"):
    return {
        "allowed": True,
        "blocking_checks": [],
        "summary": "All workflows succeeded",
        "head_sha": head_sha,
        "checked_at": "2026-05-08T12:00:00Z",
    }


def test_migration_blocks_without_task_slug():
    result = run_staging_migration(
        task_slug="",
        ci_gate=valid_ci_gate(),
        approval=APPROVAL_TOKEN,
    )

    assert result["ok"] is False
    assert any("task_slug" in error for error in result["errors"])
    assert result["audit_event"]["type"] == "migration.execution.blocked"


def test_migration_blocks_non_staging_environment():
    result = run_staging_migration(
        task_slug="deploy/migrate",
        ci_gate=valid_ci_gate(),
        approval=APPROVAL_TOKEN,
        environment="production",
    )

    assert result["ok"] is False
    assert "migrations must run in staging first" in result["errors"]


def test_migration_blocks_without_explicit_approval():
    result = run_staging_migration(
        task_slug="deploy/migrate",
        ci_gate=valid_ci_gate(),
        approval=None,
    )

    assert result["ok"] is False
    assert 'migrations require approval="APPROVED"' in result["errors"]


def test_migration_blocks_without_ci_gate():
    result = run_staging_migration(
        task_slug="deploy/migrate",
        ci_gate=None,
        approval=APPROVAL_TOKEN,
    )

    assert result["ok"] is False
    assert "ci_gate is required for execute mode" in result["errors"]


def test_migration_blocks_when_ci_gate_denies():
    result = run_staging_migration(
        task_slug="deploy/migrate",
        ci_gate={
            "allowed": False,
            "blocking_checks": ["test"],
            "summary": "tests failed",
            "head_sha": "abc123",
        },
        approval=APPROVAL_TOKEN,
    )

    assert result["ok"] is False
    assert any("CI gate blocked" in error for error in result["errors"])


def test_migration_blocks_policy_failure():
    policy = {
        "version": 1,
        "allowed_environments": ["preview"],
        "allowed_app_providers": ["render"],
        "allowed_database_providers": ["supabase"],
        "production": {"allowed": False, "requires_approval": True},
        "rules": {},
    }

    result = run_staging_migration(
        task_slug="deploy/migrate",
        ci_gate=valid_ci_gate(),
        approval=APPROVAL_TOKEN,
        policy=policy,
    )

    assert result["ok"] is False
    assert "policy validation failed" in result["errors"]


def test_migration_allowed_delegates_to_render_workflow():
    workflow_result = {
        "ok": True,
        "task_slug": "deploy/migrate",
        "task_run": {"id": "tr_123", "status": "succeeded"},
    }

    with patch(
        "deploy_orchestrator_mcp.migrations.render_run_task",
        return_value=workflow_result,
    ) as mock_run_task:
        result = run_staging_migration(
            task_slug="deploy/migrate",
            ci_gate=valid_ci_gate("sha-123"),
            approval=APPROVAL_TOKEN,
            input_data={"command": "npx prisma migrate deploy"},
            wait=False,
        )

    mock_run_task.assert_called_once_with(
        task_slug="deploy/migrate",
        input_data={"command": "npx prisma migrate deploy"},
        wait=False,
        environment="staging",
        approval=APPROVAL_TOKEN,
    )
    assert result["ok"] is True
    assert result["allowed"] is True
    assert result["result"] == workflow_result
    assert result["audit_event"]["type"] == "migration.execution.allowed"


def test_migration_result_is_redacted():
    workflow_result = {
        "ok": True,
        "task_run": {
            "id": "tr_secret",
            "output": "postgresql://user:password@example.supabase.co/db",
        },
    }

    with patch(
        "deploy_orchestrator_mcp.migrations.render_run_task",
        return_value=workflow_result,
    ):
        result = run_staging_migration(
            task_slug="deploy/migrate",
            ci_gate=valid_ci_gate(),
            approval=APPROVAL_TOKEN,
        )

    assert "password" not in str(result).lower()
