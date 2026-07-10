from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_matches_project_metadata() -> None:
    release_version = (ROOT / "release" / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_version = pyproject["project"]["version"]

    assert re.fullmatch(r"\d+\.\d+\.\d+", release_version)
    assert release_version == project_version
