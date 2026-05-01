# deploy-orchestrator-mcp

Remote MCP server for multi-provider deployment orchestration.

It is designed to work together with `github-unified-mcp`:

- `github-unified-mcp`: repositories, files, branches, pull requests, GitHub Actions, checks, releases.
- `deploy-orchestrator-mcp`: app hosting, database/backend provisioning, deploys, logs, healthchecks, rollback and provider recommendation.

## Current status

MVP dry-run scaffold with provider-specific planning.

The server does not execute real deploys yet.

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
2. Add provider credential validation in read-only mode.
3. Add Render read-only API client.
4. Add Supabase read-only API client.
5. Add approval-gated execution model.
