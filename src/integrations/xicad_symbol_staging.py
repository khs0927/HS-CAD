from __future__ import annotations

import json
import re
import shutil
import subprocess
import csv
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
ANONYMOUS_BLOCK_PREFIXES = ("*U", "*A", "*D")


@dataclass
class ShapeFeatures:
    source: str = ""
    entity_count: int = 0
    entity_counts: dict[str, int] | None = None
    width: float = 0.0
    height: float = 0.0
    aspect_ratio: float = 0.0
    has_text: bool = False
    has_circle: bool = False
    has_arc: bool = False
    has_insert: bool = False


@dataclass
class SymbolCandidate:
    name: str
    sanitized_name: str
    category: str
    confidence: float
    reason: list[str]
    target_folder: str
    shape: ShapeFeatures | None
    source_status: str
    source_path: str | None = None
    staged_path: str | None = None
    preview_path: str | None = None


def sanitize_symbol_filename(name: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub("_", name).strip().strip(".")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:120] or "unnamed_symbol"


def _upper(name: str) -> str:
    return name.upper().strip()


def _is_review_only_name(name: str) -> bool:
    up = _upper(name)
    return up.startswith("A$C") or up.startswith(ANONYMOUS_BLOCK_PREFIXES) or up.startswith("XREF-")


def classify_symbol(name: str, shape: ShapeFeatures | None = None) -> tuple[str, float, list[str]]:
    """Classify a CAD block using fast name rules plus optional geometry hints.

    The geometry rules are deliberately conservative: they improve sorting but
    do not pretend to replace a human check before installing symbols into XiCAD.
    """

    up = _upper(name)
    reason: list[str] = []

    if _is_review_only_name(name):
        return "review_only", 0.3, ["anonymous_or_xref_name"]

    keyword_rules: list[tuple[str, tuple[str, ...], str, float]] = [
        ("title_sheet", ("ZIUM_SHEET", "TITLE", "SHEET", "도곽", "표제"), "title/name", 0.94),
        ("brand", ("ZIUM LOGO", "LOGO"), "brand/name", 0.9),
        ("door", ("DOOR", "-D-", "$0$D", "문", "도어"), "door/name", 0.82),
        ("window", ("WINDOW", "-W-", "$0$W", "창호", "창문"), "window/name", 0.82),
        ("sanitary", ("TOILET", "BATH", "SINK", "INUS", "TOIP", "KITPD", "위생", "변기", "세면"), "sanitary/name", 0.86),
        ("furniture", ("CHAIR", "SOFA", "BED", "TABLE", "FURN", "가구"), "furniture/name", 0.78),
        ("vehicle", ("CAR", "PARK", "차량", "주차"), "vehicle/name", 0.78),
        ("landscape", ("TREE", "LAND", "조경", "식재", "투수"), "landscape/name", 0.78),
        ("security", ("CCTV", "CAMERA", "보안"), "security/name", 0.82),
        ("structure", ("COL", "COLUMN", "BEAM", "ANCHOR", "BOLT", "기둥", "보"), "structure/name", 0.78),
        ("annotation_symbol", ("ARROW", "DOT", "BUBBLE", "SYM", "HANDI", "표시", "부호"), "symbol/name", 0.78),
        ("material", ("INSUL", "INSU", "MATERIAL", "재료", "단열"), "material/name", 0.72),
    ]
    for category, tokens, marker, confidence in keyword_rules:
        if any(token in up or token in name for token in tokens):
            return category, confidence, [marker]

    if shape and shape.entity_count:
        counts = shape.entity_counts or {}
        lineish = sum(counts.get(k, 0) for k in ("LINE", "LWPOLYLINE", "POLYLINE"))
        circles = counts.get("CIRCLE", 0)
        arcs = counts.get("ARC", 0)
        text = counts.get("TEXT", 0) + counts.get("MTEXT", 0) + counts.get("ATTRIB", 0) + counts.get("ATTDEF", 0)

        if text and shape.entity_count <= max(8, text * 3):
            reason.append("mostly_text_geometry")
            return "annotation_symbol", 0.64, reason
        if arcs and lineish and 0.3 <= shape.aspect_ratio <= 3.5:
            reason.append("arc_and_line_geometry")
            return "door_or_fixture", 0.58, reason
        if lineish >= 4 and (shape.aspect_ratio >= 3.0 or shape.aspect_ratio <= 0.33):
            reason.append("long_rectilinear_geometry")
            return "window_or_linear_symbol", 0.56, reason
        if circles and circles >= lineish:
            reason.append("circle_dominant_geometry")
            return "annotation_symbol", 0.54, reason

    return "general_symbol", 0.42, ["fallback"]


