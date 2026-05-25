# Live Runner Policy and ODA Contract Review

## 1. PR69 Hold Rationale

**PR69 (feat: implement FinalLiveRunner and register ZWCAD live runner CLIs)** remains open but is strictly on hold.
- **Reason**: The PR has unresolved conflicts and failing checks. More importantly, live CAD execution poses significant mutation risks to origin files.
- **Action**: PR69 must not be merged directly. It will serve solely as a reference point for future runner integrations.

## 2. ODA / Live-Runner Boundary

The live runner must not interface directly with ODA internals. ODA conversion is an upstream extraction step. The live runner must only consume neutral output contracts emitted by the ODA layer or preflight steps.

### Proposed ODA Neutral Contract

**Input:**
- `original_dwg_path`: Absolute path to the original DWG (read-only).
- `working_copy_path`: Path for a temporary working copy (must not overwrite original).
- `output_workspace`: Directory for generated artifacts.
- `requested_target_dxf_version`: e.g., 'ACAD2018'.

**Output:**
- `status`: success | failure
- `converted_dxf_path`: Path to the successful DXF output.
- `log_path`: Path to conversion diagnostics.
- `converter_used`: 'ODA_File_Converter'
- `original_mutated`: false (Asserted guarantee).
- `warnings`: Array of non-fatal issues.
- `failure_reason`: Error description if status == failure.

## 3. Execution Candidate Planner Contract

Before any live runner can execute commands, an Execution Candidate Planner must generate a safe sequence plan for human operator review. 

**Input:**
- `preflight_decision_json`: Preflight guard output.
- `manual_copy_only_interface_json`: Copy-only state.
- `oda_conversion_contract_json`: Output from ODA conversion.
- `operator_approval_state`: Boolean indicating explicit human review.

**Output:**
- `execution_candidate_allowed`: **false** (by default).
- `sendcommand_allowed`: **false**.
- `saveas_allowed`: **false**.
- `original_dwg_mutation_allowed`: **false**.
- `candidate_steps`: Array of planned, human-readable steps.
- `rollback_audit_requirements`: Actions needed to revert if execution fails.

## 4. Required Preconditions Before Implementation

1. **Strict Operator Approval**: No automated scripts can flip the `execution_candidate_allowed` flag without human intervention logs.
2. **Immutable Originals**: The core orchestrator must enforce read-only locks on the original DWG paths prior to triggering the planner.
3. **ODA Separation**: ODA conversion must complete and yield a valid contract JSON *before* the planner evaluates CAD feasibility.

## 5. Next Steps

- **Exact Next PR Title**: `docs: add live runner execution candidate planner contracts`
- **Scope**: Documentation-only. Establishes the planner JSON schemas and contract boundaries.
- **Files That Must Not Be Touched**: 
  - `src/main.py`
  - `config/worker_manifest.json`
  - `src/adapters/zwcad_com_adapter.py`
  - Any core CAD runner logic or legacy PR69 files.
