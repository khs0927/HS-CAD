from __future__ import annotations

from pathlib import Path
from typing import Any

from src.adapters.lisp_adapter import LispAdapter
from src.integrations.xicad_paths import detect_xicad_profile, XiCADPathProfile


def _log_success(message: str) -> None:
    try:
        from rich.console import Console

        Console().print(f"[green]{message}[/green]")
    except Exception:
        print(message)


def _log_warn(message: str) -> None:
    try:
        from rich.console import Console

        Console().print(f"[yellow]{message}[/yellow]")
    except Exception:
        print(message)


class XiCADAdapter:
    """Safe bridge between ZWCAD AI Modifier and an existing XiCAD package.

    XiCAD is a compiled architectural CAD add-on. This adapter does not reverse
    engineer XiCAD internals. It only performs safe integration tasks:

    - detect XiCAD folders and important files,
    - append XiCAD support paths to the ZWCAD support path environment,
    - load XiCAD bootstrap candidates such as xi.zelx / xi.fas / zwcad.lsp,
    - queue known XiCAD aliases such as WAL, COL, D1, W1 and PK,
    - produce dry-run plans for AI workflows.

    Most XiCAD commands are interactive. The correct automation pattern is:
    AI Modifier prepares layers/objects -> XiCAD command is queued -> user or
    scripted command input finishes the XiCAD workflow -> AI Modifier rescans
    and verifies the resulting DWG.
    """

    def __init__(self, com_adapter: Any, xicad_root: str | Path):
        self.com_adapter = com_adapter
        self.root = Path(xicad_root).expanduser().resolve()
        self.profile: XiCADPathProfile = detect_xicad_profile(self.root)
        self.lisp = LispAdapter(com_adapter)

    def exists(self) -> bool:
        return self.root.exists() and bool(self.profile.support_paths)

    def support_paths(self) -> list[Path]:
        return [Path(path) for path in self.profile.support_paths]

    def loader_candidates(self) -> list[Path]:
        return [Path(path) for path in self.profile.loader_candidates]

    def menu_candidates(self) -> list[Path]:
        return [Path(path) for path in self.profile.menu_candidates]

    def zrx_candidates(self) -> list[Path]:
        return [Path(path) for path in self.profile.zrx_candidates]

    def _send_lisp_expr(self, expr: str) -> None:
        self.lisp.send_command(expr)

    @staticmethod
    def _lisp_path(path: str | Path) -> str:
        return str(path).replace('\\', '/').replace('"', '\\"')

    def add_support_paths(self) -> None:
        for path in self.support_paths():
            normalized = self._lisp_path(path)
            expr = (
                '(progn '
                f'(setq xi_path "{normalized}") '
                '(if (not (vl-string-search (strcase xi_path) (strcase (getenv "ACAD")))) '
                '(setenv "ACAD" (strcat (getenv "ACAD") ";" xi_path))) '
                '(princ))'
            )
            self._send_lisp_expr(expr)
        _log_success(f"XiCAD support paths queued: {len(self.support_paths())}")

    def load(self) -> Path | None:
        if not self.exists():
            _log_warn(f"XiCAD root not found or incomplete: {self.root}")
            return None
        self.add_support_paths()
        for candidate in self.loader_candidates():
            if candidate.exists():
                self.lisp.load_lisp(candidate)
                _log_success(f"XiCAD loader queued: {candidate}")
                return candidate
        _log_warn("No XiCAD loader found. Check xi.zelx / xi.fas / _ZWCad/zwcad.lsp")
        return None

    def load_menu_hint(self) -> list[str]:
        """Return CUIX/MENUC commands that can be manually loaded in ZWCAD.

        ZWCAD menu loading may differ by version/profile, so we expose these as
        explicit hints rather than blindly mutating the user profile.
        """
        return [f'MENULOAD {self._lisp_path(path)}' for path in self.menu_candidates()]

    def load_zrx_hints(self) -> list[str]:
        return [f'APPLOAD {self._lisp_path(path)}' for path in self.zrx_candidates()]

    def run_alias(self, alias: str, *, escape_first: bool = True) -> None:
        clean = alias.strip()
        if not clean:
            raise ValueError("XiCAD alias is empty")
        prefix = "\x1b\x1b" if escape_first else ""
        self.lisp.send_command(f"{prefix}{clean}")

    def run_scripted_alias(self, alias: str, args: list[str] | None = None) -> None:
        clean = alias.strip()
        if not clean:
            raise ValueError("XiCAD alias is empty")
        tokens = [clean] + [str(arg) for arg in (args or [])]
        self.lisp.send_command(" ".join(tokens))

    def dry_run_plan(self, alias: str, *, args: list[str] | None = None, load_first: bool = False) -> dict[str, Any]:
        return {
            'action': 'xicad_command',
            'alias': alias,
            'args': args or [],
            'load_first': load_first,
            'xicad_root': str(self.root),
            'support_paths': self.profile.support_paths,
            'loader_candidates': self.profile.loader_candidates,
            'interactive': not bool(args),
            'menu_hints': self.load_menu_hint(),
            'zrx_hints': self.load_zrx_hints(),
        }
