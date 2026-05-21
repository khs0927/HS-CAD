# Merged QA Report

## Image-to-CAD QA
- no neuro qa report loaded

## Style Context Warnings
- local_style_sample: path not provided
- zium_sheet_area: path not provided
- active_form_sample: path not provided
- active_scan: path not provided
- reference_style_profile: path not provided

## Preview Plan Warnings
- model_adapter_missing: Raster2Seq third_party/Raster2Seq not found
- model_adapter_missing: PlanParser third_party/planparser not found
- license_review_required: PlanParser/AGPL style dependencies must be reviewed before commercial use
- optional_dependency_missing: ultralytics is not installed
- wall_thickness_fallback
- low_confidence_entities: 12
- scale_confidence: 0.86
- wall_thickness_source: standard_fallback
- local_style_sample: path not provided
- zium_sheet_area: path not provided
- active_form_sample: path not provided
- active_scan: path not provided
- reference_style_profile: path not provided

## Manual Review Checklist
- Check DXF insertion scale and base point.
- Check QA-REVIEW and AI_LOWCONF entities before merging into office DWG.
- Do not save the original DWG until preview is verified.
- Use UNDO BACK if the inserted preview is not correct.
