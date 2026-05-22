from deploy_orchestrator_mcp.execution import APPROVAL_TOKEN, evaluate_execution_gate


def base_plan(**overrides):
    plan = {
        "environment": "staging",
        "mode": "dry-run",
        "policy_result": {"valid": True, "errors": []},
        "approval_required": True,
        "approval_required_actions": ["create service"],
    }
    plan.update(overrides)
    return plan


def valid_ci_gate(head_sha="abc123"):
    return {
        "allowed": True,
        "blocking_checks": [],
        "summary": "All workflows succeeded",
        "head_sha": head_sha,
        "checked_at": "2026-05-07T12:00:00Z",
    }


# ---------------------------------------------------------------------------
# dry-run (ci_gate not required)
# ---------------------------------------------------------------------------


def test_dry_run_mode_is_allowed_without_provider_writes():
    decision = evaluate_execution_gate(base_plan())

    assert decision["allowed"] is True
    assert decision["mode"] == "dry-run"
    assert decision["requires_approval"] is False
    assert decision["reasons"] == []
    assert decision["audit_event"]["metadata"]["decision"] == "allowed"


def test_dry_run_mode_ignores_missing_ci_gate():
    decision = evaluate_execution_gate(base_plan(), mode="dry-run", ci_gate=None)
    assert decision["allowed"] is True


# ---------------------------------------------------------------------------
# CI gate validation (execute mode)
# ---------------------------------------------------------------------------


def test_execute_blocked_when_ci_gate_absent():
    decision = evaluate_execution_gate(
        base_plan(approval_required=False),
        approval=APPROVAL_TOKEN,
        mode="execute",
        ci_gate=None,
    )
    assert decision["allowed"] is False
    assert "ci_gate is required for execute mode" in decision["reasons"]


def test_execute_blocked_when_ci_gate_not_allowed():
    decision = evaluate_execution_gate(
        base_plan(approval_required=False),
        approval=APPROVAL_TOKEN,
        mode="execute",
        ci_gate={"allowed": False, "head_sha": "abc123", "reason": "tests failed"},
    )
    assert decision["allowed"] is False
    assert any("CI gate blocked" in r for r in decision["reasons"])
    assert "tests failed" in decision["reasons"][0]


def test_execute_blocked_when_ci_gate_missing_head_sha():
    decision = evaluate_execution_gate(
        base_plan(approval_required=False),
        approval=APPROVAL_TOKEN,
        mode="execute",
        ci_gate={"allowed": True},
    )
    assert decision["allowed"] is False
    assert "ci_gate.head_sha is required" in decision["reasons"]


def test_execute_allowed_with_valid_ci_gate_and_approval():
    decision = evaluate_execution_gate(
        base_plan(),
        approval=APPROVAL_TOKEN,
        mode="execute",
        ci_gate=valid_ci_gate(),
    )
    assert decision["allowed"] is True
    assert decision["reasons"] == []


def test_ci_gate_head_sha_recorded_in_audit():
    decision = evaluate_execution_gate(
        base_plan(),
        approval=APPROVAL_TOKEN,
        mode="execute",
        ci_gate=valid_ci_gate("sha-xyz"),
    )
    assert decision["audit_event"]["metadata"]["ci_gate_head_sha"] == "sha-xyz"
    assert decision["audit_event"]["metadata"]["ci_gate_allowed"] is True


# ---------------------------------------------------------------------------
# Existing approval / policy / production tests (updated with ci_gate)
# ---------------------------------------------------------------------------


def test_approval_required_plan_is_blocked_without_approval():
    decision = evaluate_execution_gate(
        base_plan(),
        mode="execute",
        ci_gate=valid_ci_gate(),
    )
    assert decision["allowed"] is False
    assert "approval required" in decision["reasons"]
    assert decision["audit_event"]["type"] == "deployment.execution.blocked"


def test_approval_required_plan_is_allowed_with_approval_token():
    decision = evaluate_execution_gate(
        base_plan(),
        approval=APPROVAL_TOKEN,
        mode="execute",
        ci_gate=valid_ci_gate(),
    )
    assert decision["allowed"] is True
    assert decision["reasons"] == []
    assert decision["audit_event"]["metadata"]["decision"] == "allowed"


def test_policy_failure_blocks_execution_even_with_approval():
    decision = evaluate_execution_gate(
        base_plan(policy_result={"valid": False, "errors": ["provider not allowed"]}),
        approval=APPROVAL_TOKEN,
        mode="execute",
        ci_gate=valid_ci_gate(),
    )
    assert decision["allowed"] is False
    assert "policy validation failed" in decision["reasons"]


def test_production_execution_requires_approval():
    decision = evaluate_execution_gate(
        base_plan(environment="production"),
        mode="execute",
        ci_gate=valid_ci_gate(),
    )
    assert decision["allowed"] is False
    assert "production execution requires explicit approval" in decision["reasons"]
    assert "approval required" in decision["reasons"]


def test_approved_policy_valid_production_execution_is_allowed():
    decision = evaluate_execution_gate(
        base_plan(environment="production"),
        approval=APPROVAL_TOKEN,
        mode="execute",
        ci_gate=valid_ci_gate(),
    )
    assert decision["allowed"] is True
    assert decision["reasons"] == []


def test_non_approval_plan_can_execute_when_policy_is_valid():
    decision = evaluate_execution_gate(
        base_plan(approval_required=False, approval_required_actions=[]),
        mode="execute",
        ci_gate=valid_ci_gate(),
    )
    assert decision["allowed"] is True
    assert decision["requires_approval"] is False
    assert decision["reasons"] == []


def test_audit_event_records_blocked_execution_decision():
    decision = evaluate_execution_gate(
        base_plan(),
        mode="execute",
        ci_gate=valid_ci_gate(),
    )
    audit_event = decision["audit_event"]
    assert audit_event["type"] == "deployment.execution.blocked"
    assert audit_event["metadata"]["environment"] == "staging"
    assert audit_event["metadata"]["approval_required"] is True
    assert audit_event["metadata"]["approval_required_actions"] == ["create service"]
    assert audit_event["metadata"]["decision"] == "blocked"
