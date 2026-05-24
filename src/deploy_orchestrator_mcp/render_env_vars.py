from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from deploy_orchestrator_mcp.audit import create_audit_event
from deploy_orchestrator_mcp.credentials import get_credential
from deploy_orchestrator_mcp.provider_env_vars import (
    blocked_env_result,
    env_write_gate,
    safe_variable_names,
    success_env_result,
    validate_variables,
)
from deploy_orchestrator_mcp.redaction import redact

RENDER_API_BASE_URL = "https://api.render.com/v1"


def _render_api_key(api_key: str | None = None) -> str | None:
    return api_key or get_credential("render")


def render_set_env_vars(
    *,
    service_id: str,
    variables: Mapping[str, Any],
    approval: str | bool | None = None,
    ci_gate: dict[str, Any] | None = None,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    variable_names = safe_variable_names(variables)
    validation_errors = validate_variables(variables)
    if validation_errors:
        return blocked_env_result(
            "render",
            operation="set_env_vars",
            reason="invalid_variables",
            service_id=service_id,
            variable_names=variable_names,
            errors=validation_errors,
        )

    gate = env_write_gate("render", approval=approval, ci_gate=ci_gate)
    if not gate["allowed"]:
        return blocked_env_result(
            "render",
            operation="set_env_vars",
            reason="gate_blocked",
            service_id=service_id,
            variable_names=variable_names,
            errors=gate.get("errors", []),
            missing_fields=gate.get("missing_fields", []),
            gate=gate,
        )

    key = _render_api_key(api_key)
    if not key:
        return blocked_env_result(
            "render",
            operation="set_env_vars",
            reason="missing_credentials",
            service_id=service_id,
            variable_names=variable_names,
            errors=["Render API key is not configured"],
            gate=gate,
        )

    owns_client = client is None
    http_client = client or httpx.Client(base_url=RENDER_API_BASE_URL, timeout=30.0)
    audit_events: list[dict[str, Any]] = []
    try:
        for name in variable_names:
            response = http_client.put(
                f"/services/{service_id}/env-vars/{name}",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json={"value": str(variables[name])},
            )
            audit_events.append(create_audit_event(
                "render.api.call",
                {
                    "provider": "render",
                    "operation": "set_env_var",
                    "service_id": service_id,
                    "variable_name": name,
                    "status_code": response.status_code,
                },
            ))
            if response.is_error:
                return blocked_env_result(
                    "render",
                    operation="set_env_vars",
                    reason="provider_error",
                    service_id=service_id,
                    variable_names=variable_names,
                    errors=[f"Render API returned status {response.status_code}"],
                    gate=gate,
                )
    finally:
        if owns_client:
            http_client.close()

    return redact(success_env_result(
        "render",
        operation="set_env_vars",
        service_id=service_id,
        variable_names=variable_names,
        audit_events=audit_events,
        gate=gate,
    ))
