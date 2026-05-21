# 23. Preview Lifecycle and DXF Style Rewrite

Stage 24 extends Stage 23 by managing the lifecycle of an inserted image-to-CAD preview and by preparing a conservative DXF rewrite/report flow.

## Goals

- Rewrite/copy `result_wallsolid.dxf` into `styled_result_wallsolid.dxf`.
- Track preview insert sessions using `preview_session.json`.
- Remove or replace only the preview block reference recorded by handle.
- Generate QA markup for low confidence entities.
- Generate merge candidate plans without touching the original DWG.

## Safety Rules

- No Save / SaveAs.
- No Purge.
- No Explode.
- No block definition edits.
- No bulk delete of existing drawing objects.
- Real execution requires `--allow-execute`.
- Default mode is dry-run.
- Merge planner is plan-only.

## Commands

```bash
python -m src.dxf_style_rewriter.cli rewrite-dxf --source-dxf outputs/demo/result_wallsolid.dxf --styled-result generated/neuro_bridge/styled_result.json --style-context generated/style_context/style_context.json --out generated/stage24
```

```bash
python -m src.preview_lifecycle.cli create-session --plan generated/neuro_bridge/preview_insert_plan.json --insert-result generated/neuro_bridge/insert_preview_result.json --out generated/stage24
```

```bash
python -m src.qa_visual_review.cli build-review --styled-result generated/neuro_bridge/styled_result.json --preview-session generated/stage24/preview_session.json --out generated/stage24
```

```bash
python -m src.merge_planner.cli build-merge-candidate --preview-session generated/stage24/preview_session.json --style-context generated/style_context/style_context.json --styled-result generated/neuro_bridge/styled_result.json --out generated/stage24
```

## Outputs

```text
generated/stage24/styled_result_wallsolid.dxf
generated/stage24/dxf_rewrite_report.json
generated/stage24/dxf_rewrite_report.md
generated/stage24/preview_session.json
generated/stage24/preview_session.md
generated/stage24/qa_markup.json
generated/stage24/qa_review_report.md
generated/stage24/merge_candidate_plan.json
generated/stage24/merge_candidate_report.md
```
