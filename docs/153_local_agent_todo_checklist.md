# 153. Local Agent TODO Checklist

Date: 2026-05-25

This document is the local-agent execution checklist for HS-CAD while many PRs and branches are active at the same time.

Use this checklist before, during, and after any local coding task.

## Goal

Prevent conflicts from concurrent work and ensure that every local task leaves a traceable TODO/result document before push.

## 0. Current rule

Do not start with broad code generation. Start with branch state, open PR scope, and safety posture.

The default action is:

```text
review-only, dry-run-only, no CAD mutation
```

## 1. Before starting work

Run:

```powershell
git switch main
git pull origin main
git fetch origin --prune
git status --short
git log --oneline --decorate -5
git rev-parse origin/main
```

Record this SHA:

```text
START_ORIGIN_MAIN_SHA=
```

Create a task branch:

```powershell
git switch -c <task-branch-name>
```

## 2. Decide task type

Choose exactly one task type:

```text
[ ] docs-only
[ ] tests-only
[ ] review-only pipeline
[ ] no-COM DXF/fileized analysis
[ ] preflight/safety guard
[ ] CLI registration candidate only
[ ] worker manifest candidate only
[ ] live CAD execution design only
[ ] live CAD execution implementation - blocked unless explicitly approved
```

If the task is live CAD execution implementation, stop unless a current approved safety gate explicitly permits it.

## 3. Files that need extra caution

High-risk files:

```text
src/main.py
config/worker_manifest.json
requirements.txt
pyproject.toml
.github/workflows/*.yml
src/adapters/zwcad_com_adapter.py
src/integrations/zwcad_live/**
src/analysis/final_live_runner.py
src/app/zwcad_live_runner_cli.py
```

If any of these files must be changed, first create a TODO/candidate file instead of changing the file directly.

Suggested candidate files:

```text
outputs/megapack_main_import_candidates.txt
outputs/megapack_worker_manifest_candidates.json
outputs/high_risk_file_change_plan.md
```

## 4. Coding rules

Allowed by default:

```text
- JSON report generation
- Markdown report generation
- review-only analysis
- no-COM DXF/fileized parsing
- dry-run command plan generation
- approval/preflight/refusal artifact generation
- tests and docs
```

Blocked by default:

```text
- ZWCAD SendCommand
- CHPROP execution
- SAVEAS execution
- DXFOUT execution
- XiCAD alias execution
- original DWG mutation
- automatic human approval
- auto merge to main
```

## 5. During work

After each meaningful file group, run:

```powershell
git status --short
git diff --stat
```

If new unplanned files appear under these paths, inspect them before continuing:

```text
outputs/**
*.dwg
*.dxf
*.zip
*.sqlite
*.sqlite3
__pycache__/**
.pytest_cache/**
```

Do not commit local runtime artifacts unless the task explicitly asks for fixtures or documentation artifacts.

## 6. Before finishing code

Fetch latest remote state again:

```powershell
git fetch origin --prune
git rev-parse origin/main
```

Record:

```text
END_ORIGIN_MAIN_SHA=
```

If `START_ORIGIN_MAIN_SHA` and `END_ORIGIN_MAIN_SHA` differ, main changed during the task.

Then run:

```powershell
git merge-base --is-ancestor origin/main HEAD
```

If this fails, stop and report:

```text
main moved during local work; rebase required before final commit/push
```

## 7. Conflict scan before commit

Check:

```powershell
git diff --name-only
```

Then answer:

```text
[ ] Did this task touch src/main.py?
[ ] Did this task touch config/worker_manifest.json?
[ ] Did this task touch live CAD runner files?
[ ] Did this task add runtime outputs?
[ ] Did this task add binaries?
[ ] Did this task overlap with open PRs?
```

If yes to any item, include a conflict note in the TODO result.

## 8. Required tests

For docs-only work:

```powershell
python -X utf8 -m src.main --help
```

For no-COM QA work:

```powershell
python -X utf8 -m pytest -q tests/test_reviewcontext_dxf_merge.py tests/test_qa_pipeline.py
```

For preflight guard work:

```powershell
python -X utf8 -m pytest -q tests/test_final_live_runner_preflight_guard.py
```

For broader source changes:

```powershell
python -X utf8 -m compileall -q src tests
python -X utf8 -m pytest -q
python -X utf8 -m src.main --help
```

If full pytest fails due to Windows/ZWCAD/ODA/CAD dependency, classify it separately from task-related failures.

## 9. Required TODO result document

Before commit, create:

```text
outputs/local_agent_todo_result.md
```

Template:

```markdown
# Local Agent TODO Result

## Branch
-

## Task type
-

## Base state
- START_ORIGIN_MAIN_SHA:
- END_ORIGIN_MAIN_SHA:
- main moved during work: yes/no

## Files touched
-

## High-risk files
- src/main.py modified: yes/no
- config/worker_manifest.json modified: yes/no
- live CAD runner files modified: yes/no

## Safety
- CAD mutation: no
- SendCommand: no
- SaveAs: no
- DXFOUT: no
- XiCAD alias execution: no
- original DWG mutation: no

## Tests
- targeted:
- compileall:
- full pytest:
- CLI smoke:

## Open PR overlap
-

## Issues
-

## Next action
-
```

If outputs are not intended for commit, copy the final summary into a docs file or PR body before pushing.

## 10. Commit rule

Before commit:

```powershell
git status --short
git diff --stat
git diff -- src/main.py
git diff -- config/worker_manifest.json
```

Commit with a narrow message:

```powershell
git add <only-intended-files>
git commit -m "<specific task message>"
```

## 11. Push rule

Before push, run the final remote check once more:

```powershell
git fetch origin --prune
git rev-parse origin/main
git merge-base --is-ancestor origin/main HEAD
```

If safe:

```powershell
git push origin <task-branch-name>
```

Open a PR with:

```text
- task type
- files touched
- safety statement
- tests run
- main moved during work: yes/no
- high-risk files touched: yes/no
```

## 12. GitHub approval prompt note

GitHub approval prompts are controlled by the ChatGPT/GitHub connector security layer. A user may need to click approval for write operations. To reduce prompts:

```text
- batch related changes into one create_tree or one file where possible
- avoid repeated update_file calls
- create one PR at the end
- prefer docs-only PRs for coordination work
- do not ask for many tiny pushes
```

A single approval for all future GitHub write actions cannot be guaranteed from this workflow.

## 13. Recommended next project action

Do not add more live-runner implementation until the safety stack is clear.

Recommended order:

```text
1. Merge docs/parallel-work-conflict-todo if accepted.
2. Review PR #75 final live runner preflight guard.
3. Keep PR #69 final live runner implementation on hold.
4. Validate PR #77 manual copy-only interface only after PR #75 is stable.
5. Review stacked feature PRs in base-branch order.
```
