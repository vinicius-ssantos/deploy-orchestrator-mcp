# Architecture — deploy-orchestrator-mcp

## Purpose

deploy-orchestrator-mcp is a Python MCP server that plans and executes
deployments across multiple hosting and database providers. It works as
the deployment half of a two-MCP system alongside github-unified-mcp.

## System position

```
LLM (coordinator)
 ├── github-unified-mcp  →  GitHub repos, PRs, Actions, files
 └── deploy-orchestrator-mcp  →  Render, Railway, Fly, Koyeb, Coolify, Supabase
```

The LLM coordinates. These two MCPs never call each other directly.
See `github-unified-mcp/docs/INTEGRATION.md` for the full contract.

## Module map

```
src/deploy_orchestrator_mcp/
  server.py             FastMCP tool definitions — entry point
  config.py             Settings from env vars, safety defaults
  analyzer.py           Detects runtime and framework from file list
  planner.py            Generates deployment plan from analysis
  recommender.py        Scores and recommends app and database providers
  policy.py             Policy evaluation (environments, providers, production)
  approval.py           Approval gate — classifies sensitive/destructive actions
  execution.py          Execution gate — evaluate_execution_gate()
  audit.py              Structured audit event creation
  redaction.py          Secret and sensitive value redaction
  providers.py          Provider capabilities registry
  render_provider.py    Render dry-run plan generator
  render_api.py         Render real API client and execution tools
  railway_provider.py   Railway dry-run plan generator
  fly_provider.py       Fly.io dry-run plan generator
  koyeb_provider.py     Koyeb dry-run plan generator
  coolify_provider.py   Coolify dry-run plan generator
  supabase_provider.py  Supabase dry-run plan generator
```

## Core flow

```
1. repo_analyze(files)
      analyzer.py detects runtime, framework, database needs

2. deploy_generate_plan(analysis, environment, policy)
      recommender.py scores providers
      planner.py builds steps and approval_required_actions
      policy.py evaluates allowed environments/providers
      approval.py classifies actions needing confirmation

3. evaluate_execution_gate(plan, approval)
      execution.py checks policy, production flag, approval token
      returns {allowed: bool, reasons: list}

4. Provider tools (render_*, railway_*, fly_*, koyeb_*, coolify_*, supabase_*)
      dry-run: return structured plan, no API calls
      Render real API: credentials, services, staging deploy, status, healthcheck
      other execute modes (future): call provider APIs with approval gate
```

## Safety layers

```
Request
  │
  ├─ 1. Safety settings (config.py)
  │      read_only=true by default
  │      confirmation_required=true by default
  │      production blocked by default
  │
  ├─ 2. Policy evaluation (policy.py)
  │      validates environment, app_provider, database_provider
  │      against DEFAULT_POLICY or repo-level policy
  │
  ├─ 3. Approval classification (approval.py)
  │      SENSITIVE_ACTION_KEYWORDS → requires approval=APPROVED
  │      DESTRUCTIVE_ACTION_KEYWORDS → requires explicit confirmation
  │
  ├─ 4. Execution gate (execution.py)
  │      dry-run: always allowed
  │      execute: policy valid + approval present + not production (or approved)
  │
  └─ 5. Redaction (redaction.py)
         removes secrets, tokens, connection strings from all output
```

## Default policy

```python
{
    "allowed_environments": ["preview", "staging"],
    "production": {"allowed": False, "requires_approval": True},
    "rules": {
        "require_dry_run_first": True,
        "require_healthcheck": True,
        "never_return_secret_values": True,
        "redact_logs": True,
    },
}
```

Production is blocked by default. Staging and preview are allowed.
All sensitive actions require explicit user approval.

## Current implementation status

| Phase | Description | Status |
|---|---|---|
| Phase 0 | Scaffold | Complete |
| Phase 1 | Dry-run planning (all providers) | Complete |
| Phase 2 | Render real API | Complete |
| Phase 3 | Railway + Supabase real API | Not started |
| Phase 4 | Koyeb, Fly, Coolify real API | Not started |
| Phase 5 | Production controls | Not started |

Most provider tools still operate in dry-run mode only.
Render now has real API tools for credential validation, service listing, staging deploy, deploy status and healthcheck.
Render deploy execution is gated by `evaluate_execution_gate()` and requires `approval="APPROVED"`.
