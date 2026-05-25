# HS-CAD Final Live Runner Manual Copy-only Interface Prompt

## Purpose

This package adds a review-only operator interface after the preflight guard. It produces confirmation text, audit intent, refusal output, and a next-PR plan.

## Scope

- Read the preflight decision artifact.
- Generate a human operator prompt.
- Generate refusal reasons when preflight is not ready.
- Keep all live execution flags disabled.

## Out of scope

- CAD execution.
- DWG mutation.
- Automatic approval.
- Production runner behavior.

## Recommended next step

After this interface is reviewed, a separate execution-candidate PR may be planned. That future PR still requires human approval and must remain copy-only.
