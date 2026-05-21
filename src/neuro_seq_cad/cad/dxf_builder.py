from __future__ import annotations

from pathlib import Path

from neuro_seq_cad.cad.block_factory import ensure_blocks
from neuro_seq_cad.cad.hatch_builder import add_solid_hatch
from neuro_seq_cad.config.cad_units import MILLIMETERS_INSUNITS
from neuro_seq_cad.config.layer_schema import ensure_dxf_layers
from neuro_seq_cad.fusion.evidence_graph import EvidenceGraph


def _new_doc():
    import ezdxf  # type: ignore

    doc = ezdxf.new("R2000")
    doc.header["$INSUNITS"] = MILLIMETERS_INSUNITS
    ensure_dxf_layers(doc)
    ensure_blocks(doc)
    return doc


def _points(entity: dict) -> list[tuple[float, float]]:
    return [tuple(p) for p in entity.get("points", [])]


def build_centerline_dxf(graph: EvidenceGraph, out_path: str | Path) -> tuple[Path | None, list[str]]:
    warnings: list[str] = []
    try:
        doc = _new_doc()
    except Exception as exc:
        return None, [f"optional_dependency_missing: ezdxf is required for DXF export ({exc})"]

    msp = doc.modelspace()
    for entity in graph.entities:
        geom = entity.geometry
        if entity.entity_type == "raw_line":
            p1, p2 = tuple(geom["p1"]), tuple(geom["p2"])
            msp.add_line(p1, p2, dxfattribs={"layer": "RAW_LINES", "color": 8})
        elif entity.entity_type == "wall_centerline":
            p1, p2 = tuple(geom["p1"]), tuple(geom["p2"])
            msp.add_line(p1, p2, dxfattribs={"layer": "CEN"})
        elif entity.entity_type == "door":
            p = tuple(geom.get("insert", (0, 0)))
            msp.add_blockref("DOOR_BLOCK", p, dxfattribs={"layer": "DOOR"})
        elif entity.entity_type == "window":
            p = tuple(geom.get("insert", (0, 0)))
            msp.add_blockref("WINDOW_BLOCK", p, dxfattribs={"layer": "WIN"})
        elif entity.entity_type == "text":
            msp.add_text(str(geom.get("text", "")), dxfattribs={"layer": "TEXT", "height": 250}).set_placement(tuple(geom.get("point", (0, 0))))
        if entity.confidence < 0.45:
            p = tuple(geom.get("point", geom.get("p1", (0, 0))))
            msp.add_circle(p, 120, dxfattribs={"layer": "AI_LOWCONF"})

    for idx, warning in enumerate(graph.warnings):
        msp.add_text(warning[:80], dxfattribs={"layer": "QA_MARKUP", "height": 180}).set_placement((0, -idx * 250))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out)
    return out, warnings


def build_wallsolid_dxf(graph: EvidenceGraph, out_path: str | Path) -> tuple[Path | None, list[str]]:
    warnings: list[str] = []
    try:
        doc = _new_doc()
    except Exception as exc:
        return None, [f"optional_dependency_missing: ezdxf is required for DXF export ({exc})"]

    msp = doc.modelspace()
    for entity in graph.entities:
        geom = entity.geometry
        if entity.entity_type == "wall_polygon":
            pts = _points(geom)
            if len(pts) >= 3:
                msp.add_lwpolyline(pts + [pts[0]], close=True, dxfattribs={"layer": geom.get("layer", "WAL1")})
                ok, warning = add_solid_hatch(msp, pts, "WAL_HATCH")
                if not ok and warning:
                    warnings.append(warning)
            else:
                warnings.append("open_wall_polygon: wall polygon skipped")
        elif entity.entity_type == "raw_line":
            msp.add_line(tuple(geom["p1"]), tuple(geom["p2"]), dxfattribs={"layer": "RAW_LINES", "color": 8})
        elif entity.entity_type == "door":
            msp.add_blockref("DOOR_BLOCK", tuple(geom.get("insert", (0, 0))), dxfattribs={"layer": "DOOR"})
        elif entity.entity_type == "window":
            msp.add_blockref("WINDOW_BLOCK", tuple(geom.get("insert", (0, 0))), dxfattribs={"layer": "WIN"})
        elif entity.confidence < 0.45:
            msp.add_circle(tuple(geom.get("point", (0, 0))), 120, dxfattribs={"layer": "AI_LOWCONF"})

    for idx, warning in enumerate(graph.warnings + warnings):
        msp.add_text(warning[:80], dxfattribs={"layer": "QA_MARKUP", "height": 180}).set_placement((0, -idx * 250))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out)
    return out, warnings


def build_dxf_outputs(graph: EvidenceGraph, out_dir: str | Path) -> list[str]:
    out = Path(out_dir)
    warnings: list[str] = []
    _, center_warnings = build_centerline_dxf(graph, out / "result_centerline.dxf")
    _, solid_warnings = build_wallsolid_dxf(graph, out / "result_wallsolid.dxf")
    warnings.extend(center_warnings)
    warnings.extend(solid_warnings)
    return warnings

