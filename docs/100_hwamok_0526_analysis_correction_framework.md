# Hwamok 0526 Drawing Analysis And Correction Framework

Date: 2026-05-26

Target drawing:

`G:\내 드라이브\##작업중\#계획\#화목동698-14\허가\화목동698-14 근린생활시설 신축공사_건축_0526.dwg`

This document is the required operating framework for agents that analyze or
prepare corrections for the Hwamok 0526 architectural drawing. It records the
current findings and the exact safe workflow that future agents must follow.

## 1. Safety Boundary

Agents must not mutate the original DWG during analysis.

Allowed by default:

1. Attach-only ZWCAD evidence probe.
2. ODA File Converter DWG-to-DXF conversion into an `outputs/` workspace.
3. ezdxf/fileized JSON extraction.
4. JSON validation, text/layer/block/dimension audits.
5. Dry-run correction planning.

Held unless explicitly approved:

1. `SendCommand`
2. `SaveAs`
3. XiCAD alias execution
4. Direct COM ModelSpace bulk scan as the primary analysis route
5. Any write operation against the active/original DWG

Correction execution must happen only on a copied DWG with a distinct SaveAs
target and an explicit operator approval.

## 2. Current Extraction Result

The active ZWCAD document was confirmed by attach-only probe.

Extraction route:

1. ZWCAD COM attach-only probe
2. ODA File Converter 27.1.0
3. Temporary DXF
4. ezdxf fileizer
5. fileized JSON validation

Result:

| Metric | Value |
|---|---:|
| Status | ok |
| Entities | 30,880 |
| Layers | 168 |
| Block symbols | 61 |
| Texts | 2,188 |
| Dimensions | 577 |
| JSON valid count | 1 |
| JSON invalid count | 0 |
| ODA external converter used | true |
| COM fallback used | false |

Artifacts:

- `outputs/hwamok_0526_active_probe/ZWCAD_COM_EVIDENCE_PROBE.json`
- `outputs/hwamok_0526_error_check/HWAMOK_0526_ERROR_CHECK.json`
- `outputs/hwamok_0526_error_check/HWAMOK_0526_ERROR_CHECK.md`
- `outputs/hwamok_0526_error_check/fileized/json/hwamok_0526_active.json`

## 3. Current Error Candidates

### 3.1 Suspicious Text

There are 8 suspicious text objects, all on layer `실명`.

| Handle | Current text | Layer | Meaning candidate | Action |
|---|---|---|---|---|
| AE10 | `10?` | 실명 | likely `10%` | visual confirm before correction |
| AE11 | `100?` | 실명 | likely `100%` | visual confirm before correction |
| AE16 | `5?` | 실명 | likely `5%` | visual confirm before correction |
| AE17 | `50?` | 실명 | likely `50%` | visual confirm before correction |
| AE1C | `5?` | 실명 | likely `5%` | visual confirm before correction |
| B181 | `??` | 실명 | unknown; planting table note/count area | do not auto-correct |
| B182 | `??` | 실명 | unknown; planting table note/count area | do not auto-correct |
| B183 | `??` | 실명 | unknown; planting table note/count area | do not auto-correct |

Context from nearby extracted texts indicates these objects are in the
landscape/planting quantity area. Nearby text includes:

- `조경의무면적의 ㎡ 당 1.0주 이상`
- `조경의무면적의 ㎡ 당 0.2주 이상`
- `교목수량의 20%이상`
- `관목수량의20%이상`
- `지역특성수 : 교목의 10%식재`
- `건축주지정플랜터`
- unit texts such as `주`, `본`

Decision:

- Percentage-looking values are high-confidence candidates, but still require
  visual confirmation before a mutation command is prepared.
- `??` values are low-confidence. They must be confirmed from the drawing view,
  PDF plot, or human instruction before any correction.

### 3.2 Layer Quality

Layer `0` contains 8,903 entities.

This is not an immediate drawing-breaking error. It is a quality and
standardization risk because semantic analysis becomes less reliable when too
many production objects remain on generic layer `0`.

Action:

1. Do not bulk-move layer `0` automatically.
2. Classify layer `0` objects by geometry, block, and nearby text first.
3. Produce a candidate layer-mapping report.
4. Move only explicitly approved classes on a copied DWG.

### 3.3 Anonymous Blocks

There are 19 anonymous/auto-generated block symbols.

Top examples:

| Block | Count |
|---|---:|
| A$C72A26C90 | 170 |
| A$C032327CB | 50 |
| A$C2BE44C31 | 17 |
| A$C043B7E4E | 4 |
| A$C60481E0E | 4 |

Decision:

- Anonymous blocks may be harmless imported symbols, copied details, or exploded
  external references.
- Do not rename or replace them directly.
- First group them by bounding boxes, insertion points, layers, and nearby
  labels.
- Prepare a block normalization candidate list only.

### 3.4 Text Height Outliers

There are 12 extracted text entities with height greater than 1000.

Decision:

- This may be normal for large title/table text depending on drawing scale.
- Treat as review candidate, not as a defect.
- Check whether they are title blocks, sheet labels, section/elevation markers,
  or accidental scaled text before planning edits.

### 3.5 Dimension Extraction

No dimension issue candidates were detected by the current extraction pass.

Decision:

- Continue to treat dimensions as review-sensitive.
- Do not rewrite dimensions automatically unless a later explicit dimension
  audit identifies a specific handle and approved target text/value.

## 4. Required Agent Workflow

Every agent must execute the workflow in this order. If a gate fails, stop and
write a report instead of continuing.

