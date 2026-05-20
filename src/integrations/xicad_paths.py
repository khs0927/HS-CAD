from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class XiCADPathProfile:
    root: str
    zwcad_dir: str | None
    lisp_dir: str | None
    lib_dir: str | None
    xilib_dir: str | None
    dialogbox_dir: str | None
    loader_candidates: list[str]
    support_paths: list[str]
    menu_candidates: list[str]
    zrx_candidates: list[str]
    shortkey_file: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _as_str(path: Path | None) -> str | None:
    return str(path) if path else None


def detect_xicad_profile(root: str | Path) -> XiCADPathProfile:
    """Detect a XiCAD installation/extracted package layout.

    This does not execute XiCAD or inspect compiled .fas/.zelx code. It only
    maps important files so the ZWCAD bridge can add support paths and queue
    loader/menu commands safely.
    """
    root_path = Path(root).expanduser().resolve()
    zwcad_dir = root_path / "_ZWCad"
    lisp_dir = root_path / "Lisp"
    lib_dir = root_path / "Lib"
    xilib_dir = root_path / "xiLib"
    dialogbox_dir = root_path / "DialogBox"

    loader_candidates = [
        lisp_dir / "xi.zelx",
        lisp_dir / "xi.fas",
        zwcad_dir / "zwcad.lsp",
    ]
    menu_candidates = [
        zwcad_dir / "xicad_ZWCAD.cuix",
        zwcad_dir / "xicad_ZWCAD.menuc",
    ]
    zrx_candidates = [
        zwcad_dir / "ToolBox.zrx",
        zwcad_dir / "ExportLayout_64.zrx",
        zwcad_dir / "ExportLayout_32.zrx",
    ]
    support_candidates = [lisp_dir, lib_dir, xilib_dir, dialogbox_dir, zwcad_dir]
    shortkey = lisp_dir / "xiShortkey_origin.key"

    return XiCADPathProfile(
        root=str(root_path),
        zwcad_dir=_as_str(zwcad_dir) if zwcad_dir.exists() else None,
        lisp_dir=_as_str(lisp_dir) if lisp_dir.exists() else None,
        lib_dir=_as_str(lib_dir) if lib_dir.exists() else None,
        xilib_dir=_as_str(xilib_dir) if xilib_dir.exists() else None,
        dialogbox_dir=_as_str(dialogbox_dir) if dialogbox_dir.exists() else None,
        loader_candidates=[str(p) for p in loader_candidates if p.exists()],
        support_paths=[str(p) for p in support_candidates if p.exists()],
        menu_candidates=[str(p) for p in menu_candidates if p.exists()],
        zrx_candidates=[str(p) for p in zrx_candidates if p.exists()],
        shortkey_file=str(shortkey) if shortkey.exists() else None,
    )
