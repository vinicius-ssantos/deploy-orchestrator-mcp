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

RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"

_VARIABLE_UPSERT_MUTATION = """
mutation VariableUpsert($input: VariableUpsertInput!) {
  variableUpsert(input: $input)
}
"""


def _railway_token(token: str | None = None) -> str | None:
    return token or get_credential("railway")


def railway_set_env_vars(
    *,
    project_id: str,
    service_id: str,
    environment_id: str,
    variables: Mapping[str, Any],
    approval: str | bool | None = None,
    ci_gate: dict[str, Any] | None = None,
    token: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    variable_names = safe_variable_names(variables)
    validation_errors = validate_variables(variables)
    if validation_errors:
        return blocked_env_result(
            "railway",
            operation="set_env_vars",
            reason="invalid_variables",
            service_id=service_id,
            environment_id=environment_id,
            project_id=project_id,
            variable_names=variable_names,
            errors=validation_errors,
        )

    gate = env_write_gate("railway", approval=approval, ci_gate=ci_gate)
    if not gate["allowed"]:
        return blocked_env_result(
            "railway",
            operation="set_env_vars",
            reason="gate_blocked",
            service_id=service_id,
            environment_id=environment_id,
            project_id=project_id,
            variable_names=variable_names,
            errors=gate.get("errors", []),
            missing_fields=gate.get("missing_fields", []),
            gate=gate,
        )

    resolved_token = _railway_token(token)
    if not resolved_token:
        return blocked_env_result(
            "railway",
            operation="set_env_vars",
            reason="missing_credentials",
            service_id=service_id,
            environment_id=environment_id,
            project_id=project_id,
            variable_names=variable_names,
            errors=["Railway token is not configured"],
            gate=gate,
        )

    owns_client = client is None
    http_client = client or httpx.Client(timeout=30.0)
    audit_events: list[dict[str, Any]] = []
    try:
        for name in variable_names:
            payload = {
                "query": _VARIABLE_UPSERT_MUTATION,
                "variables": {
                    "input": {
                        "projectId": project_id,
                        "environmentId": environment_id,
                        "serviceId": service_id,
                        "name": name,
                        "value": str(variables[name]),
                    }
                },
            }
            response = http_client.post(
                RAILWAY_API_URL,
                headers={
                    "Authorization": f"Bearer {resolved_token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            audit_events.append(create_audit_event(
                "railway.api.call",
                {
                    "provider": "railway",
                    "operation": "set_env_var",
                    "project_id": project_id,
                    "environment_id": environment_id,
                    "service_id": service_id,
                    "variable_name": name,
                    "status_code": response.status_code,
                },
            ))
            if response.is_error:
                return blocked_env_result(
                    "railway",
                    operation="set_env_vars",
                    reason="provider_error",
                    service_id=service_id,
                    environment_id=environment_id,
                    project_id=project_id,
                    variable_names=variable_names,
                    errors=[f"Railway API returned status {response.status_code}"],
                    gate=gate,
                )
            body = response.json() if response.content else {}
            if isinstance(body, Mapping) and body.get("errors"):
                return blocked_env_result(
                    "railway",
                    operation="set_env_vars",
                    reason="provider_error",
                    service_id=service_id,
                    environment_id=environment_id,
                    project_id=project_id,
                    variable_names=variable_names,
                    errors=["Railway GraphQL returned errors"],
                    gate=gate,
                )
    finally:
        if owns_client:
            http_client.close()

    return redact(success_env_result(
        "railway",
        operation="set_env_vars",
        service_id=service_id,
        environment_id=environment_id,
        project_id=project_id,
        variable_names=variable_names,
        audit_events=audit_events,
        gate=gate,
    ))
