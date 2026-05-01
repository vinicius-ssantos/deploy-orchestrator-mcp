# Security

This MCP can control infrastructure. It must be conservative by default.

## Default mode

The default mode is dry-run/read-only.

The server may analyze repositories, validate credentials and generate plans without approval.

## Approval-required actions

The following actions require explicit approval:

- creating an app service
- creating a database
- setting environment variables
- triggering deploys
- applying migrations
- rolling back
- configuring domains
- scaling services

## Destructive actions

The following actions require explicit destructive confirmation:

- deleting services
- deleting databases
- restoring backups
- resetting databases
- exposing databases publicly
- running write SQL in production

## Secret handling

Never return secret values in tool responses.

Only return secret names, presence and target service.

All logs must redact tokens, passwords, connection strings and service role keys.

## Allowlist

The server should support allowlists for:

- repositories
- providers
- environments
- organizations
- projects

## Production policy

Production deploys are never automatic.

Production deploys require a plan, risk summary and explicit user approval.
