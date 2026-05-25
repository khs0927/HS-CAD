# CODEX MAIN CODE V4 PROMPT

You are working in the local HS-CAD repository after v1/v2/v3 overlays passed validation.

Goal:
- Apply v4 overlay.
- Register review-only CLI commands if the patch diff is safe.
- Validate that no CAD execution is introduced.
- Prepare a clean PR candidate list without committing.

Key safety constraints:
- Do not execute CAD.
- Do not call ZWCAD COM.
- Do not call SendCommand.
- Do not execute XiCAD aliases.
- Do not mutate original DWG files.
- Do not commit outputs, incoming overlays, caches, zip files, DWG, or runtime DXF.

Required validations:
- v4 targeted tests
- standalone CLI help
- register_review_only_cli dry-run
- optional --apply only after safe diff review
- ruff critical
- src.main help
- full pytest
- commit candidate filter
