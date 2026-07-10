from __future__ import annotations

import os
import sys
from pathlib import Path


def application_root() -> Path:
    """Return the source checkout root or PyInstaller extraction root."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[2]


def resolve_resource(path: str | Path) -> Path:
    """Resolve user-supplied paths first, then bundled read-only resources."""
    candidate = Path(path).expanduser()
    if candidate.is_absolute() or candidate.exists():
        return candidate
    bundled = application_root() / candidate
    return bundled if bundled.exists() else candidate


def user_data_dir(*parts: str) -> Path:
    """Return a persistent writable HS-CAD folder on every supported platform."""
    if os.name == "nt":
        root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = root / "HS-CAD"
    for part in parts:
        path /= part
    path.mkdir(parents=True, exist_ok=True)
    return path
