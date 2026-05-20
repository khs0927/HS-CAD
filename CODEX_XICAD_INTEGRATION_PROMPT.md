# Codex Prompt: XiCAD Integration Upgrade

너는 Windows + ZWCAD + XiCAD 환경의 CAD 자동화 개발자다. 현재 프로젝트는 ZWCAD AI Architectural Modifier이며, 업로드된 XiCAD 패키지와 연동하는 코드를 추가해야 한다.

목표:
- XiCAD 설치 경로를 입력받아 support path를 ZWCAD에 추가한다.
- XiCAD loader(`Lisp/xi.zelx`, `Lisp/xi.fas`, `_ZWCad/zwcad.lsp`)를 안전하게 로드한다.
- `xiShortkey_origin.key`를 파싱해 XiCAD 명령 카탈로그를 만든다.
- `WAL`, `COL`, `D1`, `D2`, `W1`, `W2`, `WO`, `PK`, `STP`, `STC` 등 건축 명령을 AI JSON 명령으로 호출한다.
- 대부분의 XiCAD 명령은 대화형이므로, AI는 전처리/선택/검증/리포트만 담당하고 XiCAD 명령은 ZWCAD 명령줄에 큐잉한다.

구현해야 할 파일:
- src/adapters/xicad_adapter.py
- src/integrations/xicad_command_catalog.py
- src/integrations/xicad_workflows.py
- config/xicad_profile.yaml
- config/xicad_commands.yaml
- docs/06_xicad_integration.md
- examples/commands/load_xicad.json
- examples/commands/run_xicad_wall.json
- examples/commands/xicad_workflow_column.json

CLI 추가:
- xicad-catalog --shortkey PATH
- load-xicad --dwg PATH --xicad-root PATH
- run-xicad --dwg PATH --alias WAL --xicad-root PATH --load-first

run-command JSON 명령 추가:
- load_xicad
- run_xicad_command
- xicad_workflow

안전 규칙:
- 기본은 dry-run이다.
- XiCAD 명령 실행 전 백업을 만든다.
- interactive 명령은 사용자에게 ZWCAD 화면에서 후속 입력이 필요하다는 것을 명확히 출력한다.
- XiCAD 내부 fas/zelx/des 파일은 수정하지 않는다.
- XiCAD command alias 목록은 key 파일에서 파싱한다.

테스트:
- Pytest는 CAD 없이도 통과해야 한다.
- xicad_command_catalog parser 테스트를 추가한다.
- CLI help가 깨지지 않아야 한다.
