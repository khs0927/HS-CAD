# 162. Current Open PR Triage

Date: 2026-05-25

## Purpose

This document is a mid-check coordination table for HS-CAD while several local/remote agents are working at the same time.

It records the latest open PR groups and recommends whether each group should be merged, held, closed, rebased, or reviewed first.

## Baseline

Latest checked main SHA:

```text
70c8e4df3583fc9fcd8c01937dc7636444eafcf6
```

This is a documentation-only triage task.

No code, CLI registration, worker manifest, CAD adapter, live runner, DWG/DXF, or runtime output file is changed by this document.

## Global safety posture

Default remains:

```text
review-only
plan-only
dry-run-only
no CAD mutation
no SendCommand
no SaveAs
no DXFOUT
no XiCAD alias execution
no original DWG mutation
```

## Immediate actions

| Priority | Action | PRs | Decision |
|---:|---|---|---|
| 1 | Stop duplicate PR82 extraction | #82, #101, #102, #103 | Do not create new extraction PRs until main is stable |
| 2 | Keep live runner implementation blocked | #69 | HOLD |
| 3 | Review execution-candidate planner carefully | #105 | Test first, do not merge blindly |
| 4 | Close or supersede old staging PRs if already absorbed | #38, #82 | Keep as inspection only or close after audit |
| 5 | Process stacked feature chains in base order | #41-#58, #66-#76 | Do not merge out of order |

## PR-by-PR triage

### Main-target recent PRs

| PR | Title | Current recommendation | Reason |
|---:|---|---|---|
| #105 | Add execution candidate planner | TEST FIRST / REVIEW | Mergeable, but touches `src/main.py` and adds execution-candidate planning; verify all execution flags remain false |
| #103 | Add PR82 extraction status | MERGEABLE DOCS, but check duplicate | Docs-only status report; safe if it does not duplicate newer docs |
| #102 | Document PR82 CLI command contracts | REBASE or REVIEW | Not mergeable at check time; docs-only but may overlap PR82 candidate docs |
| #101 | Fix PR82 spatial text role inference | HOLD or CLOSE if already absorbed | Body says no source change needed; output report should not be committed |
| #82 | Review PR38 generated megapack validation branch | DO NOT MERGE | Large generated PR; inspection source only |
| #69 | FinalLiveRunner / ZWCAD live runner | HOLD | Live runner implementation path; merge only after preflight/copy-only/rollback gates pass |
| #67 | Human verification pack | REBASE / REVIEW | Docs-only but old base; likely superseded by newer coordination docs |
| #38 | Combined generated megapacks staging | CLOSE or keep as archive | Staging-only draft; content appears superseded by PR82 split work and current main extractions |

### PR82-related state

Safe PR82 code groups appear mostly present on `main`:

```text
src/spatial/**
src/pdf_raster/**
src/ocr/**
src/graph/**
src/analytics/**
```

Therefore do not re-extract these groups from PR82 unless a specific missing file is proven.

Remaining PR82 work should be documentation/candidate-only:

```text
docs/pr82_main_import_candidates.md
docs/pr82_worker_manifest_candidates.md
docs/pr82_extraction_status_after_parallel_merges.md
```

Do not directly edit:

```text
src/main.py
config/worker_manifest.json
```

### Stacked analysis/review chains

These PRs should be handled only in stack order. They are not independent main PRs.

| Chain | PRs | Recommendation |
|---|---|---|
| Phase/analysis pipeline chain | #41 -> #42 -> #43 -> #44 -> #45 -> #46 -> #47 -> #48 -> #49 -> #50 -> #51 -> #52 -> #53 -> #54 -> #55 -> #57 -> #58 | Keep stacked; merge only after root base is validated |
| Evidence/roadmap chain | #66 -> #68 -> #70 -> #71 -> #74 -> #76 | Keep stacked; do not merge out of order |
| Domain-rule experiment chain | #28 -> #30 -> #31 -> #33 -> #37 | Keep experimental; do not mix into main until safety gates are proven |
| Legacy megapack chain | #29 -> #32 -> #34 -> #35 | Review only if not superseded by main PR82 extraction |

## Risk hotspots

### High-risk files

```text
src/main.py
config/worker_manifest.json
src/adapters/zwcad_com_adapter.py
src/integrations/zwcad_live/**
src/analysis/final_live_runner.py
src/app/zwcad_live_runner_cli.py
```

Any PR touching these needs explicit review and targeted tests.

### Runtime/binary artifacts

Do not merge:

```text
outputs/**
artifacts/**/*.zip
*.dwg
*.dxf
*.sqlite
*.sqlite3
__pycache__/**
.pytest_cache/**
```

## Recommended next sequence

### Step 1: Pause source extraction

No new PR82 source extraction until current main is stable.

### Step 2: Validate PR #105 locally before merge

Required checks:

```powershell
python -X utf8 -m pytest -q tests/test_execution_candidate_planner.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

Review safety fields:

```text
execution_candidate_allowed=false
sendcommand_allowed=false
saveas_allowed=false
original_dwg_mutation_allowed=false
xicad_alias_execution_allowed=false
production_execution_allowed=false
```

### Step 3: Clean PR82 follow-ups

Likely decisions:

```text
#82: keep as inspection or close after all accepted pieces are confirmed
#101: close if no source diff is needed and outputs report is not desired
#102: rebase/update docs if still useful
#103: merge only if not duplicating newer status docs
```

### Step 4: Keep PR #69 blocked

Do not merge #69 until all are true:

```text
preflight guard merged
copy-only interface validated
rollback manifest proven
original DWG mutation blocked
operator approval gate required
local ZWCAD validation completed on copied DWG only
```

## Local agent instruction

All agents should use this rule before continuing:

```powershell
git switch main
git pull origin main
git fetch origin --prune
git diff --name-only origin/main...HEAD
```

If their branch touches files already changed in main, stop and rebase or close the branch.

## Final status

This document does not approve additional code generation.

Current safest action:

```text
triage open PRs
close superseded PRs
validate PR #105
keep PR #69 held
process stacked PRs only in base order
```
