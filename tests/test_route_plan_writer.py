from pathlib import Path

from src.orchestrator.route_plan_writer import RoutePlanWriter
from src.orchestrator.task_router import TaskRouter


def test_route_plan_writer_outputs_review_files(tmp_path: Path):
    route = TaskRouter().route('도면을 분석해줘', tmp_path / 'sample.dwg', workspace=tmp_path / 'workspace')
    paths = RoutePlanWriter(tmp_path / 'plan').write(route)
    assert Path(paths['json']).exists()
    assert Path(paths['markdown']).exists()
    assert Path(paths['powershell']).exists()
    assert 'zwcad_saveas_dxf_ezdxf' in Path(paths['json']).read_text(encoding='utf-8')
    assert 'python -X utf8 -m src.main corpus-run prepare' in Path(paths['powershell']).read_text(encoding='utf-8-sig')
