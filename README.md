# deploy-orchestrator-mcp

Remote MCP server for multi-provider deployment orchestration.

It is designed to work together with `github-unified-mcp`:

- `github-unified-mcp`: repositories, files, branches, pull requests, GitHub Actions, checks, releases.
- `deploy-orchestrator-mcp`: app hosting, database/backend provisioning, deploys, logs, healthchecks, rollback and provider recommendation.

## Current status

MVP dry-run scaffold with provider-specific planning.

Render real API support is available with approval-gated execution for staging deploys.

## Implemented tools

Core tools:

- `safety_settings`
- `provider_list`
- `provider_capabilities`
- `repo_analyze`
- `deploy_generate_plan`

Render tools:

- `render_validate`
- `render_service_plan`
- `render_validate_credentials`
- `render_list_services`
- `render_deploy_staging` (requires `approval="APPROVED"`)
- `render_get_deploy_status`
- `render_healthcheck`

Railway tools:

- `railway_validate`
- `railway_service_plan`
- `railway_postgres_plan`

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

Supabase tools:

- `supabase_validate`
- `supabase_project_plan`

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
3. Add Railway real API execution tools.
4. Add Koyeb, Fly and Coolify real API execution tools.
5. Add persistent audit log and CI gate check before execute.
