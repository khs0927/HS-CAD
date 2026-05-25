# PR69 Hold And Live Runner Policy

## Purpose

This document records the current live-runner policy boundary for HS-CAD.

The next safe step is not production live runner execution. The next safe step is an execution-candidate planner that produces review artifacts only.

## PR69 status

PR69 is open, not merged, and not mergeable at the time of review.

PR69 title:

```text
feat: implement FinalLiveRunner and register ZWCAD live runner CLIs
```

Because it attempts direct FinalLiveRunner implementation while conflicting/failing, it must remain on hold.

## Required decision

```text
PR69_HOLD = true
PR69_DIRECT_MERGE_ALLOWED = false
```

## Rationale

PR69 must not be merged directly while any of these are true:

- merge conflicts exist
- checks fail
- live runner execution code is mixed with safety review code
- SendCommand, SaveAs, DXFOUT, XiCAD alias execution, or original DWG mutation could be enabled by default
- ODA conversion work is coupled directly to live runner execution

## Default live runner policy

The default posture is blocked-by-default:

```text
live_cad_execution_allowed_by_default = false
sendcommand_allowed_by_default = false
saveas_allowed_by_default = false
dxfout_allowed_by_default = false
xicad_alias_execution_allowed_by_default = false
original_dwg_mutation_allowed_by_default = false
```

## Approved next step

The next live-runner-related PR may only create candidate planning artifacts.

Approved next PR title:

```text
Add execution-candidate planner for manual copy-only live runner review
```

Approved scope:

- consume preflight decision evidence
- consume manual copy-only interface evidence
- consume ODA conversion contract evidence
- produce candidate steps for human review
- produce rollback and audit requirements
- keep all execution flags false by default

Not approved:

- production live runner
- automatic CAD command execution
- automatic SaveAs
- automatic DXFOUT
- automatic XiCAD alias execution
- original DWG mutation

## Files that must not be touched in the next PR

The execution-candidate planner PR should not touch these files unless a separate reviewed plan explicitly allows it:

```text
src/adapters/zwcad_com_adapter.py
src/app/zwcad_live_runner_cli.py
src/analysis/final_live_runner.py
src/integrations/zwcad_live/**
config/worker_manifest.json
requirements.txt
pyproject.toml
.github/workflows/**
```

Use patch/candidate files instead of editing high-risk runtime files directly.
