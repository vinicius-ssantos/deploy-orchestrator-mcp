from deploy_orchestrator_mcp.approval import approval_required_actions, requires_approval


def test_read_only_staging_plan_does_not_require_approval():
    plan = {
        "environment": "staging",
        "steps": [
            "Review repository analysis",
            "Run CI before deployment",
            "Run healthcheck after deployment",
        ],
        "approval_required": [],
    }

    assert requires_approval(plan) is False
    assert approval_required_actions(plan) == []


def test_production_plan_requires_approval():
    plan = {
        "environment": "production",
        "steps": ["Review repository analysis"],
        "approval_required": [],
    }

    assert requires_approval(plan) is True
    assert approval_required_actions(plan) == ["production deployment"]


def test_state_changing_actions_require_approval():
    plan = {
        "environment": "staging",
        "steps": [
            "Review repository analysis",
            "Configure required environment variables",
            "Trigger deployment after approval",
        ],
        "approval_required": ["create service"],
    }

    assert requires_approval(plan) is True
    assert approval_required_actions(plan) == [
        "create service",
        "Configure required environment variables",
        "Trigger deployment after approval",
    ]


def test_destructive_actions_require_approval():
    plan = {
        "environment": "staging",
        "steps": ["Delete app"],
        "approval_required": [],
    }

    assert requires_approval(plan) is True
    assert approval_required_actions(plan) == ["Delete app"]


def test_boolean_approval_flag_does_not_break_action_detection():
    plan = {
        "environment": "staging",
        "steps": ["Review repository analysis"],
        "approval_required": True,
        "approval_required_actions": ["create database"],
    }

    assert requires_approval(plan) is True
    assert approval_required_actions(plan) == ["create database"]


def test_explicit_approval_actions_take_precedence_over_legacy_metadata():
    plan = {
        "environment": "staging",
        "steps": ["Review repository analysis"],
        "approval_required": ["create service"],
        "approval_required_actions": ["create database"],
    }

    assert requires_approval(plan) is True
    assert approval_required_actions(plan) == ["create database"]