### Stage 0. Preflight

Run:

```powershell
python -X utf8 -m src.main hscad-converters --probe
python -X utf8 -m src.main hscad-zwcad-com-evidence-probe --out-dir outputs\hwamok_0526_active_probe --attach-only
```

Pass conditions:

- ODA File Converter is available.
- Probe status is `confirmed`.
- Active caption contains `화목동698-14` and `_건축_0526.dwg`.
- `sendcommand_used=false`
- `saveas_used=false`
- `original_dwg_mutated=false`

Stop conditions:

- Active drawing is not the target Hwamok 0526 DWG.
- ODA is unavailable.
- Any probe indicates mutation, SaveAs, SendCommand, or XiCAD execution.

### Stage 1. Fileize

Run the ODA/DXF/fileized extraction into a new output folder.

Required behavior:

- Source DWG is only read/copied.
- Temporary DXF is created under `outputs/`.
- `external_converter_used=true`.
- `command_fallback_used=false`.

Expected output:

- `fileized/json/*.json`
- `fileized/markdown/*.md`
- a summary JSON/Markdown report

### Stage 2. Validate

Run schema validation on the fileized JSON.

Pass condition:

- `invalid_count=0`

Stop condition:

- Any invalid JSON record.

### Stage 3. Detect Error Candidates

Run candidate checks in this order:

1. Suspicious text audit
2. Nearby text context extraction
3. Layer quality audit
4. Anonymous block audit
5. Text height outlier audit
6. Dimension audit

Each finding must include:

- handle if available
- layer
- current value
- location/insertion point if available
- confidence
- proposed action
- whether human/visual confirmation is required

### Stage 4. Classify Findings

Use these categories:

| Category | Meaning | Default action |
|---|---|---|
| Confirmed Error | Text/value is objectively wrong and target value is known | dry-run correction plan |
| High-Confidence Candidate | likely wrong, target likely known | visual confirmation first |
| Low-Confidence Candidate | wrong-looking but target unknown | no correction; request confirmation |
| Quality Risk | not wrong, but may reduce analysis/standard quality | report and plan normalization |
| Benign | normal for this drawing | no action |

For the current Hwamok 0526 pass:

- `10?`, `100?`, `5?`, `50?`, `5?`: High-Confidence Candidate
- `??`, `??`, `??`: Low-Confidence Candidate
- layer `0` overload: Quality Risk
- anonymous blocks: Quality Risk
- large text heights: Quality Risk
- dimensions: Benign in this pass

### Stage 5. Dry-Run Correction Plan

No correction command may be executed until a dry-run plan is produced.

The dry-run plan must include:

1. Original DWG path
2. Working copy path
3. SaveAs output path
4. Each target handle
5. Current text/value
6. Proposed text/value
7. Evidence from nearby context
8. Required confirmation status
9. Rollback plan

Do not include `B181`, `B182`, or `B183` in an executable correction plan until
their true text is known.

### Stage 6. Copied-DWG Execution Only

Execution is allowed only after explicit human approval.

Required paths:

- Original DWG path: active Hwamok 0526 source
- Working copy path: under a temporary or test work directory
- SaveAs result path: distinct from both original and working copy

Before execution:

- scan/fileize working copy
- record before counts
- record target handles

After execution:

- SaveAs only to approved result path
- fileize result DWG
- compare before/after
- confirm only intended text handles changed

## 5. Command Discipline For Future Agents

Agents must follow these rules when issuing commands:

1. Prefer `rg` and targeted commands for repo inspection.
2. Never run direct COM bulk scan as the first analysis tool.
3. Never run `SendCommand` during analysis.
4. Never run `SaveAs` on the active/original DWG.
5. Never edit original DWG without copied-DWG preflight.
6. Every generated artifact must live under `outputs/<task_name>/`.
7. Every stage must produce a JSON summary.
8. Every correction candidate must have evidence and confidence.
9. Unknown text such as `??` must not be guessed.
10. If source encoding looks corrupted in command output, pass paths through
    PowerShell environment variables or JSON files instead of embedding Korean
    paths directly in Python heredocs.

## 6. Recommended Next Tests

### Test A. Reproduce Current Audit

Goal: verify another agent can reproduce this state.

Expected:

- 30,880 entities, plus/minus small conversion variance
- 168 layers
- suspicious text count 8
- JSON valid count 1
- `external_converter_used=true`
- `command_fallback_used=false`

### Test B. Visual Confirmation Pack

Goal: create a focused pack for the 8 suspicious text handles.

Required output:

- table of handles and nearby text
- coordinate list
- screenshot or plotted crop if available
- proposed value only for visually confirmed rows

### Test C. Dry-Run Text Correction

Goal: create but do not execute a correction command.

Allowed rows:

- only confirmed percentage rows

Blocked rows:

- `B181`
- `B182`
- `B183`

### Test D. Copied-DWG Mutation Trial

Goal: execute correction on a copy only.

Required:

- explicit approval
- working copy
- distinct SaveAs target
- before/after fileized JSON
- delta report

## 7. Current Decision

The drawing is analyzable and structurally extractable. The immediate correction
priority is not geometry. It is the planting/landscape table text issue around
the `실명` layer.

Priority order:

1. Confirm and correct 5 percentage-like text corruption candidates.
2. Confirm the 3 unknown `??` planting table entries.
3. Produce layer `0` semantic split report.
4. Group anonymous blocks and decide whether any are reusable office-standard
   symbols.
5. Review the 12 large text-height outliers visually.

No automatic mutation should be performed until the visual confirmation and
dry-run plan are complete.
