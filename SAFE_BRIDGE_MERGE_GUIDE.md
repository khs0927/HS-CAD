# XiCAD Safe Bridge 병합 가이드

Codex가 `src/adapters/xicad_adapter.py`, `src/integrations/xicad_*`, `src/app/cli.py`를 수정 중이라면, 이 add-on은 바로 덮어쓰지 마세요.

## 1. 복사할 파일

다음 폴더를 프로젝트 루트에 그대로 복사합니다.

```text
src/extensions/xicad_safe_bridge/
tests/test_xicad_safe_bridge.py
docs/08_xicad_safe_bridge.md
examples/commands/xicad_safe_*.json
```

## 2. 즉시 실행 가능한 테스트

```powershell
python -m pytest tests/test_xicad_safe_bridge.py
```

이 테스트는 실제 ZWCAD와 XiCAD가 없어도 통과해야 합니다.

## 3. 기존 CLI에 연결하는 방법

Codex 작업이 끝난 뒤 `src/app/cli.py`에 별도 명령을 추가합니다.

권장 명령 이름:

```text
xicad-safe-plan
xicad-safe-run
```

기존 `run-xicad`와 충돌하지 않도록 이름을 다르게 둡니다.

## 4. 기존 command parser에 연결하는 방법

기존 `run_xicad`, `run_xicad_workflow` 명령과 충돌하지 않게 다음 새 명령만 추가합니다.

```text
xicad_safe_plan
xicad_safe_execute
```

## 5. 실제 실행 연결 지점

`XicadSafeExecutor`는 adapter-like 객체를 받습니다.

필요 메서드:

```python
run_command(command_text: str) -> None
load_lisp(path: str) -> None
```

기존 `ZWCADCOMAdapter`가 `run_command()`를 지원하면 그대로 연결할 수 있습니다.

## 6. 충돌 방지 규칙

- 기존 파일 덮어쓰기 금지
- 기존 command 이름 재사용 금지
- 기존 config 파일 직접 수정 금지
- 기존 XiCAD adapter와 독립된 add-on으로 먼저 테스트
- 병합은 테스트 후 수동으로 진행
