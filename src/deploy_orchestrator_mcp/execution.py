from deploy_orchestrator_mcp.audit import create_audit_event

APPROVAL_TOKEN = "APPROVED"


def _policy_valid(plan):
    policy_result = plan.get("policy_result") or {}
    return policy_result.get("valid", True) is True


def _is_production(plan):
    return str(plan.get("environment", "")).strip().lower() == "production"


def _approval_present(approval):
    return approval is True or approval == APPROVAL_TOKEN


def _validate_ci_gate(ci_gate):
    """Validate the required ci_gate_check contract."""
    if ci_gate is None:
        return [("ci_gate is required for execute mode", ["ci_gate"])]

    missing_fields = [
        field
        for field in ("allowed", "blocking_checks", "summary")
        if field not in ci_gate
    ]
    if missing_fields:
        return [("ci_gate is missing required fields", missing_fields)]

    if ci_gate.get("allowed") is not True:
        summary = ci_gate.get("summary") or "CI checks did not pass"
        return [(f"CI gate blocked: {summary}", [])]

    return []


def _collect_missing_fields(reasons_with_fields):
    seen = set()
    result = []
    for _, fields in reasons_with_fields:
        for f in fields:
            if f not in seen:
                seen.add(f)
                result.append(f)
    return result


def evaluate_execution_gate(plan, approval=None, mode=None, ci_gate=None):
    """Return a structured decision for whether a deployment plan can execute."""
    requested_mode = mode or plan.get("mode", "dry-run")
    reasons_with_fields: list[tuple[str, list[str]]] = []

    if requested_mode == "dry-run":
        return {
            "ok": True,
            "allowed": True,
            "mode": "dry-run",
            "requires_approval": False,
            "reasons": [],
            "errors": [],
            "missing_fields": [],
            "blocking_checks": [],
            "ci_summary": "",
            "audit_event": create_audit_event(
                "deployment.execution.allowed",
                {
                    "mode": "dry-run",
                    "environment": plan.get("environment"),
                    "approval_required": plan.get("approval_required", False),
                    "decision": "allowed",
                },
            ),
        }

    # CI gate is mandatory for execute mode
    reasons_with_fields.extend(_validate_ci_gate(ci_gate))

    if not _policy_valid(plan):
        reasons_with_fields.append(("policy validation failed", []))

    if _is_production(plan) and not _approval_present(approval):
        reasons_with_fields.append(("production execution requires explicit approval", ["approval"]))

    if plan.get("approval_required") and not _approval_present(approval):
        reasons_with_fields.append(("approval required", ["approval"]))

    reasons = [r for r, _ in reasons_with_fields]
    missing_fields = _collect_missing_fields(reasons_with_fields)
    allowed = len(reasons) == 0
    decision = "allowed" if allowed else "blocked"

    blocking_checks = []
    ci_summary = ""
    if isinstance(ci_gate, dict):
        blocking_checks = list(ci_gate.get("blocking_checks") or [])
        ci_summary = str(ci_gate.get("summary") or "")

    return {
        "ok": allowed,
        "allowed": allowed,
        "mode": requested_mode,
        "requires_approval": plan.get("approval_required", False),
        "reasons": reasons,
        "errors": reasons,
        "missing_fields": missing_fields,
        "blocking_checks": blocking_checks,
        "ci_summary": ci_summary,
        "audit_event": create_audit_event(
            f"deployment.execution.{decision}",
            {
                "mode": requested_mode,
                "environment": plan.get("environment"),
                "approval_required": plan.get("approval_required", False),
                "approval_required_actions": plan.get(
                    "approval_required_actions", []
                ),
                "policy_valid": (plan.get("policy_result") or {}).get(
                    "valid", True
                ),
                "ci_gate_allowed": (ci_gate or {}).get("allowed"),
                "ci_gate_head_sha": (ci_gate or {}).get("head_sha"),
                "ci_blocking_checks": blocking_checks,
                "ci_summary": ci_summary,
                "decision": decision,
            },
        ),
    }
