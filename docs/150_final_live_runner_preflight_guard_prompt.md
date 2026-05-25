# HS-CAD Final Live Runner Preflight Guard Prompt

## Purpose
이번 PR의 목적은 Safety Spec Approval 이후 첫 구현 단계로, Final Live Runner의 "Preflight Guard"를 구현하는 것이다.

## Scope
- 실행 전 필요한 안전 조건을 모두 점검하는 Guard 구현
- preflight / refusal / audit intent만 생성
- SendCommand, SaveAs, XiCAD 실행 등 CAD 명령 실행은 일절 금지된다.

## Next Steps
- 다음 단계는 manual-copy-only interface PR 구현이다.
