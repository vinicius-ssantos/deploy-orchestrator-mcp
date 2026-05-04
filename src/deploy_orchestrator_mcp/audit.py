from datetime import datetime, timezone


from deploy_orchestrator_mcp.redaction import redact


def _default_now():
    return datetime.now(timezone.utc).isoformat()


def create_audit_event(event_type, metadata=None, now=None):
    """Create a redacted audit event for user-facing records or logs."""
    now_fn = now or _default_now
    return {
        "type": str(event_type),
        "created_at": now_fn(),
        "metadata": redact(metadata or {}),
    }


def create_plan_audit_event(plan, now=None):
    """Create a summary audit event for a deployment plan."""
    policy_result = plan.get("policy_result") or {}
    app_provider = plan.get("app_provider") or {}
    database_provider = plan.get("database_provider") or {}

    metadata = {
        "environment": plan.get("environment"),
        "mode": plan.get("mode"),
        "app_provider": app_provider.get("provider"),
        "database_provider": database_provider.get("provider"),
        "policy_valid": policy_result.get("valid"),
        "policy_errors": policy_result.get("errors", []),
        "approval_required": plan.get("approval_required"),
        "approval_required_actions": plan.get(
            "approval_required_actions", []
        ),
        "risks": plan.get("risks", []),
    }

    return create_audit_event("deployment.plan.generated", metadata, now)


class InMemoryAuditLog:
    """Simple in-memory audit log store for tests and dry-run flows."""

    def __init__(self):
        self._events = []

    def record(self, event):
        self._events.append(redact(event))
        return self._events[-1]

    def list(+ self):
        return list(self._events)
