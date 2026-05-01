# Decision policy

The provider recommendation engine should be deterministic, explainable and conservative.

## App provider rules

Python or FastMCP HTTP services should prefer Render or Railway.

Node APIs should prefer Railway, Koyeb or Render.

Dockerized apps should prefer Fly.io, Koyeb, Railway or Coolify.

Java or Spring Boot apps should prefer Railway, Koyeb, Fly.io or Coolify.

VPS/self-hosted deployments should prefer Coolify.

## Database rules

If the app only needs a simple Postgres connection, prefer the database offering from the selected app provider for MVPs.

If the app needs Auth, Storage, Realtime, RLS or a managed backend surface, prefer Supabase.

If the app needs preview database branches, consider Supabase first and add Neon later.

## Environment rules

Preview and staging may be automated after dry-run.

Production always requires explicit approval.

## Output requirements

Every recommendation must include:

- selected provider
- confidence score
- reasons
- rejected alternatives
- required environment variables
- approval-required actions
- rollback strategy
