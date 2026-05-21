import pathlib


def test_readme_safety_rules():
    readme_path = pathlib.Path(__file__).resolve().parents[1] / "README.md"
    content = readme_path.read_text(encoding="utf-8")

    assert "기존 사무소 DWG를 편집할 때는 샘플링한 주변 레이어와 시각 문법을 우선 사용합니다." in content
    assert "사용자가 명시적으로 요청하지 않는 한 기존 레이어를 리맵하지 않습니다." in content
    assert "명시적 생성 레이어는 독립 생성 도면 또는 검수 격리 워크플로우에서만 사용합니다." in content
    assert "Keep generated layers explicit" not in content
