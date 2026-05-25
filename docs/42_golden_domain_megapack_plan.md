# HS-CAD Golden/Domain Megapack Plan

## Purpose

This megapack continues after the roadmap stack and focuses on the next production wave:

1. Golden artifact fixtures.
2. Evidence-linked report assertions.
3. Plan-only domain rule expansion.
4. Local validation handoff.

## Remote-safe deliverables

This package intentionally avoids committing generated outputs or real drawing files. It adds planning documents, fixture schema contracts, and implementation prompts that can be used after local samples are available.

## Golden artifact target set

Representative HS-CAD output folders should provide stable JSON fixtures for:

- FILEIZED_DRAWING.json
- LAYER_SEMANTICS.json
- TEXT_ROLE_INFERENCE.json
- AREA_ELEMENTS.json
- SPATIAL_GRAPH.json
- SHAPELY_TOPOLOGY.json
- CROSS_VALIDATION.json
- DOMAIN_RULE_RESULTS.json
- EVIDENCE_GRAPH.json
- FINAL_REPORT.md snapshot where appropriate

## Domain rule target set

Plan-only rule families to expand:

- Architectural: rooms, openings, walls, dimensions, annotations.
- Structural: columns, walls, beams, grid/centerline consistency.
- Fire/life-safety review: egress candidates, protected opening candidates, review flags.
- Energy/envelope: insulation, panel, window, roof/wall spec text extraction.
- XiCAD recommendation: recommendation records only, no command execution.

## Acceptance criteria

- Golden fixtures are generated from real output folders, not invented.
- Evidence counts are asserted per fixture.
- Evidence IDs are stable enough to link reports and QA overlays.
- Domain rules emit plan-only results with evidence references.
- Runtime outputs stay outside commits.
