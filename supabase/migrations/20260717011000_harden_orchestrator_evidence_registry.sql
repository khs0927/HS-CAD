alter table public.orchestrator_evidence
  add constraint orchestrator_evidence_schema_version_format
    check (schema_version ~ '^hscad\.plugin-orchestrator\.v[0-9]+(\.[0-9]+)*$'),
  add constraint orchestrator_evidence_runner_format
    check (runner ~ '^[a-z0-9][a-z0-9._-]{0,63}$'),
  add constraint orchestrator_evidence_profile_count
    check (jsonb_array_length(profiles) between 1 and 6),
  add constraint orchestrator_evidence_result_count
    check (jsonb_array_length(results) <= 128),
  add constraint orchestrator_evidence_summary_shape
    check (
      summary ?& array['total', 'passed', 'failed', 'blocked']
      and jsonb_typeof(summary -> 'total') = 'number'
      and jsonb_typeof(summary -> 'passed') = 'number'
      and jsonb_typeof(summary -> 'failed') = 'number'
      and jsonb_typeof(summary -> 'blocked') = 'number'
    );

comment on constraint orchestrator_evidence_runner_format on public.orchestrator_evidence is
  'Runner identifiers are bounded safe labels, never hostnames, paths, or free-form logs.';
