# HS-CAD Next Stage Overlay Patch

이 zip은 기존 PR55 결과물을 직접 알 수 없는 상태에서, HS-CAD 저장소 루트에 안전하게 겹쳐 적용할 수 있도록 만든 **overlay patch package**입니다.

핵심 목표는 다음 단계 기능을 한 번에 추가하는 것입니다.

1. `src/hscad` 계층의 fileizer, evidence, fusion, domain-rule, CAD builder를 실제 실행 가능한 형태로 강화
2. `ezdxf`가 있으면 실제 DXF를 쓰고, 없으면 최소 ASCII DXF fallback으로 테스트가 통과되게 구성
3. DWG는 기본 COM scan이 아니라 ODA File Converter 또는 외부 CAD 변환 경로를 계획하고, 실패 시 evidence error를 남김
4. Domain rule engine은 CAD 명령 실행 없이 `plan-only` 결과만 생성
5. `python -m hscad.pipelines.next_stage_pipeline ...`로 smoke 실행 가능

## 적용 방법

저장소 루트에서:

```bash
python scripts/apply_hscad_overlay.py --overlay <압축해제한_폴더> --repo-root . --dry-run
python scripts/apply_hscad_overlay.py --overlay <압축해제한_폴더> --repo-root .
```

또는 zip 내부의 `src/`, `tests/`, `scripts/`, `docs/`를 저장소 루트에 복사하면 됩니다.

## 권장 검증

```bash
python -X utf8 -m pytest -q tests/test_next_stage_overlay_contracts.py tests/test_next_stage_pipeline_smoke.py
python -X utf8 -m hscad.pipelines.next_stage_pipeline --input tests/fixtures/minimal_floorplan.dxf --out outputs/next_stage_smoke
python -X utf8 -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m pytest -q
```

## 주의

- 이 패치는 CAD live execution을 구현하지 않습니다.
- ZWCAD COM, SendCommand, XiCAD alias 실행은 없습니다.
- DXF builder는 실제 파일을 생성하지만, 자동 수정 명령 실행은 하지 않습니다.
- 기존 저장소에 동일 파일이 있으면 백업 후 병합하거나 diff를 확인하세요.
