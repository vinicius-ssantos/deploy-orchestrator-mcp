# Integration Contract — deploy-orchestrator-mcp

This document describes how deploy-orchestrator-mcp integrates with
github-unified-mcp. The authoritative contract lives in the other repo.

## Authoritative contract

The full integration contract — coordination rules, shared data types,
approval tokens, Mermaid flow diagrams, and security boundaries — is
maintained in:

  `github-unified-mcp / docs/INTEGRATION.md`

This file is a summary. Always defer to the above for authoritative details.

## Summary

deploy-orchestrator-mcp manages deployment providers (Render, Railway,
Fly.io, Koyeb, Coolify, Supabase). It works with github-unified-mcp, which
manages GitHub operations. The LLM coordinates between them.

```
LLM
 ├── github-unified-mcp  →  reads repo, posts PR comments, runs Actions
 └── deploy-orchestrator-mcp  →  plans and executes provider deploys
```

## This MCP responsibilities

- Detect runtime and stack from file list
- Score and recommend deployment providers
- Generate dry-run deployment plans
- Evaluate policy (allowed environments, providers)
- Gate execution on user approval
- Execute provider API calls (when out of dry-run mode)
- Run healthchecks after deploy
- Report results back to the LLM for posting to GitHub

## What this MCP never does

- Read from the GitHub API directly
- Hold or use GitHub tokens
- Post comments to GitHub issues or PRs (the LLM does this via github-unified-mcp)
- Execute without policy validation and user approval

## Data received from github-unified-mcp (via LLM)

| Field | Type | Description |
|---|---|---|
| `repo_full_name` | str | "owner/repo" — identifies the target repository |
| `files` | list[str] | file paths from repo_tree — input for repo_analyze |

## Data returned to the LLM (for posting via github-unified-mcp)

| Field | Type | Description |
|---|---|---|
| `plan_summary` | dict | Full deployment plan — posted as PR comment |
| `policy_result` | dict | Policy validation result |
| `approval_required_actions` | list[str] | Actions needing user confirmation |
| `risks` | list[str] | Identified deployment risks |

## Approval token

Sensitive deployment actions require `approval="APPROVED"` passed to
`evaluate_execution_gate()`. This token is distinct from
`CONFIRM_DESTRUCTIVE_OPERATION` used by github-unified-mcp.

## Injection risk at the boundary

`files` (file_list) comes from untrusted GitHub content and may contain
injected paths or names. This MCP treats the list as opaque paths only —
it does not execute or interpret file content received through this channel.
If github-unified-mcp flags `injection_risk: true`, the LLM must not pass
the content to this MCP without explicit user confirmation.
