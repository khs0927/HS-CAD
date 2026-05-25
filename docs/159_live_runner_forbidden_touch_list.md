# Live Runner Forbidden Touch List

## Purpose

This document lists files and behaviors that must not be changed by the next execution-candidate planner PR.

The goal is to keep the next PR review-only and contract-driven.

## Do not touch runtime files

The next planner PR must not edit these files:

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

## Use candidate or patch files instead

If integration is needed, use patch/candidate files such as:

```text
config/worker_manifest.execution_candidate_planner.patch.json
MAIN_IMPORT_EXECUTION_CANDIDATE_PLANNER_PATCH.txt
docs/160_execution_candidate_planner_prompt.md
```

## Forbidden default behaviors

The next PR must not enable the following by default:

```text
live CAD execution
SendCommand
SaveAs
DXFOUT
XiCAD alias execution
original DWG mutation
automatic operator approval
automatic merge to main
```

## Required default flags

The next planner output must keep:

```text
execution_candidate_allowed = false
sendcommand_allowed = false
saveas_allowed = false
original_dwg_mutation_allowed = false
xicad_alias_execution_allowed = false
```

## Allowed work

Allowed in the next planner PR:

- read evidence JSON files
- validate contract status
- generate candidate steps for human review
- generate rollback requirements
- generate audit requirements
- generate refusal reasons
- write markdown and JSON review artifacts
- add tests for planner decisions

## Review rule

If a PR changes any forbidden runtime file, it must include a separate rationale document and must not be merged automatically.
