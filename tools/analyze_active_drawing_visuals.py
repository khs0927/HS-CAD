from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from src.integrations.xicad_rule_engine import XiCADRuleEngine
from src.integrations.archioffice_rule_engine import ArchiOfficeRuleEngine
from src.integrations.hssteel_rule_engine import HSSteelRuleEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
DEFAULT_OUT = PROJECT_ROOT / "outputs" / "active_drawing_visual_analysis"
INVENTORY_PATH = PROJECT_ROOT / "outputs" / "active_drawing_inventory" / "inventory.json"


@dataclass
class VisualCheckRule:
    key: str
    reason: str
    visual_signal: str
    code_output: str
    confidence: str = "needs_pdf_or_screenshot"


VISUAL_CHECK_RULES = [
    VisualCheckRule(
        "title_block_detection",
        "Object data can say A-FORM exists, but visual sheet extents and actual title block placement need page review.",
        "outer border, title block cluster, sheet number/name area",
        "sheet_regions[].title_block, sheet_regions[].border_bbox",
    ),
    VisualCheckRule(
        "zero_layer_visual_risk",
        "Layer 0 still has many objects; visual review helps decide if they are border, symbols, notes, or true leftovers.",
        "visible objects whose CAD layer is 0",
        "layer_remap_candidates['0']",
    ),
    VisualCheckRule(
        "lineweight_and_linetype_mismatch",
        "COM layer data records names, but plotted appearance reveals hidden/center/batting mistakes.",
        "continuous vs dashed vs center vs batting patterns",
        "visual_linetype_observations[]",
    ),
    VisualCheckRule(
        "text_readability_and_garbled_text",
        "CAD text strings may be encoded incorrectly or missing fonts; PDF shows whether the sheet is readable.",
        "broken Korean text, missing glyphs, overlapped notes",
        "text_quality_findings[]",
    ),
    VisualCheckRule(
        "xref_or_block_sheet_content",
        "Blocks and xrefs can hide repeated title/symbol content that is hard to classify from references alone.",
        "repeated title marks, imported block outlines, xref-like groups",
        "block_visual_roles[]",
    ),
    VisualCheckRule(
        "sheet_specific_remap_rules",
        "Some layer aliases only appear in particular sheets; PDF review can attach rules to sheet context.",
        "sheet-local labels and visible object categories",
        "sheet_rules[].layer_aliases",
    ),
]


def _json_default(value: Any) -> str:
    return str(value)


