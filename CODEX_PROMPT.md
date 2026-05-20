# Codex 작업 프롬프트

너는 Windows + ZWCAD 2025–2027 환경에서 동작하는 CAD 자동화 개발자다. 이 저장소는 ZWCAD AI Architectural Modifier의 MVP이다.

## 핵심 목표

1. PyRx/cad-pyrx를 메인 Adapter로 완성한다.
2. 현재 COM fallback Adapter는 유지하고, 실제 ZWCAD에서 DWG 열기/스캔/수정/저장을 검증한다.
3. AI는 Python 코드를 직접 실행하지 않고 JSON 명령만 생성한다.
4. 모든 수정 명령은 백업과 dry-run을 거친다.

## 우선 작업

- `src/adapters/pyrx_adapter.py`에 실제 cad-pyrx/ZRX API 연동 구현
- `src/adapters/zwcad_com_adapter.py`를 실제 ZWCAD에서 검증
- `replace_block` 실행 기능 구현
- `create_boundary`, `create_grid`, `place_columns` planned action을 실제 CAD 생성 명령으로 구현
- `delete_layer_objects`는 강한 안전장치와 함께 구현
- ZWCAD 내부 LISP 로딩 및 SendCommand 안정화
- 수정 전후 diff report를 파일로 저장
- README에 실제 ZWCAD 테스트 결과 추가

## 실행 예

```bash
pip install -r requirements.txt
python -m src.main scan --dwg "C:/cad/sample.dwg" --out "outputs/objects.json"
python -m src.main run-command --dwg "C:/cad/sample_copy.dwg" --command "examples/commands/move_layer.json" --dry-run
python -m src.main run-command --dwg "C:/cad/sample_copy.dwg" --command "examples/commands/move_layer.json" --execute --save-as "C:/cad/sample_modified.dwg"
```

## 안전 원칙

- 실제 DWG 수정 전 원본 백업 필수
- AI 출력은 `src/ai/command_parser.py`의 Pydantic 모델을 통과해야 함
- 허용되지 않은 명령은 절대 실행하지 않음
- CAD 연결 실패 시 명확한 오류 메시지 출력
