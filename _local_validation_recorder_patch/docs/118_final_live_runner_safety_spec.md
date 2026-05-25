# HS-CAD Final Live Runner Safety Spec

## Status

Design specification seed only. This PR must not implement the runner.

## PR #59 context

PR #59 created the final human main merge review gate and reported:

- targeted test: 3 passed
- full pytest: 227 passed, 16 skipped
- CLI smoke: passed
- human review decision: ready yes
- final live runner remains not implemented

## Mandatory gates

1. PR #55~#59 human approval completed.
2. Main has review-only / plan-only / safety-guard scope merged.
3. Local copied-DWG scan validation passed.
4. Local copied-DWG SaveAs validation passed.
5. C:/xicad policy candidates validated.
6. Phase 12 manual candidate guard validated.
7. Operator approval policy reviewed.
8. Risk register reviewed.

## Hard requirements

- copied DWG only
- original DWG must be refused
- save_as_target must be distinct
- alias must be allowlisted
- unknown alias must fail closed
- destructive alias must fail closed
- manual_live_flag required
- operator_approved required
- one harmless command only in first implementation
- before scan required
- after scan required
- delta report required
- append-only audit required
- original hash before/after must remain unchanged
