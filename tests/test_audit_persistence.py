"""Tests for JsonlAuditBackend and persistent audit log integration."""

import json
import os

import pytest

from deploy_orchestrator_mcp.audit import (
    JsonlAuditLog,
    audit_log_list,
    audit_log_status,
    create_audit_event,
)


# ---------------------------------------------------------------------------
# JsonlAuditLog unit tests
# ---------------------------------------------------------------------------


def test_jsonl_write_and_read(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)
    event = {"type": "test.event", "created_at": "2026-05-07T00:00:00Z", "metadata": {}}
    log.record(event)

    events = log.list()
    assert len(events) == 1
    assert events[0]["type"] == "test.event"


def test_jsonl_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "dir" / "audit.jsonl"
    log = JsonlAuditLog(path)
    log.record({"type": "x", "created_at": "2026-05-07T00:00:00Z", "metadata": {}})
    assert path.exists()


def test_jsonl_returns_empty_when_file_missing(tmp_path):
    log = JsonlAuditLog(tmp_path / "nonexistent.jsonl")
    assert log.list() == []


def test_jsonl_multiple_events_most_recent_first(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)
    for i in range(5):
        log.record({"type": f"event.{i}", "created_at": f"2026-05-07T00:00:0{i}Z", "metadata": {}})

    events = log.list(limit=5)
    assert events[0]["type"] == "event.0"
    assert events[-1]["type"] == "event.4"


def test_jsonl_limit_respected(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)
    for i in range(10):
        log.record({"type": f"event.{i}", "created_at": "2026-05-07T00:00:00Z", "metadata": {}})

    assert len(log.list(limit=3)) == 3
    assert len(log.list(limit=500)) == 10


def test_jsonl_redacts_before_write(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)
    log.record({
        "type": "test",
        "created_at": "2026-05-07T00:00:00Z",
        "metadata": {"api_key": "super-secret-value"},
    })
    raw = path.read_text()
    assert "super-secret-value" not in raw


def test_jsonl_status_enabled(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)
    log.record({"type": "x", "created_at": "2026-05-07T00:00:00Z", "metadata": {}})
    status = log.status()
    assert status["enabled"] is True
    assert status["backend"] == "jsonl"
    assert status["size_bytes"] > 0


def test_jsonl_status_file_not_yet_created(tmp_path):
    log = JsonlAuditLog(tmp_path / "new.jsonl")
    status = log.status()
    assert status["exists"] is False
    assert status["size_bytes"] == 0


# ---------------------------------------------------------------------------
# create_audit_event auto-persistence
# ---------------------------------------------------------------------------


def test_create_audit_event_persists_when_path_configured(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("MCP_AUDIT_LOG_PATH", str(path))

    create_audit_event("test.persist", {"key": "value"})

    assert path.exists()
    events = json.loads(path.read_text().strip())
    assert events["type"] == "test.persist"


def test_create_audit_event_no_file_when_path_not_set(tmp_path, monkeypatch):
    monkeypatch.delenv("MCP_AUDIT_LOG_PATH", raising=False)
    event = create_audit_event("test.no_persist", {})
    assert event["type"] == "test.no_persist"


def test_create_audit_event_redacts_before_persistence(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("MCP_AUDIT_LOG_PATH", str(path))

    create_audit_event("test.redact", {"render_api_key": "SENSITIVE_VALUE_XYZ"})

    raw = path.read_text()
    assert "SENSITIVE_VALUE_XYZ" not in raw


# ---------------------------------------------------------------------------
# audit_log_list and audit_log_status helpers
# ---------------------------------------------------------------------------


def test_audit_log_list_returns_empty_when_not_configured(monkeypatch):
    monkeypatch.delenv("MCP_AUDIT_LOG_PATH", raising=False)
    result = audit_log_list()
    assert result["enabled"] is False
    assert result["events"] == []


def test_audit_log_list_returns_events_when_configured(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("MCP_AUDIT_LOG_PATH", str(path))

    create_audit_event("event.one", {})
    create_audit_event("event.two", {})

    result = audit_log_list(limit=10)
    assert result["enabled"] is True
    assert len(result["events"]) == 2
    assert result["events"][-1]["type"] == "event.two"  # last written = last in list


def test_audit_log_status_disabled(monkeypatch):
    monkeypatch.delenv("MCP_AUDIT_LOG_PATH", raising=False)
    result = audit_log_status()
    assert result["enabled"] is False


def test_audit_log_status_enabled(tmp_path, monkeypatch):
    path = tmp_path / "audit.jsonl"
    monkeypatch.setenv("MCP_AUDIT_LOG_PATH", str(path))

    create_audit_event("status.test", {})

    result = audit_log_status()
    assert result["enabled"] is True
    assert result["backend"] == "jsonl"
