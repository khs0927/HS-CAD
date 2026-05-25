# HS-CAD CLI Finalization Megapack ZIP

This is a local code bundle, not a pushed branch.

## Apply order

1. Start from the final generated branch:

```powershell
git fetch origin analysis-evidence-megapack-pr25
git switch -C local-megapack-final origin/analysis-evidence-megapack-pr25
```

2. Extract this zip into the repository root.

3. Patch `src/main.py` using `PATCH_MAIN_IMPORT.md`.

4. Keep all validation as TODO until local batch testing is ready.

## New code

```text
src/app/analysis_shortcut_cli.py
docs/49_analysis_cli_shortcuts_todo.md
docs/VALIDATION_TODO_ALL_MEGAPACKS.md
scripts/package_analysis_megapack.ps1
PATCH_MAIN_IMPORT.md
```

## No push yet

Keep this local. Push once the full bundle is applied and reviewed.
