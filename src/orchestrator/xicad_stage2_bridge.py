from __future__ import annotations

from pathlib import Path
from typing import Any

from .xicad_context_provider import find_xicad_candidates
from .xicad_recipe_registry import recipe_summary


def detect_neuro_seq_package(repo_root: str | Path = ".") -> dict[str, Any]:
    root = Path(repo_root)
    candidates = [
        root / "neuro_seq_cad",
        root / "src" / "neuro_seq_cad",
    ]
    existing = [str(path) for path in candidates if path.exists()]
    return {
        "exists": bool(existing),
        "paths": existing,
        "preferred_path": existing[0] if existing else str(candidates[0]),
    }


def build_stage2_readiness_report(repo_root: str | Path = ".", query: str = "벽체 단열 문 창") -> dict[str, Any]:
    root = Path(repo_root)
    neuro = detect_neuro_seq_package(root)
    candidates = find_xicad_candidates(query, category="DRAW_ARCH", limit=12)
    recipes = recipe_summary()
    return {
        "status": "PASS" if candidates else "WARNING",
        "repo_root": str(root.resolve()),
        "neuro_seq_cad": neuro,
        "candidate_count": len(candidates),
        "sample_candidates": candidates,
        "recipe_policy": recipes["policy"],
        "auto_scriptable_count": recipes["auto_scriptable_count"],
        "recommendations": [
            "Keep DXFBuilder as the canonical output.",
            "Generate xicad_command_plan.json before any script candidate.",
            "Do not mark XiCAD commands scriptable until verified in ZWCAD.",
            "Inject only limited XiCAD prompt context into VLM/LLM.",
        ],
    }
