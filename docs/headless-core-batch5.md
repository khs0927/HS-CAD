# xiCAD Headless Core Batch 5

This batch converts twelve legacy prompt/DCL workflows into explicit structured contracts:

- COI, COR: numeric comma formatting
- ND, NP, NS: group arithmetic
- NUC: bulk numeric calculation inside text
- PY: square metre to pyeong conversion using the recovered 0.3025 factor
- FAR: filtered find/replace
- TAP: prefix/suffix
- TD: text split
- TM: text merge
- TS: text height change

## Evidence discipline

The implementation uses strings recovered from the xiCAD 5.50 FAS4 resource stream. Where evidence conflicts, the contract does not guess. NP is the main example: the shortcut description suggests pairwise products while the recovered DCL label says group-sum multiplication. The caller must select one explicit mode.

## Safety

All MCP registrations are read-only planning tools. They return validated plans and never mutate CAD. Actual mutation remains blocked until reviewed CAD adapters, fixture postconditions, Undo restoration, and ZWCAD 2025/2026 smoke evidence exist.
