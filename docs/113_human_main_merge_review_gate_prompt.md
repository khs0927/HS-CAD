# HS-CAD Human Main Merge Review Gate Prompt

## Context

PR #58 has completed:

- Branch: `planning/post-main-local-validation-live-runner-safety`
- PR URL: https://github.com/khs0927/HS-CAD/pull/58
- Targeted test: `3 passed`
- Full pytest: `218 passed, 16 skipped`
- compileall: passed
- CLI smoke: passed
- Safety:
  - `main_merge_performed_by_this_bundle = false`
  - `local_validation_executed_by_this_bundle = false`
  - `final_live_runner_implemented = false`
  - `cad_execution_allowed_by_default = false`
  - `zwcad_com_sendcommand_allowed = false`
  - `xicad_alias_execution_allowed = false`
  - `domain_rule_command_execution_allowed = false`
  - `original_dwg_mutation_allowed = false`
  - `post_main_local_validation_manual_only = true`
  - `final_live_runner_requires_separate_safety_spec_pr = true`

## Goal

Generate the human main merge review gate.

This is the final review package before a human decides whether to merge review-only / plan-only / safety-guard scope to main.

This does not merge main.

## Branch

```powershell
git fetch origin planning/post-main-local-validation-live-runner-safety
git switch planning/post-main-local-validation-live-runner-safety
git switch -c human/main-merge-review-gate
```

## Apply ZIP

Save ZIP at:

```text
C:\Users\user\Downloads\HS-CAD-human-main-merge-review-gate.zip
```

Apply:

```powershell
Expand-Archive -Path "C:\Users\user\Downloads\HS-CAD-human-main-merge-review-gate.zip" -DestinationPath ".\_human_main_merge_review_patch" -Force
Copy-Item -Path ".\_human_main_merge_review_patch\*" -Destination "." -Recurse -Force
```

## Optional CLI registration

Add to `src/main.py` if desired:

```python
import src.app.human_main_merge_review_cli  # noqa: F401,E402
```

## Validation

```powershell
python -X utf8 -m pytest -q tests/test_human_main_merge_review_gate.py
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

If CLI was registered:

```powershell
python -X utf8 -m src.main hscad-human-main-merge-review-gate --repo-root . --post-main-safety-workspace outputs\post_main_local_validation_live_runner_safety --out-dir outputs\human_main_merge_review_gate
```

## Expected outputs

```text
HUMAN_MAIN_MERGE_REVIEW_GATE.json
HUMAN_MAIN_MERGE_REVIEW_GATE.md
HUMAN_MAIN_MERGE_OPERATOR_PROMPT.md
POST_MERGE_LOCAL_VALIDATION_PROMPT.md
POST_MERGE_LOCAL_VALIDATION_COMMANDS.json
FINAL_LIVE_RUNNER_DEFERRED_GUARD.json
```

## Commit

```powershell
git add src/analysis/human_main_merge_review_gate.py
git add src/workers/human_main_merge_review_gate_worker.py
git add src/app/human_main_merge_review_cli.py
git add tests/test_human_main_merge_review_gate.py
git add docs/113_human_main_merge_review_gate_prompt.md
git add docs/114_human_main_merge_review_gate_report.md
git add docs/115_main_merge_manual_runbook.md
git add docs/116_post_merge_local_validation_command_pack.md
git add config/worker_manifest.human_main_merge_review.patch.json
git add MAIN_IMPORT_HUMAN_MAIN_MERGE_REVIEW_PATCH.txt
git add README_APPLY_HUMAN_MAIN_MERGE_REVIEW.md

git commit -m "review: add human main merge review gate"
git push -u origin human/main-merge-review-gate
```

## PR

Base:

```text
planning/post-main-local-validation-live-runner-safety
```

Head:

```text
human/main-merge-review-gate
```

Title:

```text
Add human main merge review gate
```
