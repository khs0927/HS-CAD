# XiCAD Safe Bridge Add-on

이 폴더는 `zwcad-ai-modifier` 본체와 XiCAD 연동 작업이 동시에 진행될 때 충돌을 줄이기 위한 **안전한 확장 레이어**입니다.

## 설계 원칙

- 기존 `src/app/cli.py`, `src/ai/command_parser.py`, `src/adapters/xicad_adapter.py` 등을 직접 덮어쓰지 않습니다.
- 새 코드는 `src/extensions/xicad_safe_bridge/` 아래에만 추가합니다.
- 기존 프로젝트에 병합할 때는 `MERGE_GUIDE.md` 순서대로 수동 연결합니다.
- Codex가 작업 중인 XiCAD 연동부와 중복되지 않도록, 이 add-on은 다음 역할만 담당합니다.

## 담당 역할

1. XiCAD alias를 안전하게 검증하는 registry
2. AI JSON 명령과 XiCAD 실행 계획을 분리하는 bridge command 모델
3. ZWCAD COM adapter가 없어도 테스트 가능한 dry-run executor
4. 실제 ZWCAD 실행 전 preview plan 생성
5. XiCAD 대화형 명령과 자동 명령을 구분
6. 충돌 방지를 위한 namespace 분리

## 추천 병합 순서

1. 이 add-on 폴더를 프로젝트 루트에 복사
2. `src/extensions/xicad_safe_bridge/`를 그대로 추가
3. `tests/test_xicad_safe_bridge.py`를 추가
4. pytest 실행
5. 기존 CLI에 연결은 마지막에 진행
