from __future__ import annotations

from src.app.cli import app

# Import side-effect registrations for optional orchestration commands.
# This keeps the original Typer app intact while making hscad-tools and
# hscad-tool-plan available from `python -m src.main`.
import src.app.orchestrated_cli  # noqa: F401,E402

if __name__ == '__main__':
    app()
