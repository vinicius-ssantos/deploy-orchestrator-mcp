import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from deploy_orchestrator_mcp.redaction import redact

AUDIT_LOG_PATH_ENV = "MCP_AUDIT_LOG_PATH"


def _default_now():
    return datetime.now(timezone.utc).isoformat()


def _configured_audit_log_path() -> str | None:
    path = os.getenv(AUDIT_LOG_PATH_ENV, "").strip()
    return path or None


class JsonlAuditLog:
    """Append-only JSONL audit log with redaction before persistence."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    def record(self, event: dict[str, Any]) -> dict[str, Any]:
        redacted_event = redact(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(redacted_event, sort_keys=True) + "\n")
        return redacted_event

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []

        safe_limit = max(0, min(int(limit), 500))
        if safe_limit == 0:
            return []

        events: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    events.append(redact(value))

        return events[-safe_limit:]

    def status(self) -> dict[str, Any]:
        exists = self.path.exists()
        return {
            "enabled": True,
            "backend": "jsonl",
            "path": str(self.path),
            "exists": exists,
            "size_bytes": self.path.stat().st_size if exists else 0,
        }


def _persist_if_configured(event: dict[str, Any]) -> None:
    path = _configured_audit_log_path()
    if not path:
        return
    try:
        JsonlAuditLog(path).record(event)
    except OSError:
        # Audit persistence should not break the user-facing operation.
        # A future hardening pass can surface persistence failures via metrics.
        return


def create_audit_event(event_type, metadata=None, now=None):
    """Create a redacted audit event and optionally persist it as JSONL."""
    now_fn = now or _default_now
    event = {
        "type": str(event_type),
        "created_at": now_fn(),
        "metadata": redact(metadata or {}),
    }
    _persist_if_configured(event)
    return event


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


def audit_log_status() -> dict[str, Any]:
    """Return safe status for the configured persistent audit backend."""
    path = _configured_audit_log_path()
    if not path:
        return {
            "enabled": False,
            "backend": None,
            "path": None,
            "exists": False,
            "size_bytes": 0,
        }
    return JsonlAuditLog(path).status()


def audit_log_list(limit: int = 50) -> dict[str, Any]:
    """List recent persisted audit events with redacted output."""
    path = _configured_audit_log_path()
    if not path:
        return {
            "enabled": False,
            "events": [],
            "limit": limit,
        }

    events = JsonlAuditLog(path).list(limit=limit)
    return {
        "enabled": True,
        "events": events,
        "limit": max(0, min(int(limit), 500)),
    }


class InMemoryAuditLog:
    """Simple in-memory audit log store for tests and dry-run flows."""

    def __init__(self):
        self._events = []

    def record(self, event):
        self._events.append(redact(event))
        return self._events[-1]

    def list(self):
        return list(self._events)
