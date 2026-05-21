# Merge Candidate Plan

- Mode: plan_only
- Can merge: False
- Requires user approval: True
- Source preview session: generated/stage24/preview_session.json

## Merge Groups
- raw_line: action=review_before_merge, layer=QA-REVIEW, confidence=0.69, count=9
- wall_centerline: action=review_before_merge, layer=QA-REVIEW, confidence=0.41, count=9
- wall_polygon: action=review_before_merge, layer=QA-REVIEW, confidence=0.29, count=9
- door: action=review_before_merge, layer=QA-REVIEW, confidence=0.368, count=1
- window: action=review_before_merge, layer=QA-REVIEW, confidence=0.356, count=1
- text: action=review_before_merge, layer=QA-REVIEW, confidence=0.32, count=1

## Blocked Actions
- save
- save_as
- purge
- explode
- explode_block_definition
- bulk_delete_existing_objects
- auto_remap_existing_layers

## Warnings
- Stage 24 creates a merge candidate plan only; it does not merge into DWG.
