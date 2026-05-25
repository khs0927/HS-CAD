# HS-CAD Future PR Roadmap

## PR A: Golden artifact fixtures

Goal: convert representative HS-CAD output directories into stable JSON fixtures.

Deliverables:

- schema report fixtures
- evidence graph snapshots
- bridge report snapshots
- focused regression tests

## PR B: Review output implementation

Goal: apply the v7 package after local validation.

Deliverables:

- structured QA labels
- low-confidence markers
- review output manifest
- output inspection tests

## PR C: Evidence-linked reports

Goal: connect stable evidence IDs to final reports and review overlays.

Deliverables:

- evidence ID table
- conflict summary
- action recommendation table
- SQLite index assertions

## PR D: Plan-only domain rule expansion

Goal: add deeper rule coverage while keeping behavior review-oriented.

Deliverables:

- architecture rules
- structure rules
- fire/egress review rules
- energy/envelope review rules
- XiCAD recommendation records only

## PR E: Optional file adapter expansion

Goal: add optional adapters for PDF/image workflows without forcing dependencies.

Deliverables:

- optional import guards
- adapter status reports
- coordinate normalization tests
