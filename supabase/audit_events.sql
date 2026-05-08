-- Supabase audit log schema for deploy-orchestrator-mcp.
--
-- Run this once in the Supabase SQL Editor for the project used by
-- the Render deployment. The application writes to this table via
-- the Supabase REST API when MCP_AUDIT_BACKEND=supabase.
--
-- Do not store the Supabase service_role key in SQL, docs, issues,
-- PRs, logs, or chat. Keep it only in the Render secret environment.

create extension if not exists pgcrypto;

create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  event_type text not null,
  actor text,
  environment text,
  provider text,
  repository text,
  payload jsonb not null
);

create index if not exists audit_events_created_at_idx
  on public.audit_events (created_at desc);

create index if not exists audit_events_event_type_idx
  on public.audit_events (event_type);

comment on table public.audit_events is
  'Persistent redacted audit events for deploy-orchestrator-mcp.';

comment on column public.audit_events.payload is
  'Redacted full audit event payload. Never insert raw secrets.';
