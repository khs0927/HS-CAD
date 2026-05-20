# XiCAD 연동 전략

업로드된 XiCAD 패키지에는 ZWCAD 전용 구성 파일(`_ZWCad`), XiCAD 컴파일 LISP/ZELX/FAS(`Lisp`), 건축 라이브러리 DWG(`Lib`), 심볼/설정 폴더(`xiLib`, `DialogBox`)가 포함되어 있습니다.

## 결론

ZWCAD AI Modifier와 XiCAD는 연동 가능합니다. 단, XiCAD 내부 코드는 대부분 컴파일된 `fas/zelx/des` 형태이므로 내부 알고리즘을 직접 수정하기보다 다음 방식이 안전합니다.

1. AI Modifier가 도면을 스캔하고 레이어/블록/좌표를 정리합니다.
2. AI Modifier가 필요한 기준선, 바운더리, 그리드, 선택 후보를 준비합니다.
3. XiCAD 명령(`WAL`, `COL`, `D1`, `W1`, `PK` 등)을 ZWCAD 명령줄로 호출합니다.
4. XiCAD 대화형 명령은 사용자가 ZWCAD 화면에서 마무리합니다.
5. 실행 후 AI Modifier가 다시 도면을 스캔하여 변경 사항을 JSON/Excel 리포트로 저장합니다.

## 추천 연동 레벨

### Level 1: 명령 호출형

- `load_xicad`: XiCAD support path와 loader를 ZWCAD에 로드
- `run_xicad_command`: XiCAD 단축 명령을 실행
- 예: `WAL`, `COL`, `D1`, `W1`, `PK`

### Level 2: AI 전처리 + XiCAD 실행

- AI가 벽 레이어, 기둥 그리드, 바운더리 등을 생성/정리
- 이후 XiCAD 명령을 호출
- 실행 후 결과를 다시 분석

### Level 3: XiCAD 라이브러리 활용

- `Lib` 폴더의 DWG 블록을 AI가 직접 삽입
- 문/창/가구/설비 블록을 수량화
- XiCAD 명령 없이도 일부 자동 배치 가능

## 주요 XiCAD 건축 명령 후보

- `WAL`: 벽 그리기
- `COL`: 기둥 그리기
- `CLI`: 기둥 일람표
- `BLI`: 보 일람표
- `BLS`: 보 스케줄
- `D1`, `D2`, `D3`: 문 그리기
- `W1`, `W2`, `W3`: 창 그리기
- `WO`: 개구부 그리기
- `PK`: 주차장 그리기
- `STP`, `STC`: 계단 평면/입면
- `INS`: 단열재
- `ELV`: 엘리베이터

## CLI 예시

```bash
python -m src.main xicad-catalog --shortkey "C:/xicad/Lisp/xiShortkey_origin.key"
python -m src.main load-xicad --dwg "C:/cad/sample.dwg" --xicad-root "C:/xicad"
python -m src.main run-xicad --dwg "C:/cad/sample.dwg" --xicad-root "C:/xicad" --load-first --alias WAL
python -m src.main run-command --dwg "C:/cad/sample.dwg" --command "examples/commands/run_xicad_wall.json" --dry-run
```

## 주의

XiCAD 명령 다수는 대화형입니다. 따라서 완전 무인 자동화보다, AI가 전처리/검증/리포트를 담당하고 XiCAD가 건축 전용 작도 명령을 담당하는 하이브리드 방식이 현실적입니다.
