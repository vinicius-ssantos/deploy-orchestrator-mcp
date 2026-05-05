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


def test_dry_run_mode_is_allowed_without_provider_writes():
    decision = evaluate_execution_gate(base_plan())

    assert decision["allowed"] is True
    assert decision["mode"] == "dry-run"
    assert decision["requires_approval"] is False
    assert decision["reasons"] == []
    assert decision["audit_event"]["metadata"]["decision"] == "allowed"


def test_approval_required_plan_is_blocked_without_approval():
    decision = evaluate_execution_gate(base_plan(), mode="execute")

    assert decision["allowed"] is False
    assert decision["reasons"] == ["approval required"]
    assert decision["audit_event"]["type"] == "deployment.execution.blocked"


def test_approval_required_plan_is_allowed_with_approval_token():
    decision = evaluate_execution_gate(
        base_plan(),
        approval=APPROVAL_TOKEN,
        mode="execute",
    )

    assert decision["allowed"] is True
    assert decision["reasons"] == []
    assert decision["audit_event"]["metadata"]["decision"] == "allowed"


def test_policy_failure_blocks_execution_even_with_approval():
    decision = evaluate_execution_gate(
        base_plan(policy_result={"valid": False, "errors": ["provider not allowed"]}),
        approval=APPROVAL_TOKEN,
        mode="execute",
    )

    assert decision["allowed"] is False
    assert decision["reasons"] == ["policy validation failed"]


def test_production_execution_remains_blocked_by_default():
    decision = evaluate_execution_gate(
        base_plan(environment="production"),
        approval=APPROVAL_TOKEN,
        mode="execute",
    )

    assert decision["allowed"] is False
    assert decision["reasons"] == ["production execution requires explicit approval"]


def test_non_approval_plan_can_execute_when_policy_is_valid():
    decision = evaluate_execution_gate(
        base_plan(approval_required=False, approval_required_actions=[]),
        mode="execute",
    )

    assert decision["allowed"] is True
    assert decision["requires_approval"] is False
    assert decision["reasons"] == []


def test_audit_event_records_blocked_execution_decision():
    decision = evaluate_execution_gate(base_plan(), mode="execute")

    audit_event = decision["audit_event"]

    assert audit_event["type"] == "deployment.execution.blocked"
    assert audit_event["metadata"]["environment"] == "staging"
    assert audit_event["metadata"]["approval_required"] is True
    assert audit_event["metadata"]["approval_required_actions"] == ["create service"]
    assert audit_event["metadata"]["decision"] == "blocked"
