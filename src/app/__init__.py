from __future__ import annotations

"""Application package namespace.

Keep this module intentionally side-effect free.

CLI command modules register Typer commands when they are imported by
``src.main``. Importing them here makes every ``src.app`` submodule import pull in
``src.app.cli`` and the CAD adapters, which can create circular imports during
pytest collection and in non-CAD environments.
"""
