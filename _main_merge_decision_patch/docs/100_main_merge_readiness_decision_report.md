# HS-CAD Main Merge Readiness Decision Report

## Purpose

This patch creates the final decision package before human main merge review.

## It creates

- `MAIN_MERGE_READINESS_DECISION.json`
- `MAIN_MERGE_READINESS_DECISION.md`
- `MAIN_MERGE_PR_BODY_DRAFT.md`
- `POST_MERGE_LOCAL_VALIDATION_PROMPT.md`

## Allowed in main

- review-only analysis pipeline
- plan-only Domain Rule bridge
- copied-DWG validation planning
- manual live candidate guard
- safety policy docs

## Not allowed in main

- final live runner
- ZWCAD COM SendCommand execution
- XiCAD alias execution
- Domain Rule Command Plan execution
- original DWG mutation
- automatic operator approval

## Safety

Main merge remains human-review only. This package does not merge main.
