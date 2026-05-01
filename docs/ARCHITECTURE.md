# Architecture

## Purpose

deploy-orchestrator-mcp is a remote MCP server that recommends and orchestrates deployments across app and database providers.

It is not meant to replace CI/CD. GitHub Actions should remain the execution engine for tests, builds and controlled deploy workflows.

## System boundary

ChatGPT coordinates the work.

github-unified-mcp manages GitHub.

deploy-orchestrator-mcp manages hosting and database providers.

## Main modules

- repository analyzer
- provider recommender
- deployment planner
- provider adapters
- database adapters
- safety and approval gates
- audit logging
- healthcheck runner

## Provider adapters

App providers:

- Render
- Railway
- Fly.io
- Koyeb
- Coolify

Database providers:

- Supabase
- Railway Postgres
- Render Postgres
- Koyeb Database
- Coolify Postgres

## Core flow

1. Analyze repository files.
2. Detect runtime, framework, build command and start command.
3. Detect database/backend requirements.
4. Score candidate providers.
5. Generate a dry-run deployment plan.
6. Mark approval-required actions.
7. Execute only when allowed.
8. Validate with logs and healthchecks.
