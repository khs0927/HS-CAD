# xiCAD Headless Core Batch 6

대상: `M2`, `INA`, `LIS`, `LMA`, `LNA`, `QD`, `SPN`, `NUMC`, `TIC`, `TIE`, `TII`, `TIN`.

FAS4 문자열·DCL·진입점 증거를 이용해 대화상자의 선택값을 Pydantic 구조화 입력으로 옮겼습니다. MCP Tool은 실행계획만 반환하며 CAD를 직접 수정하지 않습니다.

## 핵심 원칙

- 숫자·문자·곡선·점 입력을 Handle 또는 정규화 Snapshot으로 전달합니다.
- 이동/복사, 앞/뒤, 진법, 정렬순서, 단위, 반올림, 출력 방식 등 모호한 선택은 반드시 명시합니다.
- Dry-run이 기본입니다.
- 실제 변경 요청에는 승인 Fingerprint가 필요합니다.
- Xref와 잠긴 레이어는 변경 대상에서 거부합니다.
- Windows/ZWCAD 동등성 검증 전에는 Production Live로 승격하지 않습니다.
