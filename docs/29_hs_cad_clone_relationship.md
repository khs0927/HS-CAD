# HS-CAD Clone Relationship

`C:\cad\HS-CAD-clone` is not a Git submodule of this repository. It is a separate sibling clone that points at the same GitHub repository.

The local relationship found during integration was:

- Active PR workspace: `C:\cad\zwcad-ai-modifier`
- Sibling clone: `C:\cad\HS-CAD-clone`
- Shared remote: `https://github.com/khs0927/HS-CAD.git`
- No `.gitmodules` entry exists in the active PR workspace.

Because it is not a submodule, the clone should not be committed as a nested project or copied wholesale. Useful work from the sibling clone should be ported file-by-file into the active branch and tested.

## Ported Subparts

The useful missing subpart from `HS-CAD-clone` was the ArchiOffice rule-engine line of work. It has been ported as source code and tests:

- `src/integrations/archioffice_rule_engine.py`
- `tests/test_archioffice_rule_engine.py`
- `tests/verify_archioffice_integrity.py`
- rules-based helper functions in `src/modifiers/architectural_modifier.py`
- `tests/test_architectural_modifier_rule_actions.py`

The port keeps ArchiOffice parsing isolated from XiCAD parsing. It does not decode protected Lisp assets, does not write into `C:\Program Files\ArchiOfficeZW2024`, and does not modify DWG files.

## Not Ported Wholesale

The sibling clone also contained commits that deleted legacy tests and older/generated working files. Those changes were not imported because this PR already has a passing test suite and runtime artifacts are intentionally excluded from the repository.

