# Roadmap

## Phase 0 — Scaffold

- [x] Create repository
- [x] Add README
- [x] Add architecture docs
- [x] Add Python project config (pyproject.toml)
- [x] Add FastMCP server skeleton
- [x] Add CI (.github/workflows/test.yml)
- [x] Add Dockerfile
- [x] Add render.yaml

## Phase 1 — Dry-run planning

- [x] Implement repository analyzer (analyzer.py)
- [x] Detect runtime from common files
- [x] Detect database needs
- [x] Implement provider scoring (recommender.py)
- [x] Implement dry-run deployment plan (planner.py)
- [x] Policy evaluation (policy.py)
- [x] Approval gate (approval.py)
- [x] Execution gate (execution.py)
- [x] Add tests
- [x] Deployment plan summary formatter (PR #19)

## Phase 2 — Render provider (real API)

- [x] Validate Render credentials (read-only)
- [x] List services
- [x] Trigger staging deploy with approval gate
- [x] Read deploy status
- [x] Run healthcheck after deploy
- [x] Fetch build and runtime logs (`render_get_build_logs`, `render_get_runtime_logs`)
- [x] Rollback staging to previous deploy (`render_rollback_staging` — dual gate)
- [x] CI gate required before execute (`ci_gate` in `evaluate_execution_gate`)
- [x] OAuth 2.0 Authorization Code flow + PKCE for remote access
- [x] Stateless HMAC-SHA256 signed access tokens (`MCP_OAUTH_SIGNING_KEY`)
- [x] Enriched `/healthz` (version, tool_schema_version, commit_sha, uptime)

Notes:

- Implemented in `render_api.py` and exposed via FastMCP tools in `server.py`.
- Tests mock the Render API with `httpx.MockTransport`; CI does not call Render.
- Operational validation completed on 2026-05-06.

## Phase 3 — Railway and Supabase (real API)

- [x] Railway app provider with real API (`railway_deploy`, `railway_get_deploy_status`, `railway_healthcheck`)
- [x] Railway Postgres provisioning with approval gate (`railway_provision_postgres`)
- [x] Supabase real API — validate, list orgs/projects, status, connection info, healthcheck
- [ ] Supabase write actions (create project, apply migrations) — requires approval gate
- [ ] Migration execution tool (staging-first, with audit)

## Phase 4 — Koyeb, Fly and Coolify (real API)

- [ ] Koyeb provider with real API
- [ ] Fly.io provider with real API
- [ ] Coolify provider with real API
- [ ] Provider-specific rollback plans

## Phase 5 — Production controls

- [x] CI gate before execute (`ci_gate.allowed` required in execute mode, closes #25)
- [x] CI gate contract documented in `docs/INTEGRATION.md` (closes #24)
- [ ] Persistent audit log (issue #30)
- [ ] Per-repository policy files (`.deploy-orchestrator/policy.yml`) (issue #31)
- [ ] GitHub issue/PR reporting via github-unified-mcp integration
