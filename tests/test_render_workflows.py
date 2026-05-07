"""Tests for render_workflows.py — Render SDK Workflows integration."""

from unittest.mock import MagicMock, patch

import pytest

from deploy_orchestrator_mcp.render_workflows import (
    CONFIRM_DESTRUCTIVE,
    render_cancel_task_run,
    render_get_task_run,
    render_list_task_runs,
    render_run_task,
)

API_KEY = "rnd_test_key"


def _make_task_run(task_run_id="tr_abc123", status="succeeded"):
    tr = MagicMock()
    tr.id = task_run_id
    tr.status = status
    tr.created_at = "2026-05-07T00:00:00Z"
    tr.updated_at = "2026-05-07T00:01:00Z"
    tr.finished_at = "2026-05-07T00:01:00Z"
    tr.output = {"result": "ok"}
    tr.error = None
    return tr


def _make_task_run_with_cursor(task_run):
    item = MagicMock()
    item.task_run = task_run
    # Make _task_run_to_dict work when item is passed directly
    item.id = task_run.id
    item.status = task_run.status
    item.created_at = task_run.created_at
    item.updated_at = task_run.updated_at
    item.finished_at = task_run.finished_at
    item.output = task_run.output
    item.error = task_run.error
    return item


# ---------------------------------------------------------------------------
# render_run_task
# ---------------------------------------------------------------------------


def test_run_task_missing_api_key(monkeypatch):
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    result = render_run_task("wf/task")
    assert "errors" in result


def test_run_task_production_blocked_without_approval(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    result = render_run_task("wf/migrate", environment="production", approval=None)
    assert "errors" in result
    assert "approval" in result["errors"][0].lower()


def test_run_task_production_allowed_with_approval(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    task_run = _make_task_run()
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.run_task.return_value = task_run
        mock_svc_factory.return_value = svc

        result = render_run_task(
            "wf/migrate",
            environment="production",
            approval="APPROVED",
        )

    assert result["ok"] is True
    assert result["task_run"]["id"] == "tr_abc123"


def test_run_task_staging_no_approval_required(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    task_run = _make_task_run()
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.run_task.return_value = task_run
        mock_svc_factory.return_value = svc

        result = render_run_task("wf/smoke-tests", environment="staging")

    assert result["ok"] is True
    assert result["task_slug"] == "wf/smoke-tests"


def test_run_task_no_wait_calls_start_task(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    task_run = _make_task_run(status="running")
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.start_task.return_value = task_run
        mock_svc_factory.return_value = svc

        result = render_run_task("wf/long-task", wait=False)

    svc.start_task.assert_called_once()
    svc.run_task.assert_not_called()
    assert result["ok"] is True


def test_run_task_sdk_error_returns_error_dict(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.run_task.side_effect = RuntimeError("network failure")
        mock_svc_factory.return_value = svc

        result = render_run_task("wf/task")

    assert "errors" in result
    assert "network failure" in result["errors"][0]


def test_run_task_with_dict_input(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    task_run = _make_task_run()
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.run_task.return_value = task_run
        mock_svc_factory.return_value = svc

        result = render_run_task("wf/migrate", input_data={"target": "latest"})

    svc.run_task.assert_called_once_with("wf/migrate", {"target": "latest"})
    assert result["ok"] is True


def test_run_task_with_list_input(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    task_run = _make_task_run()
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.run_task.return_value = task_run
        mock_svc_factory.return_value = svc

        result = render_run_task("wf/task", input_data=["arg1", "arg2"])

    svc.run_task.assert_called_once_with("wf/task", ["arg1", "arg2"])
    assert result["ok"] is True


# ---------------------------------------------------------------------------
# render_get_task_run
# ---------------------------------------------------------------------------


def test_get_task_run_missing_api_key(monkeypatch):
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    result = render_get_task_run("tr_abc123")
    assert "errors" in result


def test_get_task_run_success(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    task_run = _make_task_run()
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.get_task_run.return_value = task_run
        mock_svc_factory.return_value = svc

        result = render_get_task_run("tr_abc123")

    assert result["ok"] is True
    assert result["task_run"]["id"] == "tr_abc123"


def test_get_task_run_sdk_error(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.get_task_run.side_effect = RuntimeError("not found")
        mock_svc_factory.return_value = svc

        result = render_get_task_run("tr_missing")

    assert "errors" in result


# ---------------------------------------------------------------------------
# render_list_task_runs
# ---------------------------------------------------------------------------


def test_list_task_runs_missing_api_key(monkeypatch):
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    result = render_list_task_runs()
    assert "errors" in result


def test_list_task_runs_returns_list(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    items = [_make_task_run_with_cursor(_make_task_run(f"tr_{i}")) for i in range(3)]
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.list_task_runs.return_value = items
        mock_svc_factory.return_value = svc

        result = render_list_task_runs(limit=10)

    assert result["ok"] is True
    assert result["count"] == 3


def test_list_task_runs_empty(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.list_task_runs.return_value = []
        mock_svc_factory.return_value = svc

        result = render_list_task_runs()

    assert result["ok"] is True
    assert result["task_runs"] == []


def test_list_task_runs_sdk_error(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.list_task_runs.side_effect = RuntimeError("API error")
        mock_svc_factory.return_value = svc

        result = render_list_task_runs()

    assert "errors" in result


# ---------------------------------------------------------------------------
# render_cancel_task_run
# ---------------------------------------------------------------------------


def test_cancel_task_run_missing_api_key(monkeypatch):
    monkeypatch.delenv("RENDER_API_KEY", raising=False)
    result = render_cancel_task_run("tr_abc123", confirm=CONFIRM_DESTRUCTIVE)
    assert "errors" in result


def test_cancel_task_run_missing_confirm(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    result = render_cancel_task_run("tr_abc123", confirm=None)
    assert "errors" in result
    assert CONFIRM_DESTRUCTIVE in result["errors"][0]


def test_cancel_task_run_wrong_confirm(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    result = render_cancel_task_run("tr_abc123", confirm="wrong")
    assert "errors" in result


def test_cancel_task_run_success(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.cancel_task_run.return_value = None
        mock_svc_factory.return_value = svc

        result = render_cancel_task_run("tr_abc123", confirm=CONFIRM_DESTRUCTIVE)

    assert result["ok"] is True
    assert result["status"] == "canceled"
    svc.cancel_task_run.assert_called_once_with("tr_abc123")


def test_cancel_task_run_sdk_error(monkeypatch):
    monkeypatch.setenv("RENDER_API_KEY", API_KEY)
    with patch("deploy_orchestrator_mcp.render_workflows._sync_workflows") as mock_svc_factory:
        svc = MagicMock()
        svc.cancel_task_run.side_effect = RuntimeError("already canceled")
        mock_svc_factory.return_value = svc

        result = render_cancel_task_run("tr_abc123", confirm=CONFIRM_DESTRUCTIVE)

    assert "errors" in result
