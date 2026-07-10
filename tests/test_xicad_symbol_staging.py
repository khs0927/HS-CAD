from __future__ import annotations

import json
from pathlib import Path

import ezdxf

from src.integrations.xicad_symbol_staging import (
    analyze_xicad_symbol_system,
    build_master_symbol_review_table,
    build_xicad_symbol_staging,
    classify_symbol,
    configure_xicad_block_library_default,
    discover_cad_sources,
    export_all_drawing_blocks_to_xicad,
    export_dxf_block_symbols,
    extract_dxf_block_features,
    mirror_hscad_library_to_xicad_native_folders,
    parse_xicad_block_layer_config,
    sanitize_symbol_filename,
)


def test_sanitize_symbol_filename_removes_windows_invalid_chars():
    assert sanitize_symbol_filename('A/B:C*D?"') == "A_B_C_D__"


def test_classify_symbol_uses_name_rules():
    category, confidence, reason = classify_symbol("ZIUM_sheet_architect")
    assert category == "title_sheet"
    assert confidence > 0.9
    assert reason == ["title/name"]


def test_classify_symbol_does_not_treat_embedded_d_as_door():
    category, confidence, reason = classify_symbol("HEADED_HT_BOLT-HEAD-M20")
    assert category == "structure"
    assert confidence == 0.78
    assert reason == ["structure/name"]


def test_extract_dxf_block_features_and_shape_classification(tmp_path: Path):
    dxf = tmp_path / "sample.dxf"
    doc = ezdxf.new()
    block = doc.blocks.new(name="CUSTOM_DOOR_ARC")
    block.add_line((0, 0), (900, 0))
    block.add_arc((0, 0), radius=900, start_angle=0, end_angle=90)
    doc.saveas(dxf)

    features = extract_dxf_block_features([dxf])
    assert "CUSTOM_DOOR_ARC" in features
    assert features["CUSTOM_DOOR_ARC"].has_arc is True
    assert features["CUSTOM_DOOR_ARC"].entity_counts["LINE"] == 1


