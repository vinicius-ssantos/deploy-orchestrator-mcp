# deploy-orchestrator-mcp

Remote MCP server for multi-provider deployment orchestration.

It is designed to work together with `github-unified-mcp`:

- `github-unified-mcp`: repositories, files, branches, pull requests, GitHub Actions, checks, releases.
- `deploy-orchestrator-mcp`: app hosting, database/backend provisioning, deploys, logs, healthchecks, rollback and provider recommendation.

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
- required environment variables
- missing deployment files
- risk assessment
- deployment steps
- approval-required actions

## Safety posture

The server starts in dry-run/read-only mode.

Production deploys, env var writes, migrations, rollback, domain changes and destructive actions require explicit approval.

## First milestone

Implement:

```text
repo_analyze -> deploy_generate_plan -> provider recommendation -> dry-run plan
```

Then add real providers in this order:

1. Render
2. Railway
3. Supabase
4. Koyeb
5. Fly.io
6. Coolify
