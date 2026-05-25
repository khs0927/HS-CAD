# HS-CAD Final Live Runner Deferred Safety Policy

## Policy

The final live runner must not be implemented until all of the following are true:

1. Phase 3~12 PR stack is merged into an integration branch.
2. Full pytest passes.
3. `python -X utf8 -m src.main --help` passes.
4. Worker manifest is verified.
5. CLI registration is verified.
6. Copied-DWG validation succeeds in a local Windows/ZWCAD environment.
7. Original DWG hash before/after remains unchanged.
8. XiCAD alias is allowlisted.
9. Unknown/destructive aliases remain blocked.
10. `operator_approved` is explicitly true.
11. A manual live flag is explicitly true.
12. The user confirms a copied DWG path and save-as target.

## Must remain false by default

- `execution_allowed`
- `sendcommand_allowed`
- `zwcad_com_allowed`
- `xicad_alias_execution_allowed`
- `original_dwg_mutation_allowed`

## First live candidate

The first live candidate must be:

- copied DWG only
- harmless allowlisted alias only
- one command only
- no batch execution
- audit log required
- before/after scan required
- delta report required
- rollback note required

## Not allowed

- running on original DWG
- batch SendCommand
- unknown alias
- destructive alias
- automatic operator approval
- auto-merging live-runner into main
