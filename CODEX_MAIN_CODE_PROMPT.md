너는 HS-CAD 프로젝트의 main-code pipeline을 구현하는 코딩 에이전트다.

이번 overlay는 다음 내용을 추가한다.

- fileizers: DXF parsing, DWG→DXF boundary, PDF/Image adapter boundary
- analyzers: layer/text/area/spatial composite analysis
- evidence fusion: FUSION_MATRIX.json, CROSS_VALIDATION.json
- domain rules: architectural/structural/fire/energy/XiCAD plan-only rules
- CAD outputs: review-only result_centerline.dxf, result_wallsolid.dxf, qa_overlay.dxf
- indexing: SQLite evidence/entity store
- reports: FINAL_REPORT.md writer
- pipeline: hscad.pipelines.main_code_pipeline

중요 원칙:

1. PR #58 safety/process 변경과 섞지 않는다.
2. CAD live runner는 구현하지 않는다.
3. SendCommand/ZWCAD COM/XiCAD alias/original DWG mutation은 모두 금지한다.
4. 기존 src.main CLI에는 바로 연결하지 말고, 별도 CLI smoke가 통과한 뒤 후속 PR에서 연결한다.
5. outputs, _incoming, zip, dwg, cache 파일은 커밋하지 않는다.
6. 전체 테스트가 깨지면 새 코드를 격리하고 보고한다.

검증 명령:

```powershell
python -X utf8 -m pytest -q tests/test_main_code_overlay_contracts.py tests/test_main_code_pipeline_smoke.py
python -X utf8 -m hscad.pipelines.main_code_pipeline --input tests/fixtures/minimal_floorplan.dxf --out outputs/main_code_smoke
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

완료 보고에는 적용 파일, 테스트 결과, 생성 산출물, safety 확인, 커밋 제외 확인, 후속 PR 제안을 포함한다.
