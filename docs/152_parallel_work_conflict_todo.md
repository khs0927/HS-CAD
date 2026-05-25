# 152. Parallel Work Conflict Control TODO

Date: 2026-05-25

This document records the operating rule for HS-CAD while multiple local agents, ChatGPT sessions, and GitHub branches are working in parallel.

## Current situation

Many PRs and branches are active at the same time. Some target `main`, while others are stacked on feature branches. The project must avoid accidental overwrite, duplicate CLI registration, unsafe live CAD execution, and worker manifest conflicts.

## Non-negotiable rules

1. Do not push directly to `main`.
2. Do not auto-merge active PRs unless the target branch and safety posture are verified.
3. Do not edit `src/main.py` and `config/worker_manifest.json` in broad generated-code PRs.
4. Do not run ZWCAD COM SendCommand, CHPROP, SAVEAS, DXFOUT, XiCAD alias execution, or original DWG mutation unless a dedicated safety gate explicitly approves it.
5. Prefer no-COM DXF/fileized analysis for fast review.
6. Keep live-runner work behind preflight guard, human approval, copied-DWG-only execution, and rollback evidence.
7. Every coding task must re-check whether `main` or the target branch moved before finishing.

## Required branch workflow

For every new coding task:

```powershell
git switch main
git pull origin main
git switch -c <task-branch>
```

Before committing:

```powershell
git fetch origin
git status --short
git diff --stat
git log --oneline --decorate -5
git rev-parse HEAD
git rev-parse origin/main
```

Before final report or push:

```powershell
git fetch origin
git merge-base --is-ancestor origin/main HEAD
```

If this command fails, main has moved or the branch is not based on current main. Stop and rebase or report the conflict risk before continuing.

## GitHub conflict check before finishing code

At the end of any code-writing task, the agent must check:

- Whether new commits were pushed to `main` after the branch was created.
- Whether the same files were changed in open PRs.
- Whether the PR base is `main` or a feature branch.
- Whether the PR is stacked and depends on another unmerged PR.
- Whether `src/main.py` or `config/worker_manifest.json` were modified.
- Whether outputs, DWG, DXF, ZIP, SQLite, cache, or local-only artifacts were accidentally staged.

## High-risk files

Do not modify these files without explicit narrow task scope:

```text
src/main.py
config/worker_manifest.json
requirements.txt
pyproject.toml
.github/workflows/*.yml
src/adapters/zwcad_com_adapter.py
src/integrations/zwcad_live/**
```

For `src/main.py`, create a candidate import list first:

```text
outputs/megapack_main_import_candidates.txt
```

For worker registration, create a candidate manifest first:

```text
outputs/megapack_worker_manifest_candidates.json
```

## Open PR grouping guideline

### Main-target safety PRs

These can be reviewed first if they remain non-mutating:

- ZWCAD COM evidence probe
- final live runner safety spec/design-only approval
- final live runner preflight guard
- human verification / runbook documents

### Main-target high-risk PRs

These should wait until safety gates and human review are complete:

- final live runner implementation
- ZWCAD live runner CLI registration
- any PR that permits SendCommand, SaveAs, XiCAD alias execution, or CAD mutation

### Stacked feature PRs

These should not be merged out of order:

- roadmap branches
- evidence bridge schema branches
- review output quality branches
- megapack finalization branches

## Recommended immediate merge order

1. Review and validate safety-only PRs first.
2. Keep live execution PRs open until preflight guard and copied-DWG-only validation are proven.
3. Merge roadmap/stacked PRs only after their base branch chain is clear.
4. After each merge, update local main and re-run targeted smoke tests.

## Local agent TODO template

Every local agent must write a short TODO result before push:

```markdown
# Local Agent TODO Result

## Branch
-

## Base
- origin/main SHA before work:
- origin/main SHA before finish:

## Files touched
-

## Conflict check
- main moved during work: yes/no
- overlapping PR files: yes/no
- src/main.py modified: yes/no
- config/worker_manifest.json modified: yes/no

## Tests
- targeted:
- full:

## Safety
- CAD mutation: no
- SendCommand: no
- SaveAs: no
- XiCAD alias execution: no
- original DWG mutation: no

## Next action
-
```

## Current next action

No more broad code generation should be pushed until the open PR set is triaged. The safest next task is a PR triage document or a local-only validation report that classifies each open PR as:

- merge now
- test first
- rebase required
- keep stacked
- hold due to live CAD risk

## GitHub approval note

Some GitHub connector actions require user confirmation in the ChatGPT UI. This is a platform authorization behavior. To reduce prompts, prefer fewer write operations: one branch, one file or one batched tree commit, and one PR. Do not split simple documentation work into many create/update calls.
