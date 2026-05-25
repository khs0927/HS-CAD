# 적용 지침

## 1. 가장 안전한 적용 순서

1. 현재 브랜치 확인

```bash
git status --short
git switch -c feature/next-stage-overlay
```

2. zip 압축 해제

```bash
mkdir -p _incoming/next_stage_overlay
# zip을 _incoming/next_stage_overlay 에 압축 해제
```

3. dry-run

```bash
python _incoming/next_stage_overlay/scripts/apply_hscad_overlay.py --overlay _incoming/next_stage_overlay --repo-root . --dry-run
```

4. 실제 적용

```bash
python _incoming/next_stage_overlay/scripts/apply_hscad_overlay.py --overlay _incoming/next_stage_overlay --repo-root .
```

5. 검증

```bash
python -X utf8 -m pytest -q tests/test_next_stage_overlay_contracts.py tests/test_next_stage_pipeline_smoke.py
python -X utf8 -m hscad.pipelines.next_stage_pipeline --input tests/fixtures/minimal_floorplan.dxf --out outputs/next_stage_smoke
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m pytest -q
```

## 2. 기존 PR55 파일과 충돌할 때

이미 아래 파일이 있다면 바로 덮어쓰기보다 diff를 먼저 보세요.

```text
src/hscad/core/evidence.py
src/hscad/fusion/evidence_fusion.py
src/hscad/cad/layer_schema.py
src/hscad/cad/dxf_builders.py
src/hscad/domain_rules/base.py
```

충돌 시 원칙:

- 기존 테스트를 깨지 않는 쪽 우선
- safety flag는 false 유지
- live CAD execution 추가 금지
- 기존 `src/fileizers`는 당장 삭제하지 않음
- 신규 `src/hscad/fileizers`를 adapter로 연결

## 3. 후속 PR 분리 권장

- PR-A: overlay 적용 + tests 통과
- PR-B: 기존 analyzer outputs를 Evidence 모델로 연결
- PR-C: fusion output을 기존 FINAL_REPORT.md 생성기에 연결
- PR-D: DXF builder를 실제 ezdxf writer로 확장
- PR-E: domain rules를 건축/소방/에너지 실무 룰로 확장
