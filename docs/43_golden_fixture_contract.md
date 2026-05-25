# HS-CAD Golden Fixture Contract

## Goal

Define the contract for future golden fixtures without committing project-specific runtime outputs yet.

## Directory shape

```text
tests/golden/
  case_001_basic_floorplan/
    input_manifest.json
    legacy_outputs/
      FILEIZED_DRAWING.json
      LAYER_SEMANTICS.json
      TEXT_ROLE_INFERENCE.json
      AREA_ELEMENTS.json
      CROSS_VALIDATION.json
      DOMAIN_RULE_RESULTS.json
    expected/
      EVIDENCE_GRAPH.summary.json
      FUSION_MATRIX.summary.json
      EVIDENCE_BRIDGE_REPORT.summary.json
```

## Required metadata

Each `input_manifest.json` should include:

- case_id
- source_kind
- anonymized_project_type
- expected_artifacts
- known_limitations
- safety_notes

## Snapshot style

Snapshots should avoid large raw geometry dumps where possible. Prefer compact summaries:

- artifact_count
- evidence_count
- evidence kinds
- conflict count
- rule result count
- warning count
- stable evidence ID prefixes

## Excluded from fixture commits

Do not commit original DWG files, raw private project drawings, local runtime folders, local databases, or generated archives.
