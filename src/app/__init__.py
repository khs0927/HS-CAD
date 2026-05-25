"""HS-CAD app package.

The package deliberately avoids eager imports of CLI modules to prevent circular import
issues (e.g., `src.adapters.zwcad_com_adapter` importing `src.app`). CLI commands are
registered explicitly in `src/main.py` where needed.
"""
