"""Render Workflows integration using the official render-sdk.

Wraps SyncWorkflowsService to provide task orchestration for pre/post-deploy
pipelines (migrations, smoke tests, seed scripts, etc.).

Task slugs use the format: "workflow-slug/task-name"
"""

from __future__ import annotations

import os
from typing import Any

from deploy_orchestrator_mcp.audit import create_audit_event
from deploy_orchestrator_mcp.redaction import redact

CONFIRM_DESTRUCTIVE = "CONFIRM_DESTRUCTIVE_OPERATION"


def _render_api_key(api_key: str | None = None) -> str | None:
    return api_key or os.environ.get("RENDER_API_KEY")


def _missing_api_key_result(operation: str) -> dict[str, Any]:
    return {
        "errors": [f"RENDER_API_KEY not set; cannot {operation}"],
        "hint": "Set RENDER_API_KEY via credentials_set or environment variable",
    }


def _make_client(api_key: str):
    from render_sdk.client.client import Client

    return Client(token=api_key)


def _sync_workflows(api_key: str):
    from render_sdk.client.workflows_sync import SyncWorkflowsService

    return SyncWorkflowsService(_make_client(api_key))


def _sdk_error_result(operation: str, exc: Exception) -> dict[str, Any]:
    return {"errors": [f"{operation} failed: {exc}"]}


def _task_run_to_dict(task_run) -> dict[str, Any]:
    """Convert a TaskRun or TaskRunDetails SDK object to a plain dict."""
    data: dict[str, Any] = {}
    for attr in ("id", "status", "created_at", "updated_at", "finished_at"):
        val = getattr(task_run, attr, None)
        if val is not None:
            data[attr] = str(val) if not isinstance(val, (str, int, float, bool)) else val
    output = getattr(task_run, "output", None)
    if output is not None:
        data["output"] = output
    error = getattr(task_run, "error", None)
    if error is not None:
        data["error"] = str(error)
    return data


def render_run_task(
    task_slug: str,
    input_data: list | dict | None = None,
    wait: bool = True,
    timeout_seconds: float = 300.0,
    approval: str | None = None,
    environment: str = "staging",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Trigger a Render Workflow task.

    For production environments, requires approval="APPROVED".
    task_slug format: "workflow-slug/task-name"
    """
    key = _render_api_key(api_key)
    if not key:
        return _missing_api_key_result("run task")

    if environment.strip().lower() == "production" and approval != "APPROVED":
        create_audit_event(
            "render.workflows.task.blocked",
            {"task_slug": task_slug, "environment": environment, "reason": "production requires approval"},
        )
        return {
            "errors": ["Production task execution requires approval='APPROVED'"],
            "task_slug": task_slug,
            "environment": environment,
        }

    data = input_data if input_data is not None else {}
    try:
        svc = _sync_workflows(key)
        if wait:
            result = svc.run_task(task_slug, data)
        else:
            result = svc.start_task(task_slug, data)
    except Exception as exc:
        create_audit_event(
            "render.workflows.task.error",
            {"task_slug": task_slug, "environment": environment, "error": str(exc)},
        )
        return _sdk_error_result("run_task", exc)

    task_dict = _task_run_to_dict(result)
    create_audit_event(
        "render.workflows.task.started" if not wait else "render.workflows.task.completed",
        {"task_slug": task_slug, "environment": environment, "task_run_id": task_dict.get("id")},
    )
    return redact({"ok": True, "task_run": task_dict, "task_slug": task_slug})


def render_get_task_run(
    task_run_id: str,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Fetch the current status and output of a task run."""
    key = _render_api_key(api_key)
    if not key:
        return _missing_api_key_result("get task run")

    try:
        svc = _sync_workflows(key)
        result = svc.get_task_run(task_run_id)
    except Exception as exc:
        return _sdk_error_result("get_task_run", exc)

    return redact({"ok": True, "task_run": _task_run_to_dict(result)})


def render_list_task_runs(
    limit: int = 20,
    api_key: str | None = None,
) -> dict[str, Any]:
    """List recent task runs across all workflows."""
    key = _render_api_key(api_key)
    if not key:
        return _missing_api_key_result("list task runs")

    try:
        svc = _sync_workflows(key)
        # Keep runtime compatibility with SDK variants and simplify tests that
        # mock only the service layer.
        try:
            from render_sdk.client.types import ListTaskRunsParams

            query = ListTaskRunsParams(limit=limit)
        except Exception:
            query = {"limit": limit}

        results = svc.list_task_runs(query)
    except Exception as exc:
        return _sdk_error_result("list_task_runs", exc)

    runs = []
    for item in results or []:
        task_run = getattr(item, "task_run", item)
        runs.append(_task_run_to_dict(task_run))

    return redact({"ok": True, "task_runs": runs, "count": len(runs)})


def render_cancel_task_run(
    task_run_id: str,
    confirm: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Cancel an in-progress task run.

    Requires confirm=CONFIRM_DESTRUCTIVE_OPERATION.
    """
    key = _render_api_key(api_key)
    if not key:
        return _missing_api_key_result("cancel task run")

    if confirm != CONFIRM_DESTRUCTIVE:
        return {
            "errors": [
                f"Pass confirm='{CONFIRM_DESTRUCTIVE}' to cancel a task run"
            ],
            "task_run_id": task_run_id,
        }

    try:
        svc = _sync_workflows(key)
        svc.cancel_task_run(task_run_id)
    except Exception as exc:
        create_audit_event(
            "render.workflows.task.cancel_error",
            {"task_run_id": task_run_id, "error": str(exc)},
        )
        return _sdk_error_result("cancel_task_run", exc)

    create_audit_event(
        "render.workflows.task.canceled",
        {"task_run_id": task_run_id},
    )
    return {"ok": True, "task_run_id": task_run_id, "status": "canceled"}
