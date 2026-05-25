# Add review-only main-code pipeline and evidence bridge

## Summary

This PR introduces a review-only HS-CAD main-code pipeline and evidence bridge layer. It keeps CAD execution disabled while adding structured fileizers, analysis graph outputs, evidence fusion, domain-rule planning, review DXF output generation, legacy artifact bridging, and PR hygiene tooling.

Branch: `feature/main-code-pipeline-overlay
`

## What changed

### CI
- `.github/workflows/.gitkeep`
- `.github/workflows/main-code-overlay-ci.yml`

### Docs
- `docs/.gitkeep`
- `docs/31_main_code_overlay_progress_report.md`
- `docs/32_main_code_overlay_v2_progress_report.md`
- `docs/33_main_code_overlay_v3_progress_report.md`
- `docs/34_main_code_overlay_v4_pr_readiness_report.md`
- `docs/35_main_code_overlay_pr_body.md`
- `docs/35_main_code_overlay_v5_pr_finalization_report.md`

### Other
- `APPLY_INSTRUCTIONS.md`
- `CODEX_MAIN_CODE_PROMPT.md`
- `CODEX_MAIN_CODE_V2_PROMPT.md`
- `CODEX_MAIN_CODE_V3_PROMPT.md`
- `CODEX_MAIN_CODE_V4_PROMPT.md`
- `CODEX_MAIN_CODE_V5_PROMPT.md`
- `LOCAL_AGENT_PROMPT.md`
- `MANIFEST.json`
- `hscad/`
- `src/hscad/`
- `src/main.py`

### Scripts
- `scripts/.gitkeep`
- `scripts/apply_hscad_main_code_overlay.py`
- `scripts/apply_hscad_main_code_overlay_v2.py`
- `scripts/apply_hscad_main_code_overlay_v3.py`
- `scripts/apply_hscad_main_code_overlay_v4.py`
- `scripts/apply_hscad_main_code_overlay_v5.py`
- `scripts/clean_hscad_runtime_artifacts.py`
- `scripts/generate_hscad_pr_body.py`
- `scripts/list_hscad_commit_candidates.py`
- `scripts/list_hscad_pr_commit_candidates.py`
- `scripts/register_evidence_bridge_cli.py`
- `scripts/register_main_code_cli.py`
- `scripts/register_review_only_cli.py`
- `scripts/validate_hscad_pr_ready.py`

### Tests
- `tests/.gitkeep`
- `tests/fixtures/.gitkeep`
- `tests/fixtures/legacy_artifact_factory.py`
- `tests/fixtures/minimal_floorplan_factory.py`
- `tests/test_commit_candidate_filter.py`
- `tests/test_evidence_bridge_contracts.py`
- `tests/test_evidence_bridge_pipeline_smoke.py`
- `tests/test_main_code_overlay_contracts.py`
- `tests/test_main_code_overlay_v2_contracts.py`
- `tests/test_main_code_pipeline_smoke.py`
- `tests/test_main_code_pipeline_v2_smoke.py`
- `tests/test_pr_hygiene_v4.py`
- `tests/test_pr_readiness_v5.py`
- `tests/test_review_cli_v4_contracts.py`

## Safety posture

- No CAD live execution is introduced.
- No ZWCAD COM call is introduced.
- No SendCommand execution is introduced.
- No XiCAD alias execution is introduced.
- Original DWG mutation remains disabled.
- Domain rule outputs remain plan-only/review-only.
- Runtime artifacts under `outputs/**` and `_incoming/**` are not intended for commit.

## Validation checklist

Run these before opening the PR:

```bash
python -X utf8 -m pytest -q tests/test_main_code_overlay_contracts.py tests/test_main_code_pipeline_smoke.py
python -X utf8 -m pytest -q tests/test_main_code_overlay_v2_contracts.py tests/test_main_code_pipeline_v2_smoke.py
python -X utf8 -m pytest -q tests/test_evidence_bridge_contracts.py tests/test_evidence_bridge_pipeline_smoke.py tests/test_commit_candidate_filter.py
python -X utf8 -m pytest -q tests/test_review_cli_v4_contracts.py tests/test_pr_hygiene_v4.py
python -X utf8 -m pytest -q tests/test_pr_readiness_v5.py
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
python -X utf8 scripts\validate_hscad_pr_ready.py --repo-root .
```

Expected baseline after v3/v4/v5 local validation:
- Full pytest should remain green.
- Ruff critical rules should pass.
- `src.main --help` should pass.
- Forbidden runtime files should be excluded from commit.

## Migration notes

- The new `src/hscad/*` pipeline can coexist with the older pipeline while integration proceeds.
- `src.main` registration should remain review-only and must not execute CAD commands.
- DXF fixtures should be generated at runtime rather than committed as binary/runtime artifacts.
- Future work should connect real analyzer/exporter outputs into the evidence bridge with golden artifacts.

## Follow-up PRs

1. Connect existing analyzer outputs to the new evidence model with real golden samples.
2. Strengthen optional `ezdxf` writer behavior and geometry fidelity.
3. Add more domain-rule checks while preserving plan-only safety.
4. Add Windows CAD adapter smoke tests that verify boundaries without live mutation.

