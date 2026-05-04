from deploy_orchestrator_mcp.audit import (
    InMemoryAuditLog,
    create_audit_event,
    create_plan_audit_event,
)
from deploy_orchestrator_mcp.redaction import REDACTED


def fixed_now():
    return "2026-05-04T00:00:00+00:00"


def test_create_audit_event_redacts_sensitive_metadata():
    event = create_audit_event(
        "provider.credentials.checked",
        {
            "provider": "render",
            "RENDER_API_KEY": "render-secret",
            "database_url": "postgres://user:password@example.com:5432/app",
        },
        now=fixed_now,
    )

    assert event == {
        "type": "provider.credentials.checked",
        "created_at": "2026-05-04T00:00:00+00:00",
        "metadata": {
            "provider": "render",
            "RENDER_API_KEY": REDACTED,
            "database_url": REDACTED,
        },
    }


def test_create_plan_audit_event_summarizes_policy_and_approval_metadata():
    plan = {
        "environment": "staging",
        "mode": "dry-run",
        "app_provider": {"provider": "render"},
        "database_provider": {"provider": "supabase"},
        "policy_result": {"valid": True, "errors": []},
        "approval_required": True,
        "approval_required_actions": ["create service", "create database"],
        "risks": [],
    }

    event = create_plan_audit_event(plan, now=fixed_now)

    assert event["type"] == "deployment.plan.generated"
    assert event["created_at"] == "2026-05-04T00:00:00+00:00"
    assert event["metadata"] == {
        "environment": "staging",
        "mode": "dry-run",
        "app_provider": "render",
        "database_provider": "supabase",
        "policy_valid": True,
        "policy_errors": [],
        "approval_required": True,
        "approval_required_actions": ["create service", "create database"],
        "risks": [],
    }


def test_create_plan_audit_event_omits_provider_secret_details():
    plan = {
        "environment": "staging",
        "mode": "dry-run",
        "app_provider": {"provider": "render"},
        "database_provider": {
            "provider": "supabase",
            "database_url": "postgres://user:password@example.com:5432/app",
        },
        "policy_result": {"valid": False, "errors": ["provider not allowed"]},
        "approval_required": True,
        "approval_required_actions": ["create database"],
        "risks": ["Repository policy validation failed"],
    }

    event = create_plan_audit_event(plan, now=fixed_now)

    assert "database_url" not in event["metadata"]
    assert event["metadata"]["database_provider"] == "supabase"
    assert event["metadata"]["policy_valid"] is False
    assert event["metadata"]["policy_errors"] == ["provider not allowed"]


def test_in_memory_audit_log_records_redacted_events():
    audit_log = InMemoryAuditLog()
    event = create_audit_event(
        "deployment.plan.generated",
        {"token": "secret-token", "environment": "staging"},
        now=fixed_now,
    )

    recorded = audit_log.record(event)

    assert recorded["metadata"]["token"] == REDACTED
    assert audit_log.list() == [recorded]
