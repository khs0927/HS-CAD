# Execution Candidate Planner Contract

## Purpose

The next live-runner-related PR may only create an execution-candidate planner.

It must generate review artifacts. It must not perform production live runner behavior.

## Planner input contract

The planner may consume these evidence files:

```json
{
  "preflight_decision_json": "outputs/final_live_runner_preflight_guard/FINAL_LIVE_RUNNER_PREFLIGHT_DECISION.json",
  "manual_copy_only_interface_json": "outputs/final_live_runner_manual_copy_only_interface/FINAL_LIVE_RUNNER_MANUAL_COPY_ONLY_INTERFACE.json",
  "oda_conversion_contract_json": "outputs/oda_conversion_contract/ODA_CONVERSION_CONTRACT.json",
  "operator_approval_state": {
    "operator_approved": false,
    "manual_live_flag": false,
    "operator_name": "human-reviewer"
  }
}
```

## Planner output contract

The planner must produce a candidate plan with all live action flags disabled by default:

```json
{
  "task": "execution_candidate_planner",
  "status": "blocked | ready_for_human_review",
  "execution_candidate_allowed": false,
  "sendcommand_allowed": false,
  "saveas_allowed": false,
  "original_dwg_mutation_allowed": false,
  "xicad_alias_execution_allowed": false,
  "candidate_steps_for_human_review": [],
  "rollback_requirements": [],
  "audit_requirements": [],
  "blocked_reasons": [],
  "warnings": []
}
```

## Required planner behavior

The planner must block if any required evidence is missing, invalid, uncertain, or unsafe.

Required evidence:

- preflight decision status is `ready_for_manual_implementation_review`
- manual copy-only interface status is `ready_for_operator_review`
- ODA conversion contract status is acceptable for review
- ODA contract says `original_mutated=false`
- operator approval state is explicit and human-controlled

## Default safety decision

Even if all evidence is present, the planner must keep:

```text
execution_candidate_allowed = false
sendcommand_allowed = false
saveas_allowed = false
original_dwg_mutation_allowed = false
xicad_alias_execution_allowed = false
```

A `ready_for_human_review` status means only that a human can review candidate steps. It does not mean any live operation is approved.

## Recommended next PR title

```text
Add execution-candidate planner for manual copy-only live runner review
```

## Recommended files

```text
src/analysis/execution_candidate_planner.py
src/workers/execution_candidate_planner_worker.py
src/app/execution_candidate_planner_cli.py
tests/test_execution_candidate_planner.py
docs/160_execution_candidate_planner_prompt.md
docs/161_execution_candidate_planner_report.md
config/worker_manifest.execution_candidate_planner.patch.json
```

## Files not required

The planner PR should not modify runtime adapter or production runner files. It should use new planner-specific files and patch/candidate metadata only.