def _load_inventory(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "missing": str(path),
            "hint": "Run the active drawing inventory first before visual analysis.",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_get(obj: Any, attr: str, default: Any = None) -> Any:
    try:
        return getattr(obj, attr)
    except Exception:
        return default


def _connect_active_doc():
    from src.adapters.zwcad_com_adapter import ZWCADCOMAdapter

    adapter = ZWCADCOMAdapter(visible=True, start_if_needed=False)
    adapter.connect()
    return adapter, adapter.get_active_document()


def collect_layout_plot_targets() -> list[dict[str, Any]]:
    adapter, doc = _connect_active_doc()
    targets: list[dict[str, Any]] = []
    try:
        layouts = list(doc.Layouts)
    except Exception as exc:
        return [{"error": str(exc)}]
    for layout in layouts:
        name = str(_safe_get(layout, "Name", "") or "")
        if not name:
            continue
        targets.append(
            {
                "layout": name,
                "is_model": name.lower() == "model",
                "tab_order": _safe_get(layout, "TabOrder"),
                "config_name": _safe_get(layout, "ConfigName"),
                "canonical_media_name": _safe_get(layout, "CanonicalMediaName"),
                "plot_type": _safe_get(layout, "PlotType"),
                "standard_scale": _safe_get(layout, "StandardScale"),
                "use_standard_scale": _safe_get(layout, "UseStandardScale"),
                "center_plot": _safe_get(layout, "CenterPlot"),
                "plot_rotation": _safe_get(layout, "PlotRotation"),
                "style_sheet": _safe_get(layout, "StyleSheet"),
                "pdf_path": "",
            }
        )
    return targets


def try_export_layout_pdfs(out_dir: Path, include_model: bool = False) -> list[dict[str, Any]]:
    adapter, doc = _connect_active_doc()
    pdf_dir = out_dir / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    try:
        layouts = list(doc.Layouts)
    except Exception as exc:
        return [{"error": str(exc)}]
    original_layout = str(_safe_get(_safe_get(doc, "ActiveLayout"), "Name", "") or "")
    for layout in layouts:
        name = str(_safe_get(layout, "Name", "") or "")
        if not name or (name.lower() == "model" and not include_model):
            continue
        pdf_path = pdf_dir / f"{_safe_filename(name)}.pdf"
        row = {"layout": name, "pdf_path": str(pdf_path), "exported": False, "error": ""}
        try:
            doc.ActiveLayout = layout
            # Uses the layout's existing plot settings. This avoids writing plot
            # settings into the DWG, but still depends on the current ZWCAD setup.
            doc.Plot.PlotToFile(str(pdf_path))
            row["exported"] = pdf_path.exists()
        except Exception as exc:
            row["error"] = str(exc)
        results.append(row)
    try:
        if original_layout:
            doc.ActiveLayout = doc.Layouts.Item(original_layout)
    except Exception:
        pass
    return results


def _safe_filename(value: str) -> str:
    keep = []
    for char in value:
        if char.isalnum() or char in {"-", "_"}:
            keep.append(char)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "layout"


def analyze_pdf_files(out_dir: Path) -> list[dict[str, Any]]:
    pdf_dir = out_dir / "pdf"
    rows: list[dict[str, Any]] = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        row: dict[str, Any] = {
            "pdf": str(pdf_path),
            "pages": None,
            "text_char_count": None,
            "text_sample": "",
            "render_available": False,
            "notes": [],
        }
        try:
            import fitz  # type: ignore

            doc = fitz.open(str(pdf_path))
            row["pages"] = doc.page_count
            text = "\n".join(page.get_text("text") for page in doc)
            row["text_char_count"] = len(text)
            row["text_sample"] = text[:1200]
            for index, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
                image_path = out_dir / "images" / f"{pdf_path.stem}_p{index + 1}.png"
                image_path.parent.mkdir(parents=True, exist_ok=True)
                pix.save(str(image_path))
                row["render_available"] = True
        except Exception as exc:
            row["notes"].append(f"PyMuPDF analysis skipped: {exc}")
        rows.append(row)
    return rows


def evaluate_hybrid_compliance(inventory: dict[str, Any]) -> dict[str, Any]:
    print("Loading Hybrid Rule Engines (XiCAD & ArchiOffice & HSSTEEL)...")
    try:
        xicad = XiCADRuleEngine()
        xicad.load_all()
        xicad_layers = xicad.get_layer_standards()
        xicad_layer_names = {k.upper(): v for k, v in xicad_layers.items()}
    except Exception as e:
        print(f"Warning: Failed to load XiCAD rules: {e}")
        xicad_layer_names = {}
        
    try:
        ao = ArchiOfficeRuleEngine()
        ao.load_all()
        ao_catalog = ao.get_block_catalog()
        ao_block_names = set(ao_catalog.get("all_blocks", []))
    except Exception as e:
        print(f"Warning: Failed to load ArchiOffice rules: {e}")
        ao_block_names = set()

    try:
        hssteel = HSSteelRuleEngine()
        hssteel.load_all()
        hs_catalog = hssteel.get_block_catalog()
        hs_block_names = set(hs_catalog.get("all_blocks", []))
    except Exception as e:
        print(f"Warning: Failed to load HSSTEEL rules: {e}")
        hs_block_names = set()
        
    layers = inventory.get("layers", []) if isinstance(inventory, dict) else []
    blocks = inventory.get("blocks", []) if isinstance(inventory, dict) else []
    
    layer_compliance = []
    for lyr in layers:
        lname = str(lyr.get("name", "")).upper()
        if not lname or lname == "0":
            continue
        if lname in xicad_layer_names:
            layer_compliance.append({"name": lname, "standard": "XiCAD", "status": "Compliant", "desc": xicad_layer_names[lname].get("description", "")})
        else:
            layer_compliance.append({"name": lname, "standard": "Unknown", "status": "Non-Compliant"})
            
    block_compliance = []
    for blk in blocks:
        bname = str(blk.get("name", "")).upper()
        if not bname or bname.startswith("*"):
            continue
        if bname in {b.upper() for b in ao_block_names}:
            block_compliance.append({"name": bname, "standard": "ArchiOffice", "status": "Compliant"})
        elif bname in {b.upper() for b in hs_block_names}:
            block_compliance.append({"name": bname, "standard": "HSSTEEL", "status": "Compliant"})
        else:
            block_compliance.append({"name": bname, "standard": "Unknown", "status": "Non-Compliant"})
            
    return {
        "xicad_layer_compliance_rate": f"{(len([l for l in layer_compliance if l['status'] == 'Compliant']) / max(1, len(layer_compliance)) * 100):.1f}%",
        "archioffice_block_compliance_rate": f"{(len([b for b in block_compliance if b['standard'] == 'ArchiOffice']) / max(1, len(block_compliance)) * 100):.1f}%",
        "hssteel_block_compliance_rate": f"{(len([b for b in block_compliance if b['standard'] == 'HSSTEEL']) / max(1, len(block_compliance)) * 100):.1f}%",
        "total_block_compliance_rate": f"{(len([b for b in block_compliance if b['status'] == 'Compliant']) / max(1, len(block_compliance)) * 100):.1f}%",
        "non_compliant_layers": [l["name"] for l in layer_compliance if l["status"] == "Non-Compliant"],
        "non_compliant_blocks": [b["name"] for b in block_compliance if b["status"] == "Non-Compliant"]
    }


def build_visual_code_model(inventory: dict[str, Any], layout_targets: list[dict[str, Any]], pdf_analysis: list[dict[str, Any]]) -> dict[str, Any]:
    layers = inventory.get("layers", []) if isinstance(inventory, dict) else []
    unknown = inventory.get("unknown_layers", []) if isinstance(inventory, dict) else []
    mapping = inventory.get("mapping_candidates", []) if isinstance(inventory, dict) else []
    linetype_counter = Counter(str(row.get("current_linetype") or "") for row in layers if isinstance(row, dict))
    return {
        "schema_version": 1,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_inventory": str(INVENTORY_PATH),
        "purpose": "Convert visual/PDF review needs back into machine-readable cleanup rules.",
        "drawing_summary": inventory.get("summary", {}),
        "hybrid_compliance_audit": evaluate_hybrid_compliance(inventory),
        "layout_plot_targets": layout_targets,
        "pdf_analysis": pdf_analysis,
        "visual_check_rules": [asdict(rule) for rule in VISUAL_CHECK_RULES],
        "layer_visual_priorities": {
            "zero_layer_object_count": inventory.get("summary", {}).get("zero_layer_object_count"),
            "unknown_layer_count": len(unknown),
            "mapping_candidate_count": len(mapping),
            "linetypes_in_use": dict(linetype_counter),
        },
        "next_code_tasks": [
            {
                "task": "export_layout_pdf",
                "status": "ready_when_export_pdf_flag_is_used",
                "inputs": ["active ZWCAD document", "layout plot settings"],
                "outputs": ["pdf/*.pdf", "images/*.png"],
            },
            {
                "task": "review_pdf_images",
                "status": "requires_generated_pdf_or_png",
                "outputs": ["sheet_regions", "visual_linetype_observations", "text_quality_findings"],
            },
            {
                "task": "merge_visual_findings_into_layer_rules",
                "status": "prepared",
                "outputs": ["layer_alias_updates", "sheet_specific_rules"],
            },
        ],
    }


def write_report(model: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "visual_code_model.json").write_text(json.dumps(model, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
    lines = [
        "# Visual Analysis Preparation",
        "",
        f"- Generated: {model['generated_at']}",
        f"- Source inventory: {model['source_inventory']}",
        "",
        "## Drawing Summary",
    ]
    for key, value in model.get("drawing_summary", {}).items():
        lines.append(f"- {key}: {value}")
    lines += ["", "## Layout Plot Targets", "| Layout | Plotter | Media | PDF |", "|---|---|---|---|"]
    for row in model.get("layout_plot_targets", []):
        lines.append(f"| {row.get('layout')} | {row.get('config_name')} | {row.get('canonical_media_name')} | {row.get('pdf_path', '')} |")
    lines += ["", "## Visual Checks To Convert Back To Code", "| Key | Visual Signal | Code Output |", "|---|---|---|"]
    for rule in model.get("visual_check_rules", []):
        lines.append(f"| {rule['key']} | {rule['visual_signal']} | {rule['code_output']} |")
        
    lines += ["", "## Hybrid CAD Standard Compliance Audit (XiCAD + ArchiOffice + HSSTEEL)"]
    compliance = model.get("hybrid_compliance_audit", {})
    lines.append(f"- **XiCAD Layer Compliance Rate**: {compliance.get('xicad_layer_compliance_rate', '0%')}")
    lines.append(f"- **ArchiOffice Block Compliance Rate**: {compliance.get('archioffice_block_compliance_rate', '0%')}")
    lines.append(f"- **HSSTEEL Structural Block Compliance Rate**: {compliance.get('hssteel_block_compliance_rate', '0%')}")
    lines.append(f"- **Total Standard Block Compliance Rate**: {compliance.get('total_block_compliance_rate', '0%')}")
    lines.append(f"- **Non-Compliant Layers (Count: {len(compliance.get('non_compliant_layers', []))})**: {', '.join(compliance.get('non_compliant_layers', [])[:10])} ...")
    lines.append(f"- **Non-Compliant Blocks (Count: {len(compliance.get('non_compliant_blocks', []))})**: {', '.join(compliance.get('non_compliant_blocks', [])[:10])} ...")

    lines += ["", "## Next Code Tasks"]
    for task in model.get("next_code_tasks", []):
        lines.append(f"- {task['task']}: {task['status']}")
    (out_dir / "visual_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare PDF/visual analysis artifacts for the active ZWCAD drawing.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--export-pdf", action="store_true", help="Export each paper layout using its current plot settings.")
    parser.add_argument("--include-model", action="store_true", help="Also try plotting the Model layout.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    inventory = _load_inventory(INVENTORY_PATH)
    layout_targets = collect_layout_plot_targets()
    if args.export_pdf:
        exported = try_export_layout_pdfs(out_dir, include_model=args.include_model)
        by_layout = {row.get("layout"): row for row in exported}
        for row in layout_targets:
            export_row = by_layout.get(row.get("layout"))
            if export_row:
                row["pdf_path"] = export_row.get("pdf_path", "")
                row["pdf_exported"] = export_row.get("exported", False)
                row["pdf_error"] = export_row.get("error", "")
    pdf_analysis = analyze_pdf_files(out_dir)
    model = build_visual_code_model(inventory, layout_targets, pdf_analysis)
    write_report(model, out_dir)
    print(json.dumps({"out_dir": str(out_dir), "layouts": len(layout_targets), "pdfs": len(pdf_analysis)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
