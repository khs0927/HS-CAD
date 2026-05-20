# Upgrade Roadmap: ZWCAD AI Modifier + XiCAD

## 1단계: 안전한 하이브리드 자동화

- AI Modifier가 도면을 분석한다.
- AI Modifier가 레이어/기준선/바운더리/그리드를 준비한다.
- XiCAD 명령은 사용자가 검증 가능한 interactive 명령으로 호출한다.
- 실행 후 AI Modifier가 다시 스캔하여 변경 결과를 리포트한다.

## 2단계: XiCAD 명령별 프리셋 자동화

- WAL, COL, D1, W1, PK 같은 명령별로 사전 조건을 정의한다.
- 예: WAL 실행 전 A-WALL, A-GRID, A-BOUNDARY 상태 점검.
- 예: COL 실행 전 기둥 삽입점 후보 JSON 생성.

## 3단계: XiCAD 라이브러리 직접 활용

- vendor/xicad/Lib, vendor/xicad/xiLib 내부 DWG 블록을 카탈로그화한다.
- AI가 블록 후보를 추천하고 ZWCAD COM/PyRx로 직접 삽입한다.
- XiCAD 명령 호출과 직접 블록 삽입을 병행한다.

## 4단계: ZWCAD 내부 Add-in화

- Python CLI → ZWCAD .NET/ZRX Add-in UI로 확장한다.
- 버튼: 도면 분석, XiCAD 로드, AI 명령, 결과 리포트.

## 5단계: 건축 검토 자동화

- 문/창호/기둥/보/실명/면적/주차/계단 객체를 표준화한다.
- 객체 수량, 누락, 레이어 오류, 텍스트 오류를 리포트한다.
