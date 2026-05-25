# 56. All Generated Megapacks Combined Upload

This branch records the combined generated megapack bundle uploaded through ChatGPT:

```text
HS-CAD-all-generated-megapacks-combined.zip
```

## Included source ZIPs

```text
HS-CAD-analysis-export-megapack.zip
HS-CAD-analysis-report-megapack.zip
HS-CAD-analysis-storage-megapack.zip
HS-CAD-cli-finalization-megapack.zip
HS-CAD-final-orchestration-megapack.zip
HS-CAD-pipeline-execution-megapack.zip
HS-CAD-zip-integration-megapack.zip
```

## Intended integration approach

The combined ZIP contains generated code, documentation, scripts, worker modules, and patch notes. To avoid overwriting the current `main` branch without validation, this upload is tracked as a staged integration branch.

Recommended local workflow:

```powershell
python scripts/apply_combined_megapack_zip.py `
  --zip HS-CAD-all-generated-megapacks-combined.zip `
  --repo-root . `
  --mode staged
```

The staged mode should:

1. Extract generated source files from `extracted_by_zip/*/src/**` into `src/**`.
2. Extract generated docs from `extracted_by_zip/*/docs/**` into `docs/**`.
3. Extract generated scripts from `extracted_by_zip/*/scripts/**` into `scripts/**`.
4. Preserve each pack's root README/PATCH/manifest under `docs/megapacks/<pack>/`.
5. Avoid changing `src/main.py` automatically.
6. Avoid changing `config/worker_manifest.json` automatically.
7. Produce an integration report before commit.

## Safety rules

- Do not mutate CAD files.
- Do not run ZWCAD COM or SendCommand during integration.
- Do not directly overwrite `main` without PR review.
- Register CLI imports only after local smoke tests pass.
- Register worker manifest entries only after import tests pass.

## Current GitHub push scope

This branch is a staging branch for the combined megapack upload. The binary ZIP itself remains available as the ChatGPT artifact in the current session. GitHub connector upload is text-first, so this branch records the manifest and local apply script for reproducible integration.
