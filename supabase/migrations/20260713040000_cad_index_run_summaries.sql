-- Optional HS-CAD cloud control plane.
-- Stores privacy-conscious run statistics only: no drawing bytes, absolute
-- source paths, entity payloads, or extracted text are uploaded.

create table if not exists public.cad_index_runs (
  run_id uuid primary key,
  workspace_id text not null,
  started_at timestamptz not null,
  completed_at timestamptz not null,
  status text not null check (status in ('complete', 'review', 'failed')),
  file_count integer not null default 0 check (file_count >= 0),
  complete_count integer not null default 0 check (complete_count >= 0),
  review_count integer not null default 0 check (review_count >= 0),
  failed_count integer not null default 0 check (failed_count >= 0),
  unavailable_count integer not null default 0 check (unavailable_count >= 0),
  total_entities bigint not null default 0 check (total_entities >= 0),
  total_text_occurrences bigint not null default 0 check (total_text_occurrences >= 0),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.cad_index_files (
  run_id uuid not null references public.cad_index_runs(run_id) on delete cascade,
  file_id text not null,
  relative_path text not null,
  extension text not null,
  status text not null check (status in ('ok', 'failed', 'unavailable')),
  engine text not null,
  complete boolean not null default false,
  entity_count integer not null default 0 check (entity_count >= 0),
  text_occurrence_count integer not null default 0 check (text_occurrence_count >= 0),
  layout_count integer not null default 0 check (layout_count >= 0),
  xref_count integer not null default 0 check (xref_count >= 0),
  warning_count integer not null default 0 check (warning_count >= 0),
  error_count integer not null default 0 check (error_count >= 0),
  requires_ocr_count integer not null default 0 check (requires_ocr_count >= 0),
  unsupported_proxy_count integer not null default 0 check (unsupported_proxy_count >= 0),
  unresolved_xref_count integer not null default 0 check (unresolved_xref_count >= 0),
  blockers text[] not null default '{}',
  extraction_report jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (run_id, file_id)
);

create index if not exists cad_index_runs_completed_at_idx
  on public.cad_index_runs (completed_at desc);
create index if not exists cad_index_runs_workspace_idx
  on public.cad_index_runs (workspace_id, completed_at desc);
create index if not exists cad_index_files_review_idx
  on public.cad_index_files (run_id, complete, status);
create index if not exists cad_index_files_path_idx
  on public.cad_index_files (relative_path);

create or replace function public.hscad_set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists cad_index_runs_set_updated_at on public.cad_index_runs;
create trigger cad_index_runs_set_updated_at
before update on public.cad_index_runs
for each row execute function public.hscad_set_updated_at();

drop trigger if exists cad_index_files_set_updated_at on public.cad_index_files;
create trigger cad_index_files_set_updated_at
before update on public.cad_index_files
for each row execute function public.hscad_set_updated_at();

alter table public.cad_index_runs enable row level security;
alter table public.cad_index_files enable row level security;

revoke all on table public.cad_index_runs from anon, authenticated;
revoke all on table public.cad_index_files from anon, authenticated;
grant select, insert, update, delete on table public.cad_index_runs to service_role;
grant select, insert, update, delete on table public.cad_index_files to service_role;

comment on table public.cad_index_runs is
  'HS-CAD privacy-conscious drawing index run summaries; no source drawings or extracted text.';
comment on table public.cad_index_files is
  'Per-file extraction completeness metrics for an HS-CAD index run.';
