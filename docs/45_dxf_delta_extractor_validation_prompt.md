# Validation prompt for DXF Delta Extractor (Reverse Engineering Phase 1)

Repository:
khs0927/HS-CAD

Branch:
exp/reverse-engineering-delta-extractor

Base:
exp/xicad-policy-candidate-generator

Goal:
Validate that the DXF Delta Extractor correctly diffs two DrawingScanSnapshots to identify added, deleted, and modified entities.

Rules:
- Do not execute live ZWCAD commands in this test.
- Use mocked snapshots for extraction testing.

Commands:

git fetch origin exp/reverse-engineering-delta-extractor
git switch exp/reverse-engineering-delta-extractor

python -X utf8 -m pytest -q tests/test_dxf_delta_extractor.py

Confirm:
- `dxf_delta_extractor.py` correctly calculates Delta (Added, Deleted, Modified).
- The `DXFEntityModification` records `changed_keys` accurately.

Report:
- Branch/commit tested
- Unit test result
- Failures
- PR readiness
