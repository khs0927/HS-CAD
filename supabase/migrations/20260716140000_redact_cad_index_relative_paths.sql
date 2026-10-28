-- Privacy hardening for the optional HS-CAD cloud control plane.
-- Relative paths can contain client, project, address, or drawing names, so
-- remote summaries retain only a fixed redaction marker. Local SQLite history
-- continues to store the real relative path.

update public.cad_index_files
set relative_path = '<redacted>'
where relative_path <> '<redacted>';

drop index if exists public.cad_index_files_path_idx;

comment on column public.cad_index_files.relative_path is
  'Compatibility column; optional remote summaries always store <redacted>.';

comment on table public.cad_index_files is
  'Per-file extraction completeness metrics only; no drawing paths or extracted content.';
