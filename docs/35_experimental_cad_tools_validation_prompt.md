# Validation prompt for experimental CAD tools

Copy this prompt into the verification agent after fetching `exp/isolated-tools-development`.

```text
You are validating the HS-CAD experimental CAD tools branch.

Repository: khs0927/HS-CAD
Branch: exp/isolated-tools-development

Goal:
Validate the experimental isolated-tool development without modifying main. This branch is intentionally separate from production/hotfix work.

Important context:
- Original DWG files must not be mutated during analysis.
- COM ModelSpace full scan must not be treated as the default path for object-heavy drawings.
- Preferred direction is fast read-only evidence first, then targeted COM/PyRx/XiCAD only when needed.
- PyRx and pyzwcad are metadata/experimental only unless a verified local runtime exists.
- ezdxf is a read-only offline DXF fallback.

Tasks:
1. Fetch and checkout the branch.
   - git fetch origin exp/isolated-tools-development
   - git switch exp/isolated-tools-development

2. Run targeted tests.
   - python -X utf8 -m pytest -q tests/test_experimental_cad_tools.py

3. Run full tests.
   - python -X utf8 -m pytest -q

4. Check CLI registration.
   - python -X utf8 -m src.main --help
   - Confirm these commands are present:
     - experimental-cad-backends
     - experimental-cad-scan-strategy
     - experimental-cad-evidence-synthetic

5. Run synthetic CLI smoke tests.
   - python -X utf8 -m src.main experimental-cad-backends
   - python -X utf8 -m src.main experimental-cad-backends --query dxf
   - python -X utf8 -m src.main experimental-cad-scan-strategy "large object drawing analysis" --has-dxf --object-count-hint 60000
   - python -X utf8 -m src.main experimental-cad-evidence-synthetic --out-dir outputs/experimental_cad_synthetic_verify

6. Verify generated artifacts.
   - outputs/experimental_cad_synthetic_verify/EXPERIMENTAL_CAD_EVIDENCE_SYNTHETIC.json
   - outputs/experimental_cad_synthetic_verify/EXPERIMENTAL_CAD_EVIDENCE_SYNTHETIC.md
   - Confirm JSON contains object_count, object_type_counts, layer_counts, boundary_summary, dimension_summary.
   - Confirm Markdown report opens and includes boundary and dimension sections.

7. Optional DXF smoke test only if a safe sample DXF exists.
   - Do not use production DWG directly.
   - Use a copied/exported/sample DXF only.
   - Import and call src.workers.experimental_cad_evidence_worker.run_ezdxf_evidence_worker(sample_dxf, out_dir)
   - Confirm it writes JSON and Markdown outputs.

8. Inspect these files for code review:
   - src/adapters/backend_registry.py
   - src/adapters/ezdxf_adapter.py
   - src/scanners/boundary_scanner.py
   - src/scanners/dimension_scanner.py
   - src/scanners/object_scanner.py
   - src/reports/evidence_report.py
   - src/workflows/scan_strategy.py
   - src/app/experimental_cad_cli.py
   - src/workers/experimental_cad_evidence_worker.py
   - tests/test_experimental_cad_tools.py

9. Report results in this format:
   - Branch/commit tested
   - Targeted test result
   - Full test result
   - CLI help result
   - Synthetic CLI result
   - Artifact existence/result
   - Any failures with exact traceback
   - Whether PR #24 is safe to keep open, needs patch, or can be merged after review

Do not merge the PR. Do not push to main. If a patch is needed, commit only to exp/isolated-tools-development or provide a patch summary for the maintainer.
```