def test_build_xicad_symbol_staging_from_report(tmp_path: Path):
    report = tmp_path / "fast_scan_report.json"
    report.write_text(
        json.dumps({"user_blocks_observed": ["ZIUM LOGO", "A$C123", "CCTV"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    xicad_root = tmp_path / "xicad"
    (xicad_root / "xiLib").mkdir(parents=True)

    payload = build_xicad_symbol_staging(
        observed_report=report,
        xicad_root=xicad_root,
        out_dir=tmp_path / "staging",
        copy_matches=True,
    )

    assert payload["counts"]["total"] == 3
    assert payload["counts"]["by_category"]["brand"] == 1
    assert payload["counts"]["by_category"]["review_only"] == 1
    assert (tmp_path / "staging" / "hs_cad_symbol_catalog.json").exists()


def test_export_dxf_block_symbols(tmp_path: Path):
    dxf = tmp_path / "source.dxf"
    doc = ezdxf.new()
    block = doc.blocks.new(name="CCTV")
    block.add_circle((0, 0), radius=100)
    doc.saveas(dxf)

    report = tmp_path / "fast_scan_report.json"
    report.write_text(json.dumps({"user_blocks_observed": ["CCTV"]}, ensure_ascii=False), encoding="utf-8")
    catalog_payload = build_xicad_symbol_staging(
        observed_report=report,
        xicad_root=tmp_path / "xicad",
        out_dir=tmp_path / "staging",
        dxf_sources=[dxf],
    )

    payload = export_dxf_block_symbols(
        dxf_sources=[dxf],
        catalog_path=tmp_path / "staging" / "hs_cad_symbol_catalog.json",
        out_dir=tmp_path / "exported",
    )

    assert catalog_payload["counts"]["by_category"]["security"] == 1
    assert payload["exported_count"] == 1
    assert (tmp_path / "exported" / "security" / "CCTV.dxf").exists()


def test_parse_xicad_block_layer_config(tmp_path: Path):
    cfg = tmp_path / "xiBlkLayerSet.cfg"
    cfg.write_text("FURN;FURN;HIDDEN;9;가구\nETC;SYM;Continuous;4;기타\n", encoding="utf-8")
    rows = parse_xicad_block_layer_config(cfg)
    assert rows[0]["key"] == "FURN"
    assert rows[0]["layer"] == "FURN"
    assert rows[0]["color"] == 9


def test_analyze_xicad_symbol_system_minimal(tmp_path: Path):
    root = tmp_path / "xicad"
    xilib = root / "xiLib"
    lib = root / "Lib"
    xilib.mkdir(parents=True)
    lib.mkdir()
    (xilib / "xiBlkLayerSet.cfg").write_text("ETC;SYM;Continuous;4;기타\n", encoding="utf-8")
    (xilib / "xiConfig.cfg").write_text("/xiBlkLibrary\nC:\\xicad\\xiLib|<MAINPATH>\\_동적블럭_기타|1|0\n", encoding="utf-8")
    (xilib / "sample.dwg").write_text("placeholder", encoding="utf-8")

    payload = analyze_xicad_symbol_system(root, tmp_path / "analysis.json")
    assert payload["totals"]["xiLib_dwg"] == 1
    assert payload["symbol_layer_rules_cfg"][0]["key"] == "ETC"
    assert (tmp_path / "analysis.md").exists()


def test_discover_cad_sources_excludes_generated_staging(tmp_path: Path):
    keep = tmp_path / "scratch" / "a.dxf"
    skip = tmp_path / "generated" / "xicad_symbols_staging" / "b.dxf"
    keep.parent.mkdir(parents=True)
    skip.parent.mkdir(parents=True)
    keep.write_text("0\nEOF\n", encoding="utf-8")
    skip.write_text("0\nEOF\n", encoding="utf-8")

    sources = discover_cad_sources([tmp_path])
    assert keep in sources
    assert skip not in sources


def test_export_all_drawing_blocks_to_xicad_without_install(tmp_path: Path):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    dxf = source_dir / "source.dxf"
    doc = ezdxf.new()
    block = doc.blocks.new(name="TOIPD02")
    block.add_circle((0, 0), radius=100)
    doc.saveas(dxf)

    payload = export_all_drawing_blocks_to_xicad(
        roots=[source_dir],
        xicad_root=tmp_path / "xicad",
        out_dir=tmp_path / "out",
        install=False,
    )

    assert payload["catalog"]["counts"]["total"] == 1
    assert payload["export"]["exported_count"] == 1


def test_configure_xicad_block_library_default(tmp_path: Path):
    root = tmp_path / "xicad"
    xilib = root / "xiLib"
    xilib.mkdir(parents=True)
    cfg = xilib / "xiConfig.cfg"
    cfg.write_text("/xiBlkLibrary\nC:\\xicad\\xiLib|<MAINPATH>\\_동적블럭_기타|1|0\n", encoding="cp949")

    payload = configure_xicad_block_library_default(root, r"<MAINPATH>\심볼\HS-CAD-XICAD")

    assert payload["changed"] is True
    assert Path(payload["backup"]).exists()
    assert r"<MAINPATH>\심볼\HS-CAD-XICAD" in cfg.read_text(encoding="cp949")


def test_mirror_hscad_library_to_xicad_native_folders(tmp_path: Path):
    root = tmp_path / "xicad"
    source = root / "xiLib" / "심볼" / "HS-CAD-ALL" / "sanitary"
    source.mkdir(parents=True)
    (source / "TOIPD02.dwg").write_text("placeholder", encoding="utf-8")

    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": "TOIPD02",
                        "sanitized_name": "TOIPD02",
                        "category": "sanitary",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    analysis = tmp_path / "analysis.json"
    analysis.write_text(
        json.dumps({"category_mapping": {"sanitary": {"xicad_key": "FIX", "layer": "FIX"}}}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = mirror_hscad_library_to_xicad_native_folders(
        xicad_root=root,
        catalog_path=catalog,
        analysis_path=analysis,
        out_path=tmp_path / "mirror.json",
    )

    assert payload["copied_count"] == 1
    assert (root / "xiLib" / "심볼" / "HS-CAD-XICAD" / "FIX_FIX" / "TOIPD02.dwg").exists()


def test_build_master_symbol_review_table(tmp_path: Path):
    root = tmp_path / "xicad"
    symbol = root / "xiLib" / "심볼" / "HS-CAD-ALL" / "sanitary"
    symbol.mkdir(parents=True)
    (symbol / "TOIPD02.dwg").write_text("placeholder", encoding="utf-8")

    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "name": "TOIPD02",
                        "sanitized_name": "TOIPD02",
                        "category": "sanitary",
                        "confidence": 0.86,
                        "reason": ["sanitary/name"],
                        "source_status": "from_drawing_definition",
                        "source_path": "source.dxf",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    validation = tmp_path / "validation.json"
    validation.write_text(
        json.dumps({"rows": [{"file": "TOIPD02.dwg", "status": "inserted", "effective_name": "TOIPD02"}]}),
        encoding="utf-8",
    )

    payload = build_master_symbol_review_table(
        xicad_root=root,
        libraries=("HS-CAD-ALL",),
        catalog_path=catalog,
        validation_reports={"HS-CAD-ALL": validation},
        out_dir=tmp_path / "out",
    )

    assert payload["rows"] == 1
    assert Path(payload["csv"]).exists()
    assert "TOIPD02" in Path(payload["markdown"]).read_text(encoding="utf-8")
