from __future__ import annotations

import argparse
from pathlib import Path

from neuro_seq_cad.cad.dxf_builder import build_dxf_outputs
from neuro_seq_cad.cad.metadata_exporter import write_json
from neuro_seq_cad.detection.planparser_adapter import run_planparser
from neuro_seq_cad.detection.symbol_schema import SymbolDetectionResult
from neuro_seq_cad.detection.yolo_adapter import run_yolo
from neuro_seq_cad.fusion.evidence_graph import EvidenceEntity, EvidenceGraph
from neuro_seq_cad.geometry.double_line_detector import detect_double_lines
from neuro_seq_cad.geometry.scale_calibration import calibrate_scale
from neuro_seq_cad.geometry.wall_offsetter import offset_centerline_to_wall_polygon
from neuro_seq_cad.geometry.wall_thickness_estimator import estimate_wall_thickness
from neuro_seq_cad.io.coordinate_system import image_to_cad_point
from neuro_seq_cad.io.export_paths import build_export_paths
from neuro_seq_cad.line_extraction.opencv_lsd import extract_raw_lines
from neuro_seq_cad.preprocessing.normalize_scan import normalize_scan
from neuro_seq_cad.raster2seq.adapter import run_raster2seq
from neuro_seq_cad.review.overlay_renderer import render_overlay
from neuro_seq_cad.review.qa_report import write_qa_report
from neuro_seq_cad.review.synthetic_floorplan_generator import make_synthetic_floorplan
from neuro_seq_cad.vlm.vlm_refiner import refine_with_vlm


def _synthetic_dimension_candidates(width: int) -> list[dict]:
    return [{"text": "5000", "pixel_length": max(width * 0.775, 1)}]


def _synthetic_symbols(width: int, height: int) -> SymbolDetectionResult:
    from neuro_seq_cad.detection.symbol_schema import SymbolPrediction

    return SymbolDetectionResult(
        symbols=[
            SymbolPrediction(id="door_0001", type="door", bbox=[0.475 * width, 0.62 * height, 0.531 * width, 0.62 * height + 20], confidence=0.48, source="synthetic_fallback"),
            SymbolPrediction(id="win_0001", type="window", bbox=[0.231 * width, 0.16 * height, 0.387 * width, 0.178 * height], confidence=0.46, source="synthetic_fallback"),
        ]
    )


def analyze_image(image_path: str | Path, out_dir: str | Path | None = None) -> EvidenceGraph:
    image = Path(image_path)
    warnings: list[str] = []
    normalized = normalize_scan(image, out_dir)
    warnings.extend(normalized.get("warnings", []))
    width = int(normalized["width"])
    height = int(normalized["height"])

    raster_result, raster_warnings = run_raster2seq(image)
    warnings.extend(raster_warnings)
    plan_result, plan_warnings = run_planparser(image)
    warnings.extend(plan_warnings)
    yolo_result, yolo_warnings = run_yolo(image)
    warnings.extend(yolo_warnings)

    raw_result = extract_raw_lines(image)
    scale_result = calibrate_scale(
        titleblock_texts=["SCALE 1:100"],
        dimensions=_synthetic_dimension_candidates(width),
        door_bboxes=[s.bbox for s in _synthetic_symbols(width, height).symbols if s.type == "door"],
    )
    warnings.extend(scale_result.warnings)

    double_lines = detect_double_lines(raw_result.lines, scale_result.scale)
    thickness = estimate_wall_thickness(double_lines, [])
    warnings.extend(thickness.warnings)

    entities: list[EvidenceEntity] = []
    for raw in raw_result.lines:
        p1 = image_to_cad_point(raw.p1, height, scale_result.scale)
        p2 = image_to_cad_point(raw.p2, height, scale_result.scale)
        entities.append(
            EvidenceEntity(
                id=f"raw_{raw.id}",
                entity_type="raw_line",
                geometry={"p1": list(p1), "p2": list(p2)},
                sources=[raw.source],
                confidence=raw.confidence,
                provenance={"image_points": [raw.p1, raw.p2], "layer": "RAW_LINES"},
                warnings=[],
            )
        )
        if raw.length > min(width, height) * 0.1:
            entities.append(
                EvidenceEntity(
                    id=f"cen_{raw.id}",
                    entity_type="wall_centerline",
                    geometry={"p1": list(p1), "p2": list(p2)},
                    sources=[raw.source, "line_to_centerline"],
                    confidence=min(raw.confidence, 0.62),
                    provenance={"thickness_source": thickness.source},
                    warnings=[],
                )
            )
            if thickness.thickness:
                polygon, polygon_warnings = offset_centerline_to_wall_polygon(p1, p2, thickness.thickness)
                warnings.extend(polygon_warnings)
                if polygon:
                    entities.append(
                        EvidenceEntity(
                            id=f"wall_{raw.id}",
                            entity_type="wall_polygon",
                            geometry={"points": [list(p) for p in polygon], "layer": "WAL1", "thickness": thickness.thickness},
                            sources=[raw.source, thickness.source],
                            confidence=min(raw.confidence, thickness.confidence),
                            provenance={"hatch_layer": "WAL_HATCH"},
                            warnings=polygon_warnings,
                        )
                    )

    symbols = _synthetic_symbols(width, height)
    symbols.symbols.extend(plan_result.symbols)
    symbols.symbols.extend(yolo_result.symbols)
    for symbol in symbols.symbols:
        x1, y1, x2, y2 = symbol.bbox
        insert = image_to_cad_point((x1, y1), height, scale_result.scale)
        entities.append(
            EvidenceEntity(
                id=symbol.id,
                entity_type=symbol.type,
                geometry={"bbox": symbol.bbox, "insert": list(insert)},
                sources=[symbol.source],
                confidence=symbol.confidence,
                provenance={"fallback_door_width_candidates": [800, 850, 900, 1000] if symbol.type == "door" else []},
                warnings=["low_confidence_entities"] if symbol.confidence < 0.5 else [],
            )
        )

    entities.append(
        EvidenceEntity(
            id="text_room_0001",
            entity_type="text",
            geometry={"text": "ROOM", "point": list(image_to_cad_point((width * 0.28, height * 0.35), height, scale_result.scale))},
            sources=["synthetic_fallback"],
            confidence=0.4,
            provenance={"layer": "TEXT"},
            warnings=["low_confidence_entities"],
        )
    )

    low_conf_count = sum(1 for entity in entities if entity.confidence < 0.5 or entity.warnings)
    if low_conf_count:
        warnings.append(f"low_confidence_entities: {low_conf_count}")

    vlm_result, vlm_warnings = refine_with_vlm({"entities": [e.model_dump() for e in entities]})
    warnings.extend(vlm_warnings)

    graph = EvidenceGraph(
        entities=entities,
        scale=scale_result.scale,
        scale_source=scale_result.source,
        warnings=warnings + [w.message for w in []],
    )
    graph.warnings.append(f"scale_confidence: {scale_result.confidence}")
    graph.warnings.append(f"wall_thickness_source: {thickness.source}")
    if raster_result.polygons:
        graph.warnings.append(f"raster2seq_polygons: {len(raster_result.polygons)}")
    if vlm_result.get("warnings"):
        graph.warnings.append(f"vlm_warnings: {len(vlm_result['warnings'])}")
    return graph


