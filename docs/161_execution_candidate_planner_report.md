# Execution Candidate Planner Report

## Purpose

Adds a review-only execution-candidate planner.

## This is not

- production runner
- live CAD operation
- drawing mutation
- automatic approval

## Safety defaults

- execution_candidate_allowed=false
- sendcommand_allowed=false
- saveas_allowed=false
- original_dwg_mutation_allowed=false
- xicad_alias_execution_allowed=false
- production_execution_allowed=false

## Validation

Fill after local validation:

- target tests:
- compileall:
- full pytest:
- src.main --help:
- CLI smoke:
- ruff:

## Output artifacts

- EXECUTION_CANDIDATE_PLANNER_DECISION.json
- EXECUTION_CANDIDATE_PLANNER_DECISION.md
- EXECUTION_CANDIDATE_STEPS_FOR_HUMAN_REVIEW.json
- EXECUTION_CANDIDATE_ROLLBACK_REQUIREMENTS.json
- EXECUTION_CANDIDATE_AUDIT_REQUIREMENTS.json
- EXECUTION_CANDIDATE_REFUSAL_REASONS.json
