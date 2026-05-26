# HS-CAD Worker and CLI Validation Harness

## Overview
This validation harness is designed to guarantee the architectural stability of `HS-CAD` by ensuring that:
1. No registered worker manifest entry can fail to import or be missing its execution entry point (`run_worker`).
2. No CLI command group can expose active CAD execution pathways, win32com/pyautocad mutations, or other prohibited operations in its help context.
3. No high-risk runtime artifacts are committed to the repository, and the codebase remains 100% clean and compile-ready.

---

## Architecture Policy
- **Live CAD Execution:** STRICTLY PROHIBITED. All runners, adaptors, and execution blocks must remain holding.
- **DWG Mutation:** Absolutely forbidden.
- **PR Rules:** High-risk files (`config/worker_manifest.json`, `src/main.py`) must never be modified concurrently with live runner features. 

---

## Local Execution Guide

To perform complete local verification of the worker manifest and CLI contracts, execute the following validator scripts:

### 1. Worker Manifest Candidate Scan
This script reads `config/worker_manifest.json`, dynamically imports each module, validates the callable, and scans the source code for unauthorized live CAD keywords.

```powershell
# Run validation (warn-only mode for current missing megapacks)
python scripts/validate_worker_manifest_candidates.py

# Run validation in strict mode (fails with exit code 1 on any failure)
python scripts/validate_worker_manifest_candidates.py --strict
```

### 2. CLI Command Contracts Scan
This script discovers all registered CLI command groups in `src/main.py` and recursively calls `<command> --help` to ensure exit-code stability and scan for prohibited live execution keywords.

```powershell
# Run CLI validation
python scripts/validate_cli_command_contracts.py

# Run CLI validation in strict mode
python scripts/validate_cli_command_contracts.py --strict
```

---

## Continuous Integration (CI) Integration

These tests are fully integrated into `pytest` and can be run under any standard runner:

```powershell
# Run the candidate validation tests specifically
pytest tests/test_worker_manifest_imports.py tests/test_cli_help_contracts.py -v

# Run the entire test suite to ensure no regressions
pytest
```

---

## Verification Metrics
The validator scripts save detailed output logs inside `outputs/` for review:
- `outputs/worker_manifest_validation_report.json`
- `outputs/cli_command_contracts_report.json`