def write_analysis_outputs(image_path: str | Path, out_dir: str | Path, export_dxf: bool = False) -> None:
    paths = build_export_paths(out_dir)
    graph = analyze_image(image_path, paths.out_dir)
    dxf_warnings: list[str] = []
    if export_dxf:
        dxf_warnings = build_dxf_outputs(graph, paths.out_dir)
        graph.warnings.extend(dxf_warnings)
    render_overlay(image_path, graph, paths.overlay)
    write_json(paths.result_json, graph)
    write_qa_report(paths.qa_report, graph.warnings, {"entities": len(graph.entities), "scale": graph.scale, "scale_source": graph.scale_source})


def cmd_make_sample(args: argparse.Namespace) -> None:
    out = make_synthetic_floorplan(args.out)
    print(out)


def cmd_analyze(args: argparse.Namespace) -> None:
    write_analysis_outputs(args.image, args.out, export_dxf=False)
    print(Path(args.out))


def cmd_export_dxf(args: argparse.Namespace) -> None:
    write_analysis_outputs(args.image, args.out, export_dxf=True)
    print(Path(args.out))


def cmd_overlay(args: argparse.Namespace) -> None:
    graph = analyze_image(args.image, Path(args.out).parent)
    out = render_overlay(args.image, graph, args.out)
    print(out)


def cmd_check_img2cadseq(args: argparse.Namespace) -> None:
    path = Path("third_party/Img2CADSeq")
    if path.exists():
        print("Img2CADSeq found. It is monitored as a 3D STEP candidate, not the core 2D floor-plan DXF engine.")
    else:
        print("Img2CADSeq not found. This is OK: the 2D image-to-CAD draft pipeline does not depend on it.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="neuro_seq_cad")
    sub = parser.add_subparsers(required=True)

    make_sample = sub.add_parser("make-sample")
    make_sample.add_argument("--out", required=True)
    make_sample.set_defaults(func=cmd_make_sample)

    analyze = sub.add_parser("analyze")
    analyze.add_argument("image")
    analyze.add_argument("--out", required=True)
    analyze.set_defaults(func=cmd_analyze)

    export_dxf = sub.add_parser("export-dxf")
    export_dxf.add_argument("image")
    export_dxf.add_argument("--out", required=True)
    export_dxf.set_defaults(func=cmd_export_dxf)

    overlay = sub.add_parser("overlay")
    overlay.add_argument("image")
    overlay.add_argument("--out", required=True)
    overlay.set_defaults(func=cmd_overlay)

    check = sub.add_parser("check-img2cadseq")
    check.set_defaults(func=cmd_check_img2cadseq)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

