# 53. ZIP Integration Megapack Plan

## Goal

Continue code generation without validation.

This pack adds local scripts to apply all generated ZIP megapacks into a local repository and build a final codegen bundle for one-time push later.

## Included scripts

```text
scripts/apply_megapack_zips.py
scripts/update_main_imports.py
scripts/update_worker_manifest_from_fragments.py
scripts/build_final_codegen_zip.py
scripts/run_codegen_only_finalize.ps1
```

## Intended workflow

Place these ZIPs in one folder:

```text
HS-CAD-cli-finalization-megapack.zip
HS-CAD-analysis-export-megapack.zip
HS-CAD-analysis-storage-megapack.zip
HS-CAD-analysis-report-megapack.zip
```

Then run:

```powershell
python -X utf8 scripts\apply_megapack_zips.py --zip-dir . --repo-root .
python -X utf8 scripts\update_worker_manifest_from_fragments.py --repo-root .
python -X utf8 scripts\update_main_imports.py --repo-root .
python -X utf8 scripts\build_final_codegen_zip.py --repo-root . --out outputs\HS-CAD-final-codegen-bundle.zip
```

Or:

```powershell
.\scripts\run_codegen_only_finalize.ps1 -ZipDir . -RepoRoot . -Out outputs\HS-CAD-final-codegen-bundle.zip
```

## Validation

No validation is performed by these scripts.

Validation remains deferred to TODO documents.
