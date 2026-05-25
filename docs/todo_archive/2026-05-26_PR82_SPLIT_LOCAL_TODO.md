# PR82 Split Local Validation TODO

Date: 2026-05-26

Stored on `archive/hs-cad-local-todos` for local-only execution.

## Purpose

PR82 is a draft generated megapack review PR and must not be merged directly. Local validation should extract useful groups into smaller branches.

## Local extraction order

1. Spatial Foundation
2. PDF Raster
3. OCR Tools
4. NetworkX Graph Audit
5. DuckDB Analytics
6. CLI registration candidates as docs only
7. Worker manifest candidates as docs only

## Local exclusion rules

Keep these out of extraction commits:

- runtime output folders
- generated zip archives
- binary/runtime artifacts
- direct edits to `src/main.py`
- direct edits to `config/worker_manifest.json`
- broad adapter live-execution edits

## Local checklist per extraction branch

1. Start from latest `main`.
2. Copy only files owned by that extraction group.
3. Run focused tests for that group.
4. Run compile check where available.
5. Run CLI help only if CLI registration is intentionally part of the branch.
6. Confirm no runtime artifacts are staged.
7. Compare against latest `main` before push.
8. Record result in PR body or local review note.

## Stop condition

Stop if the branch touches high-risk files directly or includes runtime artifacts.
