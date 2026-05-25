# CI and Security Guardrail Plan

## Introduction

As HS-CAD evolves, it is critical to implement strong CI/CD and security guardrails to ensure repository stability. This plan outlines the necessary safeguards to protect against artifact pollution, unintended high-risk modifications, and failing dependencies, all while avoiding the need for heavy CAD software installations on GitHub runners.

## Staged CI Plan

### 1. Minimal Python CI

A lightweight GitHub Actions workflow to validate code health on standard Ubuntu runners without CAD dependencies:
- **Dependency Installation**: `pip install -r requirements.txt`
- **Syntax Check**: `python -m compileall -q src tests`
- **Targeted Testing**: Run safe, backend-independent tests (`python -m pytest -q tests/test_corpus_foundation.py` etc.).
- **CLI Health Check**: Run `python -m src.main --help` to ensure the main entrypoint and CLI registration remain intact.

### 2. Artifact Guard

To prevent repository bloat and accidental data leaks, a strict block list will be enforced via CI:
- **Fail the PR if the following patterns are committed (unless explicitly allowed)**:
  - `outputs/**` (Runtime reports, combined JSONs)
  - `artifacts/**/*.zip` (Large generated megapacks)
  - `*.dwg`, `*.dxf` (Raw CAD files)
  - `*.sqlite`, `*.sqlite3` (Local knowledge bases)
  - `__pycache__/**`, `.pytest_cache/**`

### 3. High-Risk File Guard

Direct edits to the following core orchestrator and live-runner files present severe stability risks and will trigger a warning or failure, mandating strict human review:
- `src/main.py`
- `config/worker_manifest.json`
- `src/adapters/zwcad_com_adapter.py`
- `src/converters/oda_file_converter.py`
- `.github/workflows/*.yml`

### 4. Repo Inventory Check

- Ensure that any new modules, structural changes, or extraction bundles (like those from PR82) are fully documented before being merged into `main`.

### 5. Security Plan

Standard security workflows will be enabled for the repository:
- **CodeQL / Python Security Scan**: Automated vulnerability scanning on PRs.
- **Dependency Review**: Dependabot or GitHub native tools to catch known vulnerable libraries in `requirements.txt`.
- **Secret Scanning**: Ensuring no CAD license keys, API tokens, or server paths are hardcoded.

## Constraints

- **No Live CAD on GitHub Actions**: This plan deliberately avoids adding workflows that require ZWCAD, AutoCAD, PyRx, or ODA installations on GitHub-hosted Linux runners.
- **No Mutations**: No commands that perform DWG mutation (e.g., `SendCommand`, `SaveAs`, `DXFOUT`) will be automated in the remote CI at this stage.

## Next Steps

After reviewing and approving this plan, we will systematically translate these rules into actual `.github/workflows/` implementations in subsequent, isolated pull requests.
