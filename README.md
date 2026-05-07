# deploy-orchestrator-mcp

Remote MCP server for multi-provider deployment orchestration.

It is designed to work together with `github-unified-mcp`:

- `github-unified-mcp`: repositories, files, branches, pull requests, GitHub Actions, checks, releases.
- `deploy-orchestrator-mcp`: app hosting, database/backend provisioning, deploys, logs, healthchecks, rollback and provider recommendation.

## Current status

Phases 0–3 complete. Render, Railway and Supabase real APIs are integrated with approval-gated execution and CI gate enforcement. OAuth 2.0 (Authorization Code + PKCE) is available for remote/ChatGPT connector access.

## Implemented tools

Core tools:

- `safety_settings`
- `provider_list`
- `provider_capabilities`
- `repo_analyze`
- `deploy_generate_plan`
- `evaluate_execution_gate` — CI gate + approval + policy check before any deploy

Render tools:

- `render_validate` — dry-run gate
- `render_service_plan` — dry-run service plan
- `render_validate_credentials` — validate API key (read-only)
- `render_list_services` — list services
- `render_deploy_staging` — trigger staging deploy (requires `approval="APPROVED"`, `ci_gate`)
- `render_get_deploy_status` — read or poll deploy status
- `render_healthcheck` — HTTP healthcheck
- `render_get_build_logs` — fetch build logs for a deploy
- `render_get_runtime_logs` — fetch runtime logs for a service
- `render_rollback_staging` — revert staging to a previous deploy (requires `approval="APPROVED"` + `confirm="CONFIRM_DESTRUCTIVE_OPERATION"`)

Railway tools:

- `railway_validate` — dry-run gate
- `railway_service_plan` — dry-run service plan
- `railway_postgres_plan` — dry-run Postgres plan
- `railway_validate_credentials` — validate token (read-only)
- `railway_list_projects` — list all projects
- `railway_get_project` — get project with services and environments
- `railway_list_deployments` — list recent deployments for a service
- `railway_deploy_service` — trigger deploy (requires `approval="APPROVED"`, `ci_gate`)
- `railway_get_deploy_status` — read or poll deployment status
- `railway_healthcheck` — HTTP healthcheck

Supabase tools:

- `supabase_validate` — dry-run gate
- `supabase_project_plan` — dry-run project plan
- `supabase_validate_credentials` — validate access token (read-only)
- `supabase_list_organizations` — list organizations
- `supabase_list_projects` — list projects
- `supabase_get_project_status` — get project status
- `supabase_get_connection_info` — safe connection metadata (no secrets returned)
- `supabase_healthcheck` — REST API reachability check

Fly.io tools:

- `fly_validate`
- `fly_app_plan`

Koyeb tools:

- `koyeb_validate`
- `koyeb_service_plan`

Coolify tools:

- `coolify_validate`
- `coolify_app_plan`
- `coolify_database_plan`

## Initial providers

App providers:

- Render
- Railway
- Fly.io
- Koyeb
- Coolify

Database/backend providers:

- Supabase
- Railway Postgres
- Render Postgres
- Koyeb Database
- Coolify Postgres

## MVP goal

The first working version should answer:

```text
Analyze this repository and generate a staging deployment plan.
```

Returning:

- detected stack
- runtime type
- provider recommendation
- database/backend recommendation, if needed
- provider-specific dry-run plan
- database-specific dry-run plan
- required environment variables
- missing deployment files
- risk assessment
- deployment steps
- approval-required actions

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e . pytest
pytest -q
PYTHONPATH=src python scripts/smoke_test.py
python -m deploy_orchestrator_mcp.server
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e . pytest
.\.venv\Scripts\python.exe -m pytest -q
$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe scripts\smoke_test.py
.\.venv\Scripts\python.exe -m deploy_orchestrator_mcp.server
```

Using `.env` on Windows PowerShell:

```powershell
# Fill RENDER_API_KEY and other values in .env first
Get-Content .env | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $name, $value = $_ -split '=', 2
  [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
}

.\.venv\Scripts\python.exe -m deploy_orchestrator_mcp.server
```

## Policy and approval behavior

Deployment plans include two separate safety signals:

- `policy_result`: validates whether the requested environment and selected providers are allowed by repository policy.
- `approval_required` and `approval_required_actions`: indicate whether the plan contains actions that require explicit user confirmation before execution.

A policy failure blocks or flags the plan as invalid. It is reported in `policy_result` and adds the risk `Repository policy validation failed`.

Approval requirements are different from policy validation. A plan can be policy-valid and still require approval because it creates or changes infrastructure. For example, staging plans may be allowed by policy while still requiring confirmation for service creation, database provisioning, environment variable writes or deployment triggers.

Production deployments require explicit approval by default and are blocked by the default policy unless production is explicitly allowed.

Sensitive actions that require approval include:

- creating services or apps
- creating databases or backend projects
- setting environment variables
- triggering deployments
- applying migrations
- rolling back deployments
- configuring domains
- scaling services

Destructive actions always require explicit confirmation, including deleting apps or databases, resetting databases, restoring backups, running production write SQL or exposing a database publicly.

Example deployment-plan safety metadata:

```python
{
    "policy_result": {
        "valid": True,
        "environment": "staging",
        "app_provider": "render",
        "database_provider": "supabase",
        "errors": [],
    },
    "approval_required": True,
    "approval_required_actions": [
        "create service",
        "set environment variables",
        "trigger deployment",
        "create database",
    ],
    "risks": [],
    "mode": "dry-run",
}
```

## Safety posture

The server starts in dry-run/read-only mode.

Production deploys, env var writes, migrations, rollback, domain changes and destructive actions require explicit approval.

Default safety settings:

- read-only mode enabled
- confirmation required
- preview/staging allowed by default
- production blocked unless explicitly allowed
- provider allowlist enforced

## First milestone

Implemented:

```text
repo_analyze -> deploy_generate_plan -> provider recommendation -> provider-specific dry-run plan
```

Next:

1. Add repo-level policy files.
2. Add Supabase read-only API client.
3. ~~Add Railway real API execution tools.~~ ✅ Done (PR #36 + #37)
4. Add Fly.io, Koyeb and Coolify real API execution tools.
5. Add persistent audit log and CI gate check before execute.
