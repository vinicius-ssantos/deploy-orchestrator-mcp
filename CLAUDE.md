# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Priority Order

Follow this order for all work:

1. Execution safety, approval gate, and environment protection
2. Compatibility with MCP tool contracts
3. Small, explicit, testable changes
4. Test coverage for critical rules
5. Documentation updated when system truth changes

## Project Purpose

Python MCP server for multi-provider deployment orchestration:

- dry-run analysis and deployment planning
- controlled execution gates (policy, approval, CI)
- provider integrations (Render, Railway, Supabase, Vercel, others)
- audit trail and sensitive-output redaction

**Stack:** Python 3.11+, FastMCP, httpx, uvicorn, pytest, ruff

## Commands

```powershell
# Install (first time)
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Run all tests
py -m pytest -q

# Run a single test file
py -m pytest tests/test_supabase_api.py -q

# Lint
py -m ruff check .

# Run local server
.\.venv\Scripts\python.exe -m deploy_orchestrator_mcp.server
```

## Architecture

```
src/deploy_orchestrator_mcp/
  server.py           - MCP tools and entrypoint
  analyzer.py         - stack detection and repo analysis
  planner.py          - deployment plan generation (dry-run)
  execution.py        - execution gate (policy, approval, CI)
  policy.py           - policy parsing and evaluation
  audit.py            - audit event creation and persistence backends
  redaction.py        - sensitive data sanitization for output
  render_api.py       - Render integration
  railway_api.py      - Railway integration
  supabase_api.py     - Supabase integration
  vercel_api.py       - Vercel integration
  migrations.py       - staging-first migration guardrails
```

## Security Rules

- Respect policy validation before any execute operation
- Require explicit approval for state-changing operations
- Require CI gate for execute mode
- Enforce staging-first and provider/environment constraints where defined
- Never expose credentials, secrets, or non-redacted sensitive content

## Implementation Conventions

- Keep structured responses consistent across tools
- Use `evaluate_execution_gate(...)` for execute authorization decisions
- Use `create_audit_event(...)` for allow/block and critical provider operations
- Keep HTTP payloads explicit and minimal
- Keep tool docstrings short and objective

## Tests and Quality

Every non-trivial change must include or update tests:

- validate main behavior and guardrail cases
- for provider writes, test payload and endpoint called
- for critical rules, test negatives (missing approval, failing CI gate, policy block)
- before finishing, run `py -m pytest -q` and `py -m ruff check .`

## Git Workflow

- Never implement new features directly on `main`
- Use topic branches: `feat/*`, `fix/*`, `docs/*`
- Prefer small, coherent commits
- Never revert user changes without explicit request

## Architecture and security documentation

Before implementing security changes, new tools, or integration work, read:

- `docs/ARCHITECTURE.md`
- `docs/SECURITY.md`
- `docs/INTEGRATION.md`
- `docs/ROADMAP.md`

## Documentation Updates

When adding/removing tools or changing behavior:

- Update `README.md` (tools and status)
- Keep `docs/ROADMAP.md` aligned with implementation status
- Update `docs/INTEGRATION.md` first when the MCP contract changes