def load_observed_block_names(report_path: str | Path) -> list[str]:
    data = json.loads(Path(report_path).read_text(encoding="utf-8"))
    names = data.get("user_blocks_observed", [])
    if not isinstance(names, list):
        return []
    return sorted({str(name) for name in names if str(name).strip()})


def read_text_any(path: str | Path) -> str:
    file_path = Path(path)
    for encoding in ("utf-8-sig", "cp949", "euc-kr", "utf-8", "latin1"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="replace")


def parse_xicad_block_layer_config(path: str | Path) -> list[dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in read_text_any(file_path).splitlines():
        line = raw.strip()
        if not line or line.startswith(";") or line.startswith(";;;"):
            continue
        parts = [part.strip() for part in line.split(";")]
        if len(parts) < 4:
            continue
        if parts[0] in {"분류", "Category"}:
            continue
        rows.append(
            {
                "key": parts[0],
                "layer": parts[1],
                "linetype": parts[2],
                "color": int(parts[3]) if str(parts[3]).isdigit() else parts[3],
                "description": parts[4] if len(parts) > 4 else "",
            }
        )
    return rows


def parse_xicad_block_library_config(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    lines = read_text_any(file_path).splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "/xiBlkLibrary" and index + 1 < len(lines):
            parts = [part.strip() for part in lines[index + 1].split("|")]
            return {
                "raw": lines[index + 1],
                "root": parts[0] if parts else "",
                "default_folder": parts[1] if len(parts) > 1 else "",
                "options": parts[2:],
            }
    return {}


def _folder_file_stats(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not root.exists():
        return rows
    for folder in [root, *[p for p in root.rglob("*") if p.is_dir()]]:
        dwg = list(folder.glob("*.dwg"))
        sld = list(folder.glob("*.sld"))
        if not dwg and not sld:
            continue
        rows.append(
            {
                "folder": str(folder),
                "relative": str(folder.relative_to(root)) if folder != root else ".",
                "dwg_count": len(dwg),
                "sld_count": len(sld),
                "preview_coverage": round((len(sld) / len(dwg)), 3) if dwg else 0,
                "sample_dwg": [p.name for p in sorted(dwg)[:8]],
            }
        )
    return rows


def analyze_xicad_symbol_system(
    xicad_root: str | Path = "C:/xicad",
    out_path: str | Path = "generated/xicad_symbols_staging/xicad_symbol_system_analysis.json",
) -> dict[str, Any]:
    root = Path(xicad_root)
    xilib = root / "xiLib"
    lib = root / "Lib"
    cfg_rows = parse_xicad_block_layer_config(xilib / "xiBlkLayerSet.cfg")
    txt_rows = parse_xicad_block_layer_config(xilib / "xiBlkLayerSet.txt")
    block_library = parse_xicad_block_library_config(xilib / "xiConfig.cfg")

    payload = {
        "xicad_root": str(root),
        "xi_block_library_config": block_library,
        "symbol_layer_rules_cfg": cfg_rows,
        "symbol_layer_rules_txt": txt_rows,
        "folder_stats": {
            "xiLib": _folder_file_stats(xilib),
            "Lib": _folder_file_stats(lib),
        },
        "totals": {
            "xiLib_dwg": len(list(xilib.rglob("*.dwg"))) if xilib.exists() else 0,
            "xiLib_sld": len(list(xilib.rglob("*.sld"))) if xilib.exists() else 0,
            "Lib_dwg": len(list(lib.rglob("*.dwg"))) if lib.exists() else 0,
            "Lib_sld": len(list(lib.rglob("*.sld"))) if lib.exists() else 0,
        },
        "recommended_hscad_install_root": str(xilib / "심볼" / "HS-CAD"),
        "category_mapping": {
            "annotation_symbol": {"xicad_key": "ETC", "layer": "SYM"},
            "door": {"xicad_key": "DOOR", "layer": "DOOR"},
            "door_or_fixture": {"xicad_key": "DOOR", "layer": "DOOR"},
            "window": {"xicad_key": "WINDOW", "layer": "WIN"},
            "window_or_linear_symbol": {"xicad_key": "WINDOW", "layer": "WIN"},
            "sanitary": {"xicad_key": "FIX", "layer": "FIX"},
            "furniture": {"xicad_key": "FURN", "layer": "FURN"},
            "vehicle": {"xicad_key": "CAR", "layer": "CAR"},
            "landscape": {"xicad_key": "LAND", "layer": "LAND"},
            "material": {"xicad_key": "MATRIAL", "layer": "MATRIAL"},
            "structure": {"xicad_key": "ETC", "layer": "SYM"},
            "title_sheet": {"xicad_key": "ETC", "layer": "SYM"},
            "brand": {"xicad_key": "ETC", "layer": "SYM"},
            "security": {"xicad_key": "ETC", "layer": "SYM"},
            "general_symbol": {"xicad_key": "ETC", "layer": "SYM"},
        },
    }

    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_xicad_analysis_md(payload, output.with_suffix(".md"))
    return payload


def _write_xicad_analysis_md(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# XiCAD Symbol System Analysis",
        "",
        f"- XiCAD root: `{payload['xicad_root']}`",
        f"- Recommended HS-CAD install root: `{payload['recommended_hscad_install_root']}`",
        f"- xiLib DWG/SLD: {payload['totals']['xiLib_dwg']} / {payload['totals']['xiLib_sld']}",
        f"- Lib DWG/SLD: {payload['totals']['Lib_dwg']} / {payload['totals']['Lib_sld']}",
        "",
        "## xiBlkLibrary",
        f"- Raw: `{payload['xi_block_library_config'].get('raw', '')}`",
        "",
        "## Symbol Layer Rules",
        "| Key | Layer | Linetype | Color | Description |",
        "|---|---|---|---:|---|",
    ]
    for row in payload["symbol_layer_rules_cfg"]:
        lines.append(f"| {row['key']} | {row['layer']} | {row['linetype']} | {row['color']} | {row['description']} |")
    lines.extend(["", "## Folder Stats", "| Relative | DWG | SLD | Preview Coverage | Samples |", "|---|---:|---:|---:|---|"])
    for row in payload["folder_stats"]["xiLib"]:
        lines.append(
            f"| {row['relative']} | {row['dwg_count']} | {row['sld_count']} | "
            f"{row['preview_coverage']} | {', '.join(row['sample_dwg'][:4])} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _candidate_block_files(xicad_root: Path) -> dict[str, Path]:
    roots = [xicad_root / "xiLib", xicad_root / "Lib"]
    found: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.dwg"):
            found.setdefault(path.stem.upper(), path)
    return found


def discover_cad_sources(
    roots: Iterable[str | Path],
    exclude_parts: Iterable[str] = ("generated/xicad_symbols_staging", "generated/zwcad_symbol_live_test"),
) -> list[Path]:
    excludes = {str(part).replace("\\", "/").lower() for part in exclude_parts}
    sources: list[Path] = []
    for root in roots:
        path = Path(root)
        if path.is_file() and path.suffix.lower() in {".dwg", ".dxf"}:
            sources.append(path)
            continue
        if not path.exists():
            continue
        for item in path.rglob("*"):
            if item.suffix.lower() not in {".dwg", ".dxf"}:
                continue
            normalized = str(item).replace("\\", "/").lower()
            if any(part in normalized for part in excludes):
                continue
            sources.append(item)
    return sorted(set(sources))


def prepare_dxf_sources(
    cad_sources: Iterable[str | Path],
    out_dir: str | Path = "generated/xicad_symbols_staging/converted_dxf",
    oda_converter: str | Path | None = None,
) -> tuple[list[Path], list[dict[str, Any]]]:
    from src.scanners.dxf_indexer import convert_dwg_to_dxf

    dxf_sources: list[Path] = []
    rows: list[dict[str, Any]] = []
    out = Path(out_dir)
    for source in cad_sources:
        path = Path(source)
        if path.suffix.lower() == ".dxf":
            dxf_sources.append(path)
            rows.append({"source": str(path), "status": "already_dxf", "dxf": str(path)})
        elif path.suffix.lower() == ".dwg":
            target_dir = out / sanitize_symbol_filename(path.stem)
            try:
                dxf = convert_dwg_to_dxf(path, target_dir, str(oda_converter) if oda_converter else None)
                dxf_sources.append(dxf)
                rows.append({"source": str(path), "status": "converted", "dxf": str(dxf)})
            except Exception as exc:
                rows.append({"source": str(path), "status": "conversion_failed", "error": str(exc)})
    return dxf_sources, rows


def build_all_drawing_block_catalog(
    dxf_sources: Iterable[str | Path],
    xicad_root: str | Path = "C:/xicad",
    out_dir: str | Path = "generated/xicad_symbols_staging/all_drawings",
    target_subdir: str = "HS-CAD-ALL",
) -> dict[str, Any]:
    features = extract_dxf_block_features(dxf_sources)
    root = Path(xicad_root)
    known_dwg = _candidate_block_files(root)
    candidates: list[SymbolCandidate] = []

    for key, shape in sorted(features.items()):
        name = key
        sanitized = sanitize_symbol_filename(name)
        category, confidence, reason = classify_symbol(name, shape)
        source = known_dwg.get(key)
        candidates.append(
            SymbolCandidate(
                name=name,
                sanitized_name=sanitized,
                category=category,
                confidence=confidence,
                reason=reason,
                target_folder=f"xiLib/심볼/{target_subdir}/{category}",
                shape=shape,
                source_status="matched_existing_xicad_dwg" if source else "from_drawing_definition",
                source_path=str(source) if source else shape.source,
            )
        )

    by_category = Counter(item.category for item in candidates)
    by_status = Counter(item.source_status for item in candidates)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": "all_drawing_block_catalog",
        "dxf_sources": [str(Path(path)) for path in dxf_sources],
        "xicad_root": str(root),
        "staging_dir": str(out),
        "intended_install_dir": str(root / "xiLib" / "심볼" / target_subdir),
        "counts": {
            "total": len(candidates),
            "by_category": dict(sorted(by_category.items())),
            "by_source_status": dict(sorted(by_status.items())),
        },
        "candidates": [
            {
                **asdict(candidate),
                "shape": asdict(candidate.shape) if candidate.shape else None,
            }
            for candidate in candidates
        ],
    }
    (out / "all_drawing_block_catalog.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_report(payload, out / "all_drawing_block_catalog.md")
    return payload


def export_all_drawing_blocks_to_xicad(
    roots: Iterable[str | Path],
    xicad_root: str | Path = "C:/xicad",
    out_dir: str | Path = "generated/xicad_symbols_staging/all_drawings",
    target_subdir: str = "HS-CAD-ALL",
    install: bool = False,
    include_review_only: bool = False,
    oda_converter: str | Path | None = None,
) -> dict[str, Any]:
    out = Path(out_dir)
    sources = discover_cad_sources(roots)
    dxf_sources, conversions = prepare_dxf_sources(sources, out / "converted_dxf", oda_converter)
    catalog = build_all_drawing_block_catalog(dxf_sources, xicad_root=xicad_root, out_dir=out, target_subdir=target_subdir)
    for generated_dir in (out / "exported_dxf", out / "exported_dwg"):
        if generated_dir.exists():
            shutil.rmtree(generated_dir)
    export_payload = export_dxf_block_symbols(
        dxf_sources=dxf_sources,
        catalog_path=out / "all_drawing_block_catalog.json",
        out_dir=out / "exported_dxf",
        convert_to_dwg=True,
        oda_converter=oda_converter,
    )

    installed: list[dict[str, Any]] = []
    if install:
        source_root = out / "exported_dwg"
        target_root = Path(xicad_root) / "xiLib" / "심볼" / target_subdir
        for category_dir in sorted(p for p in source_root.glob("*") if p.is_dir()):
            if category_dir.name == "review_only" and not include_review_only:
                installed.append({"category": category_dir.name, "status": "skipped_review_only"})
                continue
            target = target_root / category_dir.name
            target.mkdir(parents=True, exist_ok=True)
            copied = 0
            for file_path in category_dir.glob("*.dwg"):
                shutil.copy2(file_path, target / file_path.name)
                copied += 1
            installed.append({"category": category_dir.name, "status": "installed", "target": str(target), "count": copied})

    payload = {
        "mode": "all_drawings_to_xicad_blocks",
        "sources": [str(path) for path in sources],
        "conversions": conversions,
        "catalog": {
            "path": str(out / "all_drawing_block_catalog.json"),
            "counts": catalog["counts"],
        },
        "export": {
            "path": str(out / "hs_cad_symbol_export_report.json"),
            "exported_count": export_payload["exported_count"],
            "converted": export_payload["converted"],
        },
        "install": {
            "enabled": install,
            "target": str(Path(xicad_root) / "xiLib" / "심볼" / target_subdir),
            "include_review_only": include_review_only,
            "installed": installed,
        },
    }
    (out / "all_drawings_to_xicad_report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def configure_xicad_block_library_default(
    xicad_root: str | Path = "C:/xicad",
    default_folder: str = r"<MAINPATH>\심볼\HS-CAD-XICAD",
    backup_dir: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(xicad_root)
    cfg = root / "xiLib" / "xiConfig.cfg"
    if not cfg.exists():
        raise FileNotFoundError(cfg)

    backup_root = Path(backup_dir) if backup_dir else root / "xicad_backup"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup = backup_root / f"xiConfig_before_hscad_{datetime.now().strftime('%Y%m%d_%H%M%S')}.cfg"
    shutil.copy2(cfg, backup)

    text = read_text_any(cfg)
    lines = text.splitlines()
    old_value = None
    new_value = None
    changed = False
    for index, line in enumerate(lines):
        if line.strip() == "/xiBlkLibrary" and index + 1 < len(lines):
            old_value = lines[index + 1]
            parts = old_value.split("|")
            if len(parts) < 2:
                raise ValueError("Invalid /xiBlkLibrary config line")
            parts[1] = default_folder
            new_value = "|".join(parts)
            lines[index + 1] = new_value
            changed = old_value != new_value
            break
    if old_value is None:
        raise ValueError("/xiBlkLibrary section was not found")

    cfg.write_text("\n".join(lines) + "\n", encoding="cp949", errors="replace")
    payload = {
        "config": str(cfg),
        "backup": str(backup),
        "old_value": old_value,
        "new_value": new_value,
        "changed": changed,
    }
    return payload


def mirror_hscad_library_to_xicad_native_folders(
    source_subdir: str = "HS-CAD-ALL",
    target_subdir: str = "HS-CAD-XICAD",
    xicad_root: str | Path = "C:/xicad",
    catalog_path: str | Path = "generated/xicad_symbols_staging/all_drawings/all_drawing_block_catalog.json",
    analysis_path: str | Path = "generated/xicad_symbols_staging/xicad_symbol_system_analysis.json",
    out_path: str | Path = "generated/xicad_symbols_staging/all_drawings/xicad_native_folder_mirror_report.json",
    clear_target: bool = True,
) -> dict[str, Any]:
    root = Path(xicad_root)
    symbol_root = root / "xiLib" / "심볼"
    source_root = symbol_root / source_subdir
    target_root = symbol_root / target_subdir
    if not source_root.exists():
        raise FileNotFoundError(source_root)

    catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    analysis = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
    mapping = analysis.get("category_mapping", {})
    fallback = mapping.get("general_symbol", {"xicad_key": "ETC", "layer": "SYM"})

    if clear_target and target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)

    installed = {p.name.upper(): p for p in source_root.rglob("*.dwg")}
    rows: list[dict[str, Any]] = []
    for item in catalog.get("candidates", []):
        if item.get("category") == "review_only":
            continue
        filename = f"{item['sanitized_name']}.dwg"
        source = installed.get(filename.upper())
        if not source:
            rows.append({"name": item.get("name"), "category": item.get("category"), "status": "not_installed_in_source"})
            continue
        rule = mapping.get(item.get("category"), fallback)
        folder = target_root / f"{rule['xicad_key']}_{rule['layer']}"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / source.name
        shutil.copy2(source, target)
        rows.append(
            {
                "name": item.get("name"),
                "category": item.get("category"),
                "xicad_key": rule["xicad_key"],
                "layer": rule["layer"],
                "source": str(source),
                "target": str(target),
                "status": "copied",
            }
        )

    payload = {
        "source_root": str(source_root),
        "target_root": str(target_root),
        "copied_count": sum(1 for row in rows if row["status"] == "copied"),
        "skipped_count": sum(1 for row in rows if row["status"] != "copied"),
        "by_folder": {p.name: len(list(p.glob("*.dwg"))) for p in sorted(target_root.iterdir()) if p.is_dir()},
        "rows": rows,
    }
    output = Path(out_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# HS-CAD XiCAD-Native Folder Mirror",
        "",
        f"- Source: `{source_root}`",
        f"- Target: `{target_root}`",
        f"- Copied: {payload['copied_count']}",
        f"- Skipped: {payload['skipped_count']}",
        "",
        "## Folders",
    ]
    for folder, count in payload["by_folder"].items():
        md.append(f"- `{folder}`: {count}")
    output.with_suffix(".md").write_text("\n".join(md), encoding="utf-8")
    return payload


def build_master_symbol_review_table(
    xicad_root: str | Path = "C:/xicad",
    libraries: Iterable[str] = ("HS-CAD-ALL", "HS-CAD-XICAD", "HS-CAD-REVIEW"),
    catalog_path: str | Path = "generated/xicad_symbols_staging/all_drawings/all_drawing_block_catalog.json",
    validation_reports: dict[str, str | Path] | None = None,
    out_dir: str | Path = "generated/xicad_symbols_staging",
) -> dict[str, Any]:
    root = Path(xicad_root) / "xiLib" / "심볼"
    catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    by_name = {f"{item['sanitized_name'].upper()}.DWG": item for item in catalog.get("candidates", [])}
    reports = validation_reports or {}
    validated: dict[tuple[str, str], dict[str, Any]] = {}
    for library, report_path in reports.items():
        path = Path(report_path)
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        for row in report.get("rows", []):
            validated[(library, str(row.get("file", "")).upper())] = row

    rows: list[dict[str, Any]] = []
    for library in libraries:
        library_root = root / library
        if not library_root.exists():
            continue
        for path in sorted(library_root.rglob("*.dwg")):
            file_key = path.name.upper()
            item = by_name.get(file_key, {})
            validation = validated.get((library, file_key), {})
            rows.append(
                {
                    "library": library,
                    "folder": str(path.parent.relative_to(library_root)),
                    "file": path.name,
                    "path": str(path),
                    "category": item.get("category", "review_only" if library == "HS-CAD-REVIEW" else ""),
                    "confidence": item.get("confidence", ""),
                    "reason": ", ".join(item.get("reason", [])) if item else "",
                    "source_status": item.get("source_status", ""),
                    "source_path": item.get("source_path", ""),
                    "zwcad_insert_status": validation.get("status", ""),
                    "effective_name": validation.get("effective_name", ""),
                    "handle": validation.get("handle", ""),
                    "action_recommendation": "promote_manually_if_needed" if library == "HS-CAD-REVIEW" else "ready",
                }
            )

    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "master_symbol_review_table.csv"
    if rows:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("", encoding="utf-8-sig")

    md_path = output_dir / "master_symbol_review_table.md"
    md = [
        "# Master Symbol Review Table",
        "",
        f"- Rows: {len(rows)}",
        f"- CSV: `{csv_path}`",
        "",
        "| Library | Folder | File | Category | Insert | Recommendation |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        md.append(
            f"| {row['library']} | {row['folder']} | {row['file']} | {row['category']} | "
            f"{row['zwcad_insert_status']} | {row['action_recommendation']} |"
        )
    md_path.write_text("\n".join(md), encoding="utf-8")

    payload = {"csv": str(csv_path), "markdown": str(md_path), "rows": len(rows)}
    (output_dir / "master_symbol_review_table.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _point_bbox(points: Iterable[tuple[float, float]]) -> tuple[float, float, float, float] | None:
    pts = list(points)
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def _entity_bbox(entity: Any) -> tuple[float, float, float, float] | None:
    typ = entity.dxftype()
    try:
        if typ == "LINE":
            return _point_bbox([(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)])
        if typ in {"LWPOLYLINE", "POLYLINE"}:
            points = []
            if typ == "LWPOLYLINE":
                points = [(float(p[0]), float(p[1])) for p in entity.get_points()]
            else:
                points = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
            return _point_bbox(points)
        if typ in {"CIRCLE", "ARC"}:
            center = entity.dxf.center
            radius = float(entity.dxf.radius)
            return center.x - radius, center.y - radius, center.x + radius, center.y + radius
        if typ in {"TEXT", "MTEXT", "INSERT", "ATTDEF", "ATTRIB"}:
            point = getattr(entity.dxf, "insert", None) or getattr(entity.dxf, "location", None)
            if point is not None:
                return point.x, point.y, point.x, point.y
    except Exception:
        return None
    return None


def extract_dxf_block_features(dxf_paths: Iterable[str | Path]) -> dict[str, ShapeFeatures]:
    import ezdxf

    features: dict[str, ShapeFeatures] = {}
    for dxf_path in dxf_paths:
        path = Path(dxf_path)
        if not path.exists() or path.suffix.lower() != ".dxf":
            continue
        try:
            doc = ezdxf.readfile(path)
        except Exception:
            continue
        for block in doc.blocks:
            name = block.name
            if not name or name.startswith("*"):
                continue
            counts: Counter[str] = Counter()
            bboxes = []
            for entity in block:
                typ = entity.dxftype()
                counts[typ] += 1
                bbox = _entity_bbox(entity)
                if bbox:
                    bboxes.append(bbox)
            if bboxes:
                xmin = min(b[0] for b in bboxes)
                ymin = min(b[1] for b in bboxes)
                xmax = max(b[2] for b in bboxes)
                ymax = max(b[3] for b in bboxes)
                width = xmax - xmin
                height = ymax - ymin
            else:
                width = height = 0.0
            aspect = (width / height) if height else (999.0 if width else 0.0)
            key = name.upper()
            features[key] = ShapeFeatures(
                source=str(path),
                entity_count=sum(counts.values()),
                entity_counts=dict(counts),
                width=round(width, 3),
                height=round(height, 3),
                aspect_ratio=round(aspect, 3),
                has_text=any(k in counts for k in ("TEXT", "MTEXT", "ATTRIB", "ATTDEF")),
                has_circle=counts.get("CIRCLE", 0) > 0,
                has_arc=counts.get("ARC", 0) > 0,
                has_insert=counts.get("INSERT", 0) > 0,
            )
    return features


def build_xicad_symbol_staging(
    observed_report: str | Path = "generated/fast_scan_report.json",
    dxf_sources: Iterable[str | Path] = (),
    xicad_root: str | Path = "C:/xicad",
    out_dir: str | Path = "generated/xicad_symbols_staging",
    target_subdir: str = "HS-CAD",
    copy_matches: bool = True,
) -> dict[str, Any]:
    names = load_observed_block_names(observed_report)
    root = Path(xicad_root)
    out = Path(out_dir)
    stage_dir = out / target_subdir
    stage_dir.mkdir(parents=True, exist_ok=True)

    known_dwg = _candidate_block_files(root)
    dxf_features = extract_dxf_block_features(dxf_sources)
    candidates: list[SymbolCandidate] = []

    for name in names:
        sanitized = sanitize_symbol_filename(name)
        shape = dxf_features.get(name.upper())
        category, confidence, reason = classify_symbol(name, shape)
        target_folder = f"xiLib/심볼/{target_subdir}/{category}"
        source = known_dwg.get(name.upper())
        staged_path = None
        preview_path = None
        status = "needs_wblock_export"

        if source:
            status = "matched_existing_xicad_dwg"
            if copy_matches:
                target = stage_dir / category
                target.mkdir(parents=True, exist_ok=True)
                staged = target / f"{sanitized}.dwg"
                shutil.copy2(source, staged)
                staged_path = str(staged)
                sld = source.with_suffix(".sld")
                if sld.exists():
                    preview = target / f"{sanitized}.sld"
                    shutil.copy2(sld, preview)
                    preview_path = str(preview)

        candidates.append(
            SymbolCandidate(
                name=name,
                sanitized_name=sanitized,
                category=category,
                confidence=confidence,
                reason=reason,
                target_folder=target_folder,
                shape=shape,
                source_status=status,
                source_path=str(source) if source else None,
                staged_path=staged_path,
                preview_path=preview_path,
            )
        )

    by_category = Counter(item.category for item in candidates)
    by_status = Counter(item.source_status for item in candidates)
    payload = {
        "mode": "staging_only_no_xicad_install",
        "observed_report": str(observed_report),
        "xicad_root": str(root),
        "staging_dir": str(stage_dir),
        "intended_install_dir": str(root / "xiLib" / "심볼" / target_subdir),
        "counts": {
            "total": len(candidates),
            "by_category": dict(sorted(by_category.items())),
            "by_source_status": dict(sorted(by_status.items())),
        },
        "candidates": [
            {
                **asdict(candidate),
                "shape": asdict(candidate.shape) if candidate.shape else None,
            }
            for candidate in candidates
        ],
    }

    (out / "hs_cad_symbol_catalog.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown_report(payload, out / "hs_cad_symbol_catalog.md")
    return payload


def export_dxf_block_symbols(
    dxf_sources: Iterable[str | Path],
    catalog_path: str | Path = "generated/xicad_symbols_staging/hs_cad_symbol_catalog.json",
    out_dir: str | Path = "generated/xicad_symbols_staging/exported_dxf",
    categories: Iterable[str] | None = None,
    convert_to_dwg: bool = False,
    oda_converter: str | Path | None = None,
) -> dict[str, Any]:
    """Export matching DXF block definitions into per-symbol DXF files.

    This is the fastest open-source path for shape-backed symbols: ezdxf reads
    source DXFs, extracts block content into modelspace, then ODA can convert
    the generated DXFs to DWG for XiCAD's block library.
    """

    import ezdxf
    from ezdxf.addons import Importer

    catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    wanted_categories = set(categories or [])
    wanted: dict[str, dict[str, Any]] = {}
    for item in catalog.get("candidates", []):
        if wanted_categories and item.get("category") not in wanted_categories:
            continue
        if item.get("source_status") == "matched_existing_xicad_dwg":
            continue
        wanted[str(item["name"]).upper()] = item

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    exported: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source in dxf_sources:
        source_path = Path(source)
        if not source_path.exists() or source_path.suffix.lower() != ".dxf":
            continue
        try:
            src_doc = ezdxf.readfile(source_path)
        except Exception as exc:
            exported.append({"source": str(source_path), "status": "read_failed", "error": str(exc)})
            continue

        for block in src_doc.blocks:
            key = block.name.upper()
            if key not in wanted or key in seen or key.startswith("*"):
                continue
            item = wanted[key]
            category = item.get("category", "general_symbol")
            target_dir = out / category
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{item['sanitized_name']}.dxf"

            target_doc = ezdxf.new("R2018")
            importer = Importer(src_doc, target_doc)
            importer.import_entities(block, target_doc.modelspace())
            importer.finalize()
            target_doc.saveas(target)
            seen.add(key)
            exported.append(
                {
                    "name": item["name"],
                    "category": category,
                    "source": str(source_path),
                    "dxf_path": str(target),
                    "status": "exported_dxf",
                }
            )

    converted = []
    if convert_to_dwg and exported:
        converter = Path(oda_converter) if oda_converter else _find_oda_converter()
        if converter is None:
            converted.append({"status": "skipped", "reason": "ODA File Converter not found"})
        else:
            converted = _convert_exported_dxf_dirs(out, converter)

    payload = {
        "catalog_path": str(catalog_path),
        "out_dir": str(out),
        "exported_count": len([row for row in exported if row.get("status") == "exported_dxf"]),
        "exported": exported,
        "converted": converted,
    }
    (Path(out_dir).parent / "hs_cad_symbol_export_report.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def _find_oda_converter() -> Path | None:
    found = shutil.which("ODAFileConverter") or shutil.which("ODAFileConverter.exe")
    if found:
        return Path(found)
    for root in (Path("C:/Program Files/ODA"), Path("C:/Program Files")):
        if root.exists():
            matches = sorted(root.rglob("ODAFileConverter.exe"))
            if matches:
                return matches[-1]
    return None


def _convert_exported_dxf_dirs(out_dir: Path, converter: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category_dir in sorted(p for p in out_dir.iterdir() if p.is_dir()):
        dxf_files = list(category_dir.glob("*.dxf"))
        if not dxf_files:
            continue
        dwg_dir = out_dir.parent / "exported_dwg" / category_dir.name
        dwg_dir.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                [str(converter), str(category_dir), str(dwg_dir), "ACAD2018", "DWG", "0", "1", "*.dxf"],
                check=True,
                text=True,
                capture_output=True,
            )
            rows.append({"category": category_dir.name, "status": "converted", "dwg_dir": str(dwg_dir), "count": len(dxf_files)})
        except subprocess.CalledProcessError as exc:
            rows.append(
                {
                    "category": category_dir.name,
                    "status": "conversion_failed",
                    "returncode": exc.returncode,
                    "stderr": exc.stderr[-1000:] if exc.stderr else "",
                }
            )
    return rows


def _write_markdown_report(payload: dict[str, Any], path: Path) -> None:
    lines = [
        "# HS-CAD XiCAD Symbol Staging",
        "",
        f"- Mode: {payload['mode']}",
        f"- Staging dir: `{payload['staging_dir']}`",
        f"- Intended install dir: `{payload['intended_install_dir']}`",
        f"- Total candidates: {payload['counts']['total']}",
        "",
        "## Category Counts",
    ]
    for key, value in payload["counts"]["by_category"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Source Status"])
    for key, value in payload["counts"]["by_source_status"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Candidates", "", "| Name | Category | Confidence | Status | Reason |", "|---|---:|---:|---|---|"])
    for item in payload["candidates"]:
        lines.append(
            f"| {item['name']} | {item['category']} | {item['confidence']:.2f} | "
            f"{item['source_status']} | {', '.join(item['reason'])} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
