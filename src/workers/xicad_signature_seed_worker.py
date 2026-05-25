from __future__ import annotations

from pathlib import Path
from typing import Any

from src.execution.xicad_signature_seed import build_signature_seeds_from_rules
from src.integrations.xicad_rule_engine import XiCADRuleEngine
from src.reports.json_exporter import export_json


def render_signature_seeds_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# HS-CAD XiCAD Signature Seeds",
        "",
        f"- Source: `{payload.get('source')}`",
        f"- Loaded: `{payload.get('loaded')}`",
        f"- Seed count: `{payload.get('seed_count')}`",
        "",
        "## Seeds",
        "",
    ]
    for seed in payload.get("seeds") or []:
        lines.append(
            f"- `{seed.get('alias')}` | {seed.get('status')} | review={seed.get('requires_human_review')}"
        )
    lines += [
        "",
        "## Safety",
        "",
        "- This worker reads XiCAD text/config assets only.",
        "- This worker does not inspect protected binary internals.",
        "- This worker does not open ZWCAD.",
        "- Seeds are not promoted to config automatically.",
        "",
    ]
    return "\n".join(lines)


def run_xicad_signature_seed_worker(
    *,
    xicad_root: str = "C:/xicad",
    out_dir: str | Path = "outputs/xicad_signature_seeds",
) -> dict[str, Any]:
    engine = XiCADRuleEngine(xicad_root)
    loaded = engine.load_all_rules()
    rules = {
        "wall_styles": engine.wall_styles,
        "block_layer_rules": engine.block_layer_rules,
        "config_variables": engine.configs,
        "shortkeys": engine.shortkeys,
        "pgp_aliases": engine.pgp_aliases,
        "structural_steel_specs": engine.structural_steel_specs,
        "block_catalog": engine.block_catalog,
    }
    seeds = build_signature_seeds_from_rules(rules, source=xicad_root)

    payload = {
        "source": xicad_root,
        "loaded": loaded,
        "seed_count": len(seeds),
        "seeds": [seed.to_dict() for seed in seeds],
        "safety": {
            "cad_mutation": False,
            "send_command": False,
            "binary_reverse_engineering": False,
            "auto_promote_to_config": False,
        },
    }

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seeds_json = out / "XICAD_SIGNATURE_SEEDS.json"
    report_md = out / "XICAD_SIGNATURE_SEEDS.md"
    export_json(payload, seeds_json)
    report_md.write_text(render_signature_seeds_markdown(payload), encoding="utf-8")

    return {
        "out_dir": str(out),
        "seeds_json": str(seeds_json),
        "report": str(report_md),
        "loaded": loaded,
        "seed_count": len(seeds),
        "aliases": [seed.alias for seed in seeds],
    }
