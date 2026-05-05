from deploy_orchestrator_mcp.audit import create_audit_event

APPROVAL_TOKEN = "APPROVED"


def _policy_valid(plan):
    policy_result = plan.get("policy_result") or {}
    return policy_result.get("valid", True) is True


def _is_production(plan):
    return str(plan.get("environment", "")).strip().lower() == "production"


def _approval_present(approval):
    return approval is True or approval == APPROVAL_TOKEN


def evaluate_execution_gate(plan, approval=None, mode=None):
    """Return a structured decision for whether a deployment plan can execute."""
    requested_mode = mode or plan.get("mode", "dry-run")
    reasons = []

    if requested_mode == "dry-run":
        return {
            "allowed": True,
            "mode": "dry-run",
            "requires_approval": False,
            "reasons": [],
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

    if not _policy_valid(plan):
        reasons.append("policy validation failed")

    if _is_production(plan) and not _approval_present(approval):
        reasons.append("production execution requires explicit approval")

    if plan.get("approval_required") and not _approval_present(approval):
        reasons.append("approval required")

    allowed = len(reasons) == 0
    decision = "allowed" if allowed else "blocked"

    return {
        "allowed": allowed,
        "mode": requested_mode,
        "requires_approval": plan.get("approval_required", False),
        "reasons": reasons,
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
                "decision": decision,
            },
        ),
    }
