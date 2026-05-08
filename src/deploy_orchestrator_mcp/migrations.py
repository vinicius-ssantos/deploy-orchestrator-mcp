"""Staging-first migration execution guardrails.

This module intentionally wraps Render Workflows task execution instead
of running migrations directly. Migrations are state-changing, so they
must pass policy, approval, CI and audit gates before any provider
task is triggered.
"""

from __future__ import annotations

from typing import Any

from deploy_orchestrator_mcp.audit import create_audit_event
from deploy_orchestrator_mcp.execution import APPROVAL_TOKEN, evaluate_execution_gate
from deploy_orchestrator_mcp.policy import DEFAULT_POLICY, evaluate_policy
from deploy_orchestrator_mcp.redaction import redact
from deploy_orchestrator_mcp.render_workflows import render_run_task


ALLOWED_MIGRATION_ENVIRONMENTS = {"staging"}


MIGRATION_APPROVAL_ACTIONS = ["apply migration"]



def _normalize_environment(environment: str) -> str:
    return (environment or "").strip().lower()



def _build_migration_plan(
    *,
    environment: str,
    app_provider: str,
    database_provider: str | None,
    policy: dict | None,
}) -> dict[str, Any]:
    policy_result = evaluate_policy(
        policy or DEFAULT_POLICY,
        environment=environment,
        app_provider=app_provider,
        database_provider=database_provider,
    )
    return {
        "environment": environment,
        "mode": "execute",
        "app_provider": app_provider,
        "database_provider": database_provider,
        "policy_result": policy_result,
        "approval_required": True,
        "approval_required_actions": MIGRATION_APPROVAL_ACTIONS,
    }



def _blocked_result(
    *,
    reasons: list[str],
    task_slug: str,
    environment: str,
    ci_gate: dict | None = None,
    gate_decision: dict | None = None,
) -> dict[str, Any]:
    audit_event = create_audit_event(
        "migration.execution.blocked",
        {
            "task_slug": task_slug,
            "environment": environment,
            "reasons": reasons,
            "ci_gate_allowed": (ci_gate or {}).get("allowed"),
            "ci_gate_head_sha": (ci_gate or {}).get("head_sha"),
            "execution_gate_allowed": (gate_decision or {}).get("allowed"),
        },
    )
    return redact(
        {
            "ok": False,
            "allowed": False,
            "errors": reasons,
            "task_slug": task_slug,
            "environment": environment,
            "ci_gate": ci_gate,
            "execution_gate": gate_decision,
            "audit_event": audit_event,
        }
    )



def run_staging_migration(
    *,
    task_slug: str,
    ci_gate: dict | None,
    approval: str | None = None,
    environment: str = "staging",
    app_provider: str = "render",
    database_provider: str | None = "supabase",
    policy: dict | None = None,
    input_data: dict | list | None = None,
    wait: bool = True,
) -> dict[str, Any]:
    """Run a staging-first migration task via Render Workflows.

    This tool is deliberately narrow: it only allows the staging
    environment, always requires approval="APPROVED", and always requires
    a passing CI gate before delegating to the Render Workflows task.
    """
    normalized_env = _normalize_environment(environment)
    reasons: list[str] = []

    if not task_slug or "/" not in task_slug:
        reasons.append('task_slug is required in "workflow-slug/task-name" format')

    if normalized_env not in ALLOWED_MIGRATION_ENVIRONMENTS:
        reasons.append("migrations must run in staging first")

    if approval != APPROVAL_TOKEN:
        reasons.append('migrations require approval="APPROVED"')

    plan = _build_migration_plan(
        environment=normalized_env,
        app_provider=app_provider,
        database_provider=database_provider,
        policy=policy,
    )
    gate_decision = evaluate_execution_gate(
        plan,
        approval=approval,
        mode="execute",
        ci_gate=ci_gate,
    )

    if not gate_decision["allowed"]:
        reasons.extend(gate_decision["reasons"])

    if reasons:
        return _blocked_result(
            reasons=reasons,
            task_slug=task_slug,
            environment=normalized_env,
            ci_gate=ci_gate,
            gate_decision=gate_decision,
        )

    audit_event = create_audit_event(
        "migration.execution.allowed",
        {
            "task_slug": task_slug,
            "environment": normalized_env,
            "ci_gate_allowed": (ci_gate or {}).get("allowed"),
            "ci_gate_head_sha": (ci_gate or {}).get("head_sha"),
        },
    )

    result = render_run_task(
        task_slug=task_slug,
        input_data=input_data,
        wait=wait,
        environment=normalized_env,
        approval=approval,
    )
    return redact(
        {
            "ok": result.get("ok", False) is True,
            "allowed": True,
            "task_slug": task_slug,
            "environment": normalized_env,
            "execution_gate": gate_decision,
            "result": result,
            "audit_event": audit_event,
        }
    )
