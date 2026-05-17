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

## Phase 3 — Railway, Supabase and migrations (real API)

- [x] Railway app provider with real API (`railway_deploy`, `railway_get_deploy_status`, `railway_healthcheck`)
- [x] Railway Postgres provisioning with approval gate (`railway_provision_postgres`)
- [x] Supabase real API — validate, list orgs/projects, status, connection info, healthcheck
- [x] Migration execution guardrails (`run_staging_migration`) — staging-first, approval, policy, CI and audit gates
- [ ] Supabase write actions (create project, apply migrations) — requires approval gate
- [ ] Operational migration validation with a real Render Workflow task slug (#63)

## Phase 4 — Koyeb, Fly and Coolify (real API)

- [ ] Koyeb provider with real API
- [ ] Fly.io provider with real API
- [ ] Coolify provider with real API
- [ ] Provider-specific rollback plans

## Phase 5 — Production controls

- [x] CI gate before execute (`ci_gate.allowed` required in execute mode, closes #25)
- [x] CI gate contract documented in `docs/INTEGRATION.md` (closes #24)
- [x] Persistent audit log support (`jsonl` and Supabase backends)
- [x] Per-repository policy files (`.deploy-orchestrator/policy.yml`) via `policy_load`
- [x] Runtime credential store (`credentials_set`, `credentials_clear`, `credentials_status`)
- [ ] Runtime audit backend activation/ops validation
- [ ] GitHub issue/PR reporting via github-unified-mcp integration

## Phase 6 — Frontend / Static Hosting providers

- [x] Frontend provider registry (`frontend_providers`) with Vercel
- [x] Vite and Next.js frontend detection in `repo_analyze`
- [x] Vercel credential validation (`vercel_validate_credentials`)
- [x] Vercel dry-run project plan (`vercel_project_plan`)
- [x] Vercel preview deploy with approval + CI gate (`vercel_deploy_preview`)
- [x] Vercel deploy status lookup (`vercel_get_deploy_status`)
- [x] Public env var exposure guard for `VITE_*`, `NEXT_PUBLIC_*`, `REACT_APP_*`, `PUBLIC_*`
- [x] Redaction fix for safe public Vercel URLs and deployment IDs (#84/#85)
- [ ] Operational Vercel preview validation with real `VERCEL_TOKEN`
- [ ] Frontend UI for Vercel Preview Deploy in `deploy-orchestrator-mcp-frontend`

## Phase 7+ — Future providers

- [ ] Netlify frontend provider
- [ ] Cloudflare Pages frontend provider
- [ ] Koyeb provider with real API
- [ ] Fly.io provider with real API
- [ ] Coolify provider with real API
- [ ] Provider-specific rollback plans
