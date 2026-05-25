# Execution Candidate Planner Prompt

## Purpose

This stage adds a review-only execution-candidate planner after the live runner policy and ODA contract review.

The planner consumes evidence JSON files and produces candidate steps for human review.

## Scope

The planner may read:

- Final Live Runner preflight decision JSON
- Manual copy-only interface JSON
- ODA conversion contract JSON
- explicit operator approval state

The planner may write:

- planner decision JSON/MD
- candidate steps for human review
- rollback requirements
- audit requirements
- refusal reasons

## Safety

This planner is not a production runner.

All action flags must remain false:

- `execution_candidate_allowed=false`
- `sendcommand_allowed=false`
- `saveas_allowed=false`
- `original_dwg_mutation_allowed=false`
- `xicad_alias_execution_allowed=false`
- `production_execution_allowed=false`

## CLI

```powershell
python -X utf8 -m src.main hscad-execution-candidate-planner --operator-approved --manual-live-flag --out-dir outputs\execution_candidate_planner
```

If evidence files are missing, blocked output is expected.

## Next stage

The next stage is still human review, not production execution.
