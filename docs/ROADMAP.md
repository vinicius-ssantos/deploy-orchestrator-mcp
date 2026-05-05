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

- [ ] Validate Render credentials (read-only)
- [ ] List services
- [ ] Trigger staging deploy with approval
- [ ] Read deploy status and logs
- [ ] Run healthcheck after deploy

## Phase 3 — Railway and Supabase (real API)

- [ ] Add Railway app provider
- [ ] Add Railway Postgres provider
- [ ] Add Supabase database/backend provider
- [ ] Add migration planning

## Phase 4 — Koyeb, Fly and Coolify (real API)

- [ ] Add Koyeb provider
- [ ] Add Fly.io provider
- [ ] Add Coolify provider
- [ ] Add rollback plans

## Phase 5 — Production controls

- [ ] Persistent audit log
- [ ] Per-repository policy files (.deploy-orchestrator/policy.yml)
- [ ] CI gate check before execute (via github-unified-mcp)
- [ ] GitHub issue/PR reporting via github-unified-mcp integration
