# Codex handoff — Windows 11 + ZWCAD 2026 fixture validation

This document contains the only remaining work that requires the user's actual Windows computer, installed ZWCAD, and private drawing fixtures.

## Prerequisites

- Windows 11
- ZWCAD 2026 installed and licensed
- Python 3.11 available through `py -3.11`
- Git and GitHub authentication
- At least 20 representative, non-corrupted project drawings in a local folder
- Include a mix of DWG, DXF, PDF, and image files where available
- Include drawings containing PaperSpace layouts, blocks/attributes, dimensions, MLeader/Leader, tables, XREFs, raster/OLE/PDF underlays, and product-specific proxy objects

Never commit source drawings, extracted drawing text, absolute paths, service-role keys, access tokens, or customer information.

## Copy this prompt into Codex

```text
Work on repository https://github.com/khs0927/HS-CAD and pull request #126.
Use the existing branch agent/drawing-index-v2. Do not create a replacement branch and do not merge the PR.

This task must run on my connected Windows 11 computer because it requires my installed ZWCAD 2026 and private local drawing fixtures. Complete every step you can directly. Ask me only when Windows, ZWCAD, GitHub, or folder access requires an explicit login/approval.

Goals:
1. Validate the complete drawing-index V2 against real DWG/DXF/PDF/image files.
2. Compare native ZWCAD extraction with the fallback-only path.
3. Fix only reproducible code defects found by the fixture matrix.
4. Leave proprietary drawings and extracted content local.
5. Push safe source/test/documentation changes to agent/drawing-index-v2 and update PR #126.

Procedure:

A. Prepare the checkout
- Clone or open khs0927/HS-CAD.
- Fetch origin and checkout agent/drawing-index-v2.
- Confirm the branch is based on the current PR #126 head before editing.
- Run `git status --short`; do not discard unrelated local work.

B. Select the fixture folder
- Ask me to select or provide the local folder containing the real drawings.
- Do not copy that folder into the repository.
- Record only a privacy-safe fixture summary: file counts by extension and which feature categories are represented. Do not record filenames when they reveal customer/project details.

C. Run the one-command fixture matrix
From the repository root run:

powershell -ExecutionPolicy Bypass -File scripts\run_windows_drawing_index_fixture_matrix.ps1 `
  -Root "<LOCAL_DRAWING_FOLDER>" `
  -Workspace "outputs\codex-windows-fixture-matrix" `
  -Query "평면도","입면도","단면도","창호","구조"

The script must:
- prepare the free-local Python 3.11 environment;
- run native ZWCAD + fallback extraction;
- run fallback-only extraction;
- generate native and fallback validation reports;
- generate CODEX_WINDOWS_FIXTURE_COMPARISON.md and JSON;
- return nonzero when native extraction has a blocking regression.

D. Inspect the evidence
- Open outputs\codex-windows-fixture-matrix\CODEX_WINDOWS_VALIDATION_RESULT.md.
- Open CODEX_WINDOWS_FIXTURE_COMPARISON.md.
- Manually inspect every REVIEW or BLOCK item against the source drawing in ZWCAD.
- Check ModelSpace and every PaperSpace layout, layers, XREF declarations/status, blocks, ATTRIB/constant ATTDEF, dimensions and overrides, MLeader/Leader, table cells, raster/OLE/PDF underlays, proxy objects, and searchable text provenance.
- Verify original drawings were never saved or mutated. Compare file modification timestamps before and after when practical.

E. Defect handling
- If the failure is an environment/licensing/COM registration issue, document it without weakening completeness rules.
- If the failure is a reproducible HS-CAD defect, add a minimal regression test first, make the smallest safe fix, and rerun the complete fixture matrix.
- Never mark a record complete merely to make the test pass.
- Preserve fail-closed behavior for warnings, missing layouts, OCR-required content, unresolved XREFs, unsupported proxies, entity failures, and missing explicit completeness assertions.

F. Safe artifacts
Create or update a sanitized report at:
`docs/25_windows_zwcad_fixture_validation_result.md`

The report may include:
- Windows and ZWCAD versions;
- anonymized counts by extension and feature category;
- PASS/REVIEW/BLOCK totals;
- defect summaries and commit SHAs;
- commands executed;
- confirmation that drawings remained read-only.

The report must not include:
- source filenames or absolute paths;
- drawing text;
- coordinates/geometry;
- customer/project names;
- secrets or tokens.

G. Final checks and publish
- Run the focused Python tests, free-only validator, and compile/import smoke checks.
- Run the fixture matrix again after any code change.
- Review `git diff` for private data before staging.
- Commit only intended source, tests, and sanitized documentation.
- Push to origin/agent/drawing-index-v2.
- Add a PR #126 comment with validation totals, commands, commit SHA, remaining REVIEW/BLOCK items, and a clear merge recommendation.
- Keep the PR Draft if any BLOCK remains or if representative ZWCAD fixtures were not inspected.
- Mark ready for review only when there are zero BLOCK findings, tests pass, and the sanitized report is committed.

Stop conditions:
- Do not upload the drawings anywhere.
- Do not enable paid services or hosted OCR/model endpoints.
- Do not expose a Supabase service-role key.
- Do not merge PR #126.
- Do not rewrite unrelated history.
```

## Expected local outputs

```text
outputs/codex-windows-fixture-matrix/
├─ native-zwcad/
│  ├─ DRAWING_INDEX_V2_VALIDATION.md
│  ├─ console.log
│  └─ fileized/...
├─ fallback-only/
│  ├─ DRAWING_INDEX_V2_VALIDATION.md
│  ├─ console.log
│  └─ fileized/...
├─ CODEX_WINDOWS_FIXTURE_COMPARISON.md
├─ CODEX_WINDOWS_FIXTURE_COMPARISON.json
└─ CODEX_WINDOWS_VALIDATION_RESULT.md
```

The entire `outputs/` directory stays local and must not be committed.
