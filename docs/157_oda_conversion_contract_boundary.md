# ODA Conversion Contract Boundary

## Purpose

ODA conversion work must remain separate from live runner planning.

The live-runner side should consume a neutral JSON contract only. ODA-specific implementation details belong behind a separate adapter or worker boundary.

## Boundary rule

```text
live_runner_owns_oda_implementation = false
live_runner_consumes_oda_contract_json = true
```

## Neutral input contract

```json
{
  "original_dwg_path": "C:/cad/test/original.dwg",
  "working_copy_path": "C:/cad/test_work/copy.dwg",
  "output_workspace": "outputs/oda_conversion_candidate",
  "requested_target_dxf_version": "R2018"
}
```

## Neutral output contract

```json
{
  "status": "converted | blocked | failed | unavailable",
  "converted_dxf_path": "outputs/oda_conversion_candidate/copy_R2018.dxf",
  "log_path": "outputs/oda_conversion_candidate/ODA_CONVERSION_LOG.txt",
  "converter_used": "ODAFileConverter | other",
  "original_mutated": false,
  "warnings": [],
  "failure_reason": ""
}
```

## Required safety field

The output contract must always include:

```text
original_mutated = false
```

If this cannot be proven, the status must be `blocked`.

## Downstream planning rule

A downstream execution-candidate planner may read `ODA_CONVERSION_CONTRACT.json`.

It must not treat missing or uncertain ODA evidence as success.

Planning must be blocked if:

- status is not `converted`
- `original_mutated` is not false
- required output paths are missing
- the failure reason indicates uncertainty

## Recommended output file

```text
outputs/oda_conversion_contract/ODA_CONVERSION_CONTRACT.json
```
