# ZWCAD Plugin Skill

Use this skill for ZWCAD automation, plugins, COM automation, PyRx, and LISP integration.

Rules:
- Treat direct CAD write operations as high-risk.
- Use dry-run first.
- Keep commands reversible.
- Avoid hardcoded absolute paths.
- Support Windows paths carefully.
- Document ZWCAD version assumptions.
- Add logging.
- Add safety confirmation before modifying drawings.

Useful command style:
- python -m src.main --help
- python -m src.main scan --dwg "C:/cad/sample.dwg" --out "outputs/objects.json"
- python -m src.main layers --dwg "C:/cad/sample.dwg"
- python -m src.main blocks --dwg "C:/cad/sample.dwg"
- python -m src.main texts --dwg "C:/cad/sample.dwg"
