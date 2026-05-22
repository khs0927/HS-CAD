from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from src.app.cli import app
from src.app.logger import console, success
from src.orchestrator.xicad_context_provider import build_xicad_prompt_context, find_xicad_candidates
from src.orchestrator.xicad_recipe_registry import get_xicad_recipe, is_scriptable_xicad_command, recipe_summary
from src.orchestrator.xicad_safety_policy import decide_xicad_safety
from src.orchestrator.xicad_stage2_bridge import build_stage2_readiness_report
from src.orchestrator.xicad_taxonomy import build_xicad_taxonomy, search_xicad_commands
from src.reports.json_exporter import export_json


def _infer_xicad_category(request: str) -> str | None:
    lowered = request.lower()
    if any(kw in lowered for kw in ["벽", "문", "창", "단열", "주차", "계단"]):
        return "DRAW_ARCH"
    if any(kw in lowered for kw in ["보", "기둥", "철골", "h빔"]):
        return "DRAW_STRUCT"
    if any(kw in lowered for kw in ["면적", "실별", "수량", "표"]):
        return "AREA_QTY"
    if any(kw in lowered for kw in ["레이어", "켜", "병합", "이름"]):
        return "LAYER_MANAGE"
    if any(kw in lowered for kw in ["문자", "치수", "텍스트"]):
        return "TEXT_DIM"
    return None


@app.command("xicad-taxonomy")
def xicad_taxonomy(
    xicad_root: str = typer.Option("C:/xicad", help="XiCAD root directory"),
    out: str = typer.Option("outputs/xicad_taxonomy.json", help="Output JSON path"),
):
    """Export the parsed XiCAD taxonomy to a JSON file."""
    taxonomy = build_xicad_taxonomy(xicad_root)
    export_json([cmd.__dict__ for cmd in taxonomy], out)
    success(f"XiCAD taxonomy written to {out}")


@app.command("xicad-search")
def xicad_search(
    query: str = typer.Argument(..., help="Free-text query for XiCAD commands"),
    category: str | None = typer.Option(None, "--category", help="Optional category filter"),
    limit: int = typer.Option(12, "--limit", help="Maximum number of results"),
    xicad_root: str = typer.Option("C:/xicad", "--xicad-root", help="XiCAD root directory"),
    out: str | None = typer.Option(None, "--out", help="Optional JSON output"),
):
    """Search the XiCAD taxonomy for matching commands."""
    matches = search_xicad_commands(query, category, limit, taxonomy=build_xicad_taxonomy(xicad_root))
    if out:
        export_json([match.__dict__ for match in matches], out)
        success(f"XiCAD search results written to {out}")
        return

    table = Table("Alias", "Function", "Description", "Category", "Risk")
    for match in matches:
        table.add_row(match.alias, match.function, match.description, match.category, match.risk)
    console.print(table)


@app.command("xicad-context")
def xicad_context(
    query: str = typer.Argument(..., help="Query describing the desired drawing operation"),
    category: str | None = typer.Option(None, "--category"),
    limit: int = typer.Option(12, "--limit"),
):
    """Print the safe XiCAD context block used for VLM prompts."""
    console.print(build_xicad_prompt_context(query, category=category, limit=limit))


@app.command("hscad-tool-plan")
def hscad_tool_plan(
    request: str = typer.Argument(..., help="Natural language request describing the drawing task"),
    xicad_root: str = typer.Option("C:/xicad", "--xicad-root", help="XiCAD root directory"),
    out: str = typer.Option("outputs/hscad_plan.json", "--out", help="Output JSON plan file"),
):
    """Generate a review-only HS-CAD/XiCAD command plan."""
    category = _infer_xicad_category(request)
    taxonomy = build_xicad_taxonomy(xicad_root)
    matches = search_xicad_commands(request, category=category, limit=12, taxonomy=taxonomy)
    candidates = []
    for match in matches:
        row = dict(match.__dict__)
        recipe = get_xicad_recipe(match.alias)
        decision = decide_xicad_safety(
            match.alias,
            match.function,
            match.description,
            recipe_verified=bool(recipe and recipe.verified),
            recipe_scriptable=bool(recipe and recipe.scriptable),
        )
        row["risk"] = decision.risk
        row["scriptable"] = is_scriptable_xicad_command(match.alias)
        row["auto_run_allowed"] = decision.auto_run_allowed
        row["execution_mode"] = "scriptable" if decision.auto_run_allowed else "review-only"
        row["safety_reasons"] = list(decision.reasons)
        row["recipe"] = recipe.to_dict() if recipe else None
        candidates.append(row)

    plan = {
        "request": request,
        "detected_category": category,
        "xicad_root": xicad_root,
        "taxonomy_count": len(taxonomy),
        "candidates": candidates,
        "risk_summary": {risk: sum(1 for row in candidates if row["risk"] == risk) for risk in {row["risk"] for row in candidates}},
    }
    export_json(plan, out)
    success(f"HS-CAD XiCAD plan written to {out}")


@app.command("xicad-stage2-readiness")
def xicad_stage2_readiness(
    repo_root: Path = typer.Option(Path("."), "--repo-root"),
    out: Path | None = typer.Option(None, "--out"),
):
    """Check whether the XiCAD deep orchestrator is ready for stage 2."""
    report = build_stage2_readiness_report(repo_root)
    table = Table("Key", "Value")
    table.add_row("status", str(report["status"]))
    table.add_row("candidate_count", str(report["candidate_count"]))
    table.add_row("auto_scriptable_count", str(report["auto_scriptable_count"]))
    table.add_row("neuro_seq_cad_exists", str(report["neuro_seq_cad"]["exists"]))
    console.print(table)
    if out:
        export_json(report, out)
        success(f"XiCAD stage2 readiness report written: {out}")


@app.command("xicad-safe-context")
def xicad_safe_context(
    query: str = typer.Argument(...),
    category: str | None = typer.Option(None, "--category"),
    limit: int = typer.Option(12, "--limit"),
    out: Path | None = typer.Option(None, "--out"),
):
    """Build a small, safe XiCAD prompt context block."""
    context = build_xicad_prompt_context(query, category=category, limit=limit)
    console.print(context)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(context, encoding="utf-8")
        success(f"XiCAD safe context written: {out}")


@app.command("xicad-recipe-summary")
def xicad_recipe_summary(out: Path | None = typer.Option(None, "--out")):
    """Show scriptable/review-only XiCAD recipe policy."""
    payload = recipe_summary()
    table = Table("Alias", "Function", "Verified", "Scriptable", "AutoRun")
    for row in payload["recipes"]:
        table.add_row(row["alias"], row["function"], str(row["verified"]), str(row["scriptable"]), str(row["auto_run_allowed"]))
    console.print(table)
    if out:
        export_json(payload, out)
        success(f"XiCAD recipe summary written: {out}")


@app.command("xicad-safe-search")
def xicad_safe_search(
    query: str = typer.Argument(...),
    category: str | None = typer.Option(None, "--category"),
    limit: int = typer.Option(12, "--limit"),
    out: Path | None = typer.Option(None, "--out"),
):
    """Search XiCAD candidates and apply stage-2 safety policy."""
    rows = find_xicad_candidates(query, category=category, limit=limit)
    table = Table("Alias", "Function", "Category", "Risk", "AutoRun")
    for row in rows:
        table.add_row(row["alias"], row.get("function", ""), row.get("category", ""), row.get("risk", ""), str(row.get("auto_run_allowed", False)))
    console.print(table)
    if out:
        export_json({"query": query, "category": category, "results": rows}, out)
        success(f"XiCAD safe search written: {out}")
