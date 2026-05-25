# HS-CAD Golden/Domain Local TODO

Date: 2026-05-25

This TODO is stored separately from feature branches for later reuse.

## Purpose

The next HS-CAD implementation wave needs real local artifacts and project samples. Those items should not be faked remotely.

## Local-only tasks

1. Collect 3 to 5 representative HS-CAD output folders.
2. Run the schema inspector against each folder.
3. Save stable schema summaries as golden JSON fixtures.
4. Validate evidence counts and evidence kinds against the golden folders.
5. Apply the review output v7 package in a clean local branch.
6. Confirm generated review outputs are excluded from commits.
7. Run focused tests, critical lint, CLI help, and full pytest.
8. Prepare a follow-up implementation PR only after local validation succeeds.

## Suggested local branch

`feature/golden-domain-local-validation`

## Commit policy

Commit source, tests, docs, and workflows only. Keep generated outputs, temporary folders, archives, local databases, cache folders, and runtime drawing files out of commits.

## Stack reference

PR #66 -> PR #68 -> PR #70 -> PR #71 -> PR #74 -> Golden/Domain Megapack.
