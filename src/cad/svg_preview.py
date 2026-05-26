from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

import ezdxf


def write_svg_preview(dxf_path: str | Path, svg_path: str | Path) -> Path:
    out = Path(svg_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        from ezdxf.addons.drawing import Frontend, RenderContext
        from ezdxf.addons.drawing.svg import SVGBackend

        doc = ezdxf.readfile(str(dxf_path))
        msp = doc.modelspace()
        backend = SVGBackend()
        Frontend(RenderContext(doc), backend).draw_layout(msp)
        out.write_text(backend.get_string(), encoding="utf-8")
        return out
    except Exception as exc:
        fallback = _fallback_svg({"error": str(exc), "source": str(dxf_path)})
        out.write_text(fallback, encoding="utf-8")
        return out


def _fallback_svg(info: dict[str, Any]) -> str:
    text = escape(f"HS-CAD preview fallback: {info}")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800">'
        '<rect width="100%" height="100%" fill="white" stroke="black"/>'
        f'<text x="40" y="80" font-size="24" fill="black">{text}</text>'
        '</svg>'
    )
