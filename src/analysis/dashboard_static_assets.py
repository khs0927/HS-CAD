from __future__ import annotations

from pathlib import Path
from typing import Any

from src.analysis.entity_loader import write_json_and_md


DASHBOARD_CSS = """
:root { --bg:#f6f7f9; --card:#fff; --text:#1d2433; --muted:#687385; --ok:#2e7d32; --warn:#f9a825; --bad:#c62828; --line:#e6e8ee; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",sans-serif; background:var(--bg); color:var(--text); }
.container { max-width:1180px; margin:0 auto; padding:24px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:18px; margin:14px 0; box-shadow:0 3px 16px rgba(20,30,50,.05); }
.badge { display:inline-block; border-radius:999px; padding:4px 10px; font-size:12px; }
.badge.ok { background:#e8f5e9; color:var(--ok); }
.badge.warn { background:#fff8e1; color:#8a6400; }
.badge.bad { background:#ffebee; color:var(--bad); }
table { border-collapse:collapse; width:100%; background:white; }
th,td { border-bottom:1px solid var(--line); padding:9px 10px; text-align:left; }
th { color:var(--muted); font-size:13px; }
pre { white-space:pre-wrap; background:#f1f3f7; border-radius:10px; padding:12px; }
"""


DASHBOARD_JS = """
function filterCards(query) {
  const q = query.toLowerCase();
  document.querySelectorAll('[data-filter-card]').forEach(card => {
    const text = card.innerText.toLowerCase();
    card.style.display = text.includes(q) ? '' : 'none';
  });
}
"""


def write_dashboard_static_assets(workspace: str | Path) -> dict[str, Any]:
    base = Path(workspace)
    assets = base / "dashboard_assets"
    assets.mkdir(parents=True, exist_ok=True)
    css_path = assets / "hscad_dashboard.css"
    js_path = assets / "hscad_dashboard.js"
    css_path.write_text(DASHBOARD_CSS.strip() + "\n", encoding="utf-8")
    js_path.write_text(DASHBOARD_JS.strip() + "\n", encoding="utf-8")

    payload = {
        "backend": "dashboard_static_assets",
        "schema_version": "0.1",
        "summary": {"asset_count": 2, "css_path": str(css_path), "js_path": str(js_path)},
        "artifacts": [str(css_path), str(js_path)],
        "todo": [
            "Link these assets from html_validation_dashboard.",
            "Add collapsible artifact detail cards.",
            "Add client-side graph filtering.",
            "Add SVG mini charts after metrics stabilize.",
        ],
        "warnings": ["Assets generated but not yet linked by existing dashboard generator."],
    }
    return write_json_and_md(base, "DASHBOARD_STATIC_ASSETS", payload, _markdown(payload))


def _markdown(payload: dict[str, Any]) -> str:
    s = payload.get("summary") or {}
    return "\n".join([
        "# Dashboard Static Assets",
        "",
        f"- Asset count: `{s.get('asset_count')}`",
        f"- CSS: `{s.get('css_path')}`",
        f"- JS: `{s.get('js_path')}`",
        "",
    ])
