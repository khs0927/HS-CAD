from __future__ import annotations

import argparse
from pathlib import Path

from src.integrations.xicad_paths import detect_xicad_profile


def lisp_quote(path: str) -> str:
    return path.replace('\\', '/').replace('"', '\\"')


def build_bootstrap_lisp(xicad_root: str | Path) -> str:
    profile = detect_xicad_profile(xicad_root)
    lines: list[str] = []
    lines.append('; Auto-generated XiCAD bootstrap for ZWCAD AI Modifier')
    lines.append('; Load this file in ZWCAD with APPLOAD or (load "path/to/zwai_xicad_bootstrap.lsp")')
    lines.append('(vl-load-com)')
    lines.append('(defun zwai-add-support-path (p / old upper-old upper-p)')
    lines.append('  (setq old (getenv "ACAD"))')
    lines.append('  (setq upper-old (strcase old))')
    lines.append('  (setq upper-p (strcase p))')
    lines.append('  (if (not (vl-string-search upper-p upper-old))')
    lines.append('    (setenv "ACAD" (strcat old ";" p))')
    lines.append('  )')
    lines.append(')')
    for path in profile.support_paths:
        lines.append(f'(zwai-add-support-path "{lisp_quote(path)}")')
    if profile.loader_candidates:
        loader = lisp_quote(profile.loader_candidates[0])
        lines.append(f'(if (findfile "{loader}") (load "{loader}"))')
    for zrx in profile.zrx_candidates:
        lines.append(f'; Optional ZRX: {lisp_quote(zrx)}')
    if profile.menu_candidates:
        lines.append(f'; Optional CUIX menu file: {lisp_quote(profile.menu_candidates[0])}')
    lines.append('(princ "\\n[ZWAi] XiCAD support paths and loader queued. ")')
    lines.append('(princ)')
    return '\n'.join(lines) + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description='Create a ZWCAD LISP bootstrap file for XiCAD.')
    parser.add_argument('--xicad-root', required=True)
    parser.add_argument('--out', default='generated/xicad/zwai_xicad_bootstrap.lsp')
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_bootstrap_lisp(args.xicad_root), encoding='utf-8')
    print(f'Bootstrap LISP generated: {out}')


if __name__ == '__main__':
    main()
