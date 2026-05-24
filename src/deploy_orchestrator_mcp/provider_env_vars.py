"""Safety helpers for provider environment-variable writes."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from deploy_orchestrator_mcp.audit import create_audit_event
from deploy_orchestrator_mcp.execution import evaluate_execution_gate
from deploy_orchestrator_mcp.redaction import redact

VARIABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def safe_variable_names(variables: Mapping[str, Any] | None) -> list[str]:
    return sorted(str(key) for key in (variables or {}).keys())


def validate_variables(variables: Mapping[str, Any] | None) -> list[str]:
    if not variables:
        return ["variables must contain at least one key"]
    invalid = [name for name in safe_variable_names(variables) if not VARIABLE_NAME_RE.match(name)]
    if invalid:
        return [f"invalid variable names: {', '.join(invalid)}"]
    return []


def env_write_gate(provider: str, *, approval: str | bool | None, ci_gate: dict[str, Any] | None) -> dict[str, Any]:
    plan = {
        "provider": provider,
        "environment": "staging",
        "mode": "execute",
        "approval_required": True,
        "approval_required_actions": ["set environment variables"],
    }
    return evaluate_execution_gate(plan, approval=approval, mode="execute", ci_gate=ci_gate)


def blocked_env_result(
    provider: str,
    *,
    operation: str,
    reason: str,
    service_id: str,
    variable_names: list[str],
    errors: list[str],
    missing_fields: list[str] | None = None,
    gate: dict[str, Any] | None = None,
    environment_id: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    metadata = {
        "provider": provider,
        "operation": operation,
        "reason": reason,
        "service_id": service_id,
        "variable_names": variable_names,
        "count": len(variable_names),
    }
    if environment_id:
        metadata["environment_id"] = environment_id
    if project_id:
        metadata["project_id"] = project_id
    return redact({
        "provider": provider,
        "ok": False,
        "updated": False,
        "service_id": service_id,
        "environment_id": environment_id,
        "project_id": project_id,
        "variable_names": variable_names,
        "count": len(variable_names),
        "errors": errors,
        "missing_fields": missing_fields or [],
        "gate": gate,
        "audit_event": create_audit_event(f"{provider}.env_vars.blocked", metadata),
    })


def success_env_result(
    provider: str,
    *,
    operation: str,
    service_id: str,
    variable_names: list[str],
    audit_events: list[dict[str, Any]],
    gate: dict[str, Any],
    environment_id: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    metadata = {
        "provider": provider,
        "operation": operation,
        "service_id": service_id,
        "variable_names": variable_names,
        "count": len(variable_names),
    }
    if environment_id:
        metadata["environment_id"] = environment_id
    if project_id:
        metadata["project_id"] = project_id
    return redact({
        "provider": provider,
        "ok": True,
        "updated": True,
        "service_id": service_id,
        "environment_id": environment_id,
        "project_id": project_id,
        "variable_names": variable_names,
        "count": len(variable_names),
        "gate": gate,
        "audit_events": audit_events,
        "audit_event": create_audit_event(f"{provider}.env_vars.updated", metadata),
    })
