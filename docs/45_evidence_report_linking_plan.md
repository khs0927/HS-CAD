# HS-CAD Evidence Report Linking Plan

## Goal

Make reports, bridge outputs, and review overlays refer to the same evidence IDs.

## Current state

The evidence bridge can produce evidence records and summaries. The next step is linking those IDs into:

- FINAL_REPORT.md
- EVIDENCE_BRIDGE_REPORT.md
- CROSS_VALIDATION.json
- QA overlay labels
- SQLite index rows

## Proposed linkage fields

```json
{
  "evidence_id": "legacy.layer_semantics.WAL1",
  "related_entity_ids": ["WAL-001"],
  "rule_ids": ["WALL_LAYER_ROLE_REVIEW"],
  "report_section": "Layer Semantics",
  "review_output_ref": "qa_overlay"
}
```

## Report sections

- Input summary
- Artifact summary
- Evidence kind summary
- Conflicts
- Domain rule findings
- Manual review queue
- Output artifacts

## Acceptance criteria

- Each warning/conflict has at least one evidence reference where available.
- Report summaries include evidence counts by kind.
- QA labels can show evidence IDs when provided.
- SQLite can query evidence by artifact, entity, kind, and rule.
