# XiCAD Safe Bridge 설계 문서

## 목적

XiCAD는 강력한 건축 전용 ZWCAD 확장 도구지만, 많은 명령이 대화형 입력을 요구합니다.  
따라서 AI가 XiCAD 명령을 즉시 실행하면 위험합니다.

이 Safe Bridge는 다음을 보장합니다.

```text
AI 자연어
→ 허용된 JSON 명령
→ alias registry 검증
→ dry-run plan 생성
→ 대화형 여부 표시
→ 사용자가 확인한 뒤 실행
```

## 핵심 객체

### XicadAlias

XiCAD 명령 alias 정보입니다.

- alias
- name
- category
- interactive_required
- risk
- description

### XicadSafeCommand

AI가 생성하는 안전 명령입니다.

- command: xicad_safe_plan 또는 xicad_safe_execute
- alias
- load_first
- dry_run
- allow_interactive
- safety

### XicadExecutionPlan

실행 전 출력되는 계획입니다.

- steps
- warnings
- commands_to_send
- interactive_required
- can_execute

## 위험도 기준

| risk | 의미 |
|---|---|
| low | 분석/조회/보조 명령 |
| medium | 도면 객체 생성 가능 |
| high | 삭제/대량 변경/도면 구조 변경 가능 |

## 실행 정책

- dry_run 기본값 true
- high risk 명령은 allow_high_risk 없으면 실행 금지
- interactive_required 명령은 allow_interactive 없으면 실행 금지
- registry에 없는 alias는 실행 금지
