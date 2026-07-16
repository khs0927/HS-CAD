create table if not exists public.orchestrator_evidence (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  schema_version text not null,
  repository_token text not null
    check (repository_token ~ '^[0-9a-f]{64}$'),
  branch_token text not null
    check (branch_token ~ '^[0-9a-f]{64}$'),
  commit_sha text not null
    check (commit_sha ~ '^[0-9a-f]{40}$'),
  profiles jsonb not null
    check (jsonb_typeof(profiles) = 'array'),
  status text not null
    check (status in ('passed', 'failed', 'blocked')),
  summary jsonb not null
    check (jsonb_typeof(summary) = 'object'),
  results jsonb not null
    check (jsonb_typeof(results) = 'array'),
  evidence_sha256 text not null unique
    check (evidence_sha256 ~ '^[0-9a-f]{64}$'),
  runner text not null,
  completed_at timestamptz not null
);

comment on table public.orchestrator_evidence is
  'Hash-only validation evidence. Never store source paths, drawing names, extracted text, stdout, stderr, environment values, or secrets.';
comment on column public.orchestrator_evidence.repository_token is
  'SHA-256 of an opaque repository namespace; not the repository name.';
comment on column public.orchestrator_evidence.branch_token is
  'SHA-256 of an opaque branch namespace; not the branch name.';
comment on column public.orchestrator_evidence.results is
  'Only check name, status, return code, duration, and stdout/stderr SHA-256 digests are allowed.';

create index if not exists orchestrator_evidence_created_at_idx
  on public.orchestrator_evidence (created_at desc);
create index if not exists orchestrator_evidence_commit_sha_idx
  on public.orchestrator_evidence (commit_sha);
create index if not exists orchestrator_evidence_status_idx
  on public.orchestrator_evidence (status);

alter table public.orchestrator_evidence enable row level security;
revoke all on table public.orchestrator_evidence from anon, authenticated;
grant select, insert, update, delete
  on table public.orchestrator_evidence to service_role;
