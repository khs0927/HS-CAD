# HS-CAD Orchestrator Evidence Registry

## Purpose

The registry stores portable validation evidence without depending on GitHub Actions or exposing customer drawing information. It is optional: local JSON evidence remains authoritative and HS-CAD continues to work when Supabase is unavailable.

## Privacy boundary

The remote registry accepts only:

- orchestrator schema version;
- SHA-256 repository and branch tokens derived with a private namespace;
- commit SHA;
- selected profiles;
- top-level status and numeric summary;
- check name, status, return code, duration, stdout SHA-256 and stderr SHA-256;
- evidence SHA-256, runner label and completion timestamp.

It must never receive:

- repository or branch names in plaintext;
- source paths, fixture paths or working directories;
- drawing names or customer identifiers;
- extracted CAD text, geometry, images or original files;
- commands, reasons, stdout or stderr;
- environment-variable values or API keys.

The publisher reconstructs every result from an allowlist. Adding extra fields to the local JSON does not make them eligible for upload.

## Database security

Migration:

```text
supabase/migrations/20260717010000_create_orchestrator_evidence_registry.sql
```

The table has Row Level Security enabled, no `anon` or `authenticated` grants, and no public policy. Only a trusted server or runner using `service_role` may insert or read records. A service-role key must never be used by a browser, mobile widget, desktop bundle, public repository, command argument or log.

## Required trusted environment

```text
HSCAD_REPOSITORY_REF=<private repository reference>
HSCAD_BRANCH_REF=<private branch reference>
HSCAD_COMMIT_SHA=<40-character lowercase commit SHA>
HSCAD_ORCHESTRATOR_NAMESPACE=<private random namespace>
HSCAD_SUPABASE_URL=https://<project-ref>.supabase.co
HSCAD_SUPABASE_SERVICE_ROLE_KEY=<server-side secret only>
HSCAD_ORCHESTRATOR_RUNNER=<runner label>
```

Repository and branch references are read from environment variables so they do not appear in process arguments. The namespace prevents simple dictionary matching of repository and branch tokens.

## Dry-run validation

```powershell
python scripts/run_plugin_orchestrator.py --profile core
python scripts/publish_orchestrator_evidence.py --dry-run
```

Dry-run prints the sanitized database record and performs no network request. Review it before enabling remote upload.

## Trusted upload

```powershell
python scripts/publish_orchestrator_evidence.py
```

The publisher uses HTTPS, the Supabase REST endpoint, an `apikey` header and a bearer service-role credential from the trusted environment. It prints only the inserted record ID, status and evidence digest.

## Release gate usage

A remote record is supporting evidence, not proof by itself. Merge gates still require:

- a matching commit SHA;
- all required profile results;
- a passed top-level status;
- Windows/ZWCAD evidence for native CAD acceptance;
- manual mobile acceptance where required;
- no unresolved security or privacy blocker.

## Failure routing

| Failure | Action |
|---|---|
| Supabase unavailable | Keep local JSON and retry later; do not block local runtime |
| Missing service-role key | Fail closed without attempting upload |
| Invalid commit or digest | Reject before network access |
| Local JSON contains logs | Strip them through the result allowlist |
| Identifier namespace missing | Reject; never upload reversible identifier hashes |
| Duplicate evidence digest | Treat the existing record as the canonical duplicate |
