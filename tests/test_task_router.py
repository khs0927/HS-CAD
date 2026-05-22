from pathlib import Path

from src.orchestrator.task_router import TaskRouter


def test_task_router_routes_dwg_to_dxf_pipeline(tmp_path: Path):
    route = TaskRouter().route('도면을 분석해줘', tmp_path / 'sample.dwg')
    assert route.intent == 'dwg_index'
    assert route.pipeline == 'dwg_bulk_index'
    assert route.tools[0].name == 'DWG SaveAs DXF fileizer'
    assert any('SaveAs DXF' in item for item in route.warnings)


def test_task_router_routes_pdf_to_pdf_pipeline(tmp_path: Path):
    route = TaskRouter().route('PDF에서 치수와 문자를 뽑아줘', tmp_path / 'sample.pdf')
    assert route.intent == 'pdf_extract'
    assert route.pipeline == 'pdf_index'
    assert route.tools[0].name == 'PyMuPDF'


def test_task_router_routes_image_to_vision_pipeline(tmp_path: Path):
    route = TaskRouter().route('이미지를 도면화해줘', tmp_path / 'scan.png')
    assert route.intent == 'image_to_cad'
    assert route.pipeline == 'image_analysis'


def test_task_router_routes_ifc_to_bim_pipeline(tmp_path: Path):
    route = TaskRouter().route('IFC 물량 산출해줘', tmp_path / 'model.ifc')
    assert route.intent == 'bim_extract'
    assert route.pipeline == 'ifc_bim'
