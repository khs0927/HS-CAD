# HS-CAD Plan-Only Domain Rule Backlog

## Purpose

This backlog lists domain rules to add after evidence bridge stabilization. All rules remain plan-only.

## Architectural checks

- Room label to area polygon consistency.
- Door/window candidate attached to wall candidate.
- Wall layer role consistency.
- Dimension text and measured geometry mismatch review.
- Missing room label review.
- Duplicate room label review.

## Structural checks

- Column layer and block consistency.
- Centerline grid relation to columns.
- Beam/column intersection candidate review.
- Structural wall vs partition layer conflict review.

## Fire/life-safety checks

- Opening candidates requiring review.
- Protected door/window candidate tagging.
- Egress path candidate gaps.
- Fire compartment annotation detection.
- Manual review flags where evidence is weak.

## Energy/envelope checks

- Exterior wall spec text extraction.
- Roof panel spec text extraction.
- Window performance text extraction.
- Insulation thickness/spec consistency.
- South-region project review notes where metadata is available.

## XiCAD recommendation checks

- Produce recommendation records only.
- Include evidence IDs.
- Include dry-run command description text only.
- Do not execute or dispatch commands.
