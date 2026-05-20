# Codex 추가 작업 프롬프트: XiCAD Safe Bridge 병합

현재 Codex가 XiCAD 연동 핵심 파일을 작업 중이라면, 이 add-on은 충돌 방지를 위해 `src/extensions/xicad_safe_bridge/`에 격리되어 있다.

## 해야 할 일

1. 이 add-on을 프로젝트에 복사한다.
2. `python -m pytest tests/test_xicad_safe_bridge.py`를 실행한다.
3. 기존 테스트와 함께 전체 테스트를 실행한다.
4. 기존 CLI가 안정화된 뒤에만 다음 명령을 추가한다.

```text
python -m src.main xicad-safe-plan --command examples/commands/xicad_safe_wall_plan.json
python -m src.main xicad-safe-run --dwg C:/cad/sample.dwg --command examples/commands/xicad_safe_wall_plan.json --execute
```

## 기존 파일과 연결할 위치

- `src/app/cli.py`: 새 CLI 명령 추가
- `src/ai/command_parser.py`: xicad_safe_plan, xicad_safe_execute 명령 추가
- `src/adapters/zwcad_com_adapter.py`: run_command(command_text) 메서드 확인
- `docs/06_xicad_integration.md`: Safe Bridge 섹션 링크 추가

## 절대 하지 말 것

- 기존 XiCAD adapter를 덮어쓰지 말 것
- 기존 run_xicad 명령 이름을 바꾸지 말 것
- vendor/xicad 원본 파일을 수정하지 말 것
