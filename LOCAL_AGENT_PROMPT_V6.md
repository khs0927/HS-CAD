너는 HS-CAD v6 stacked branch를 검증하는 로컬 코딩 에이전트다.

현재 원격 브랜치:
- base: feature/main-code-pipeline-overlay
- new branch: feature/evidence-bridge-schema-golden

목표:
1. schema-aware legacy artifact bridge를 검증한다.
2. runtime JSON fixture만 사용한다.
3. CAD 실행 없이 evidence bridge만 확인한다.

검증 명령:

```powershell
python -X utf8 -m pytest -q tests/test_legacy_artifact_schema_v6.py
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

선택 검증:

```powershell
python -X utf8 scripts\inspect_legacy_artifact_schema.py --legacy-dir outputs\main_code_v2_smoke --out outputs\schema_report_v6.json
```

주의:
- outputs/** 커밋 금지
- _incoming/** 커밋 금지
- *.zip, *.dwg, runtime *.dxf, *.sqlite3 커밋 금지
- CAD/ZWCAD COM/SendCommand/XiCAD alias/original DWG mutation 금지
