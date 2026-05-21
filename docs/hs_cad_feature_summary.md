# HS-CAD (ZWCAD AI Architectural Modifier) 종합 기능 요약 보고서 (보완본)

**HS-CAD 프로젝트**는 **Windows + ZWCAD 환경**에서 AI를 활용하여 기존 DWG 도면을 분석·검증하고, 안전하게 제어·수정하며, 서드파티 건축 리습(XiCAD) 및 특정 사무소의 도면 문법을 결합하여 도면 작성을 자동화하는 **지능형 CAD 제어 및 설계 자동화 프레임워크**입니다.

---

## 1. ZWCAD 도면 고속 스캔 및 데이터 추출 (Extraction & Scan)
도면 내의 다양한 기하학적 요소와 메타데이터를 ZWCAD와 실시간 연동하여 구조화된 JSON 데이터로 고속 추출합니다.

* **ActiveX/COM API 기반 스캔**: ZWCAD와 직접 통신하여 활성화된 도면의 ModelSpace 내부 데이터를 완전 스캔합니다.
* **추출 대상 객체**: `LINE`, `LWPOLYLINE` (폴리라인), `TEXT/MTEXT` (주석 및 문자), `INSERT` (블록 참조), `CIRCLE` (원), `ARC` (호), `DIMENSION` (치수) 등의 핵심 속성과 좌표 정보 추출.
* **건축 도면 분석 및 품질 검사 (`analyze-architecture`)**:
  - 레이어별 개체 수 집계 및 블록별 수량 분석.
  - 룸 텍스트(Room Text) 추출을 통한 공간 네이밍 분석.
  - 닫힌 폴리라인(Closed Polyline)의 면적 및 경계 무결성 오딧(Audit).
  - 전체 도면 아키텍처 상태를 종합적으로 리포팅하여 도면 품질 검증.

---

## 2. 안전한 도면 수정 및 설계 자동화 (Safe Execution & Generative Actions)
인공지능이 도면을 직접 파괴적으로 수정하지 않도록, 안전 장치가 적용된 **허용 명령 방식(Permitted Command Framework)**으로 도면을 편집합니다.

* **수정 명령의 안전성 규칙 (Safety First)**:
  - AI는 Python 코드를 직접 작성/실행하지 않고, 엄격하게 포맷팅된 **명령 JSON**만을 발행하여 실행 제어.
  - **수정 전 자동 백업**: 실제 도면을 덮어쓰기 전에 기존 도면의 백업본을 상시 생성.
  - **Dry-run (실행 계획 프리뷰)**: 실제 ZWCAD 연동 없이도 수정 명령의 유효성과 영향 범위를 시각화 및 사전 검토 가능.
* **구체적 도면 편집 기능**:
  - `replace_text`: 도면 내 특정 텍스트 일괄 치환.
  - `move_layer`: 특정 레이어 전체 개체를 지정 좌표로 이동.
  - `replace_block`: 기존 배치된 특정 블록 참조를 새 블록으로 일괄 교체.
  - `delete_layer_objects`: 레이어 내 개체 삭제 (안전성 필터를 거친 제한적 삭제).
  - `create_line` / `create_polyline` / `insert_block`: 선, 폴리라인, 블록 참조의 신규 생성.
* **건축 설계 자동화 매크로**:
  - `place_beams_2d()`: 2D 도면상의 보(Beam) 자동 배치 계획 및 실행.
  - 바운더리(Boundary), 그리드(Grid), 기둥(Column) 및 벽체(Wall) 배치 계획 생성 및 자동 제도.

---

## 3. Image-to-CAD (이미지를 캐드로 변환하는 서브파트)
AI 또는 외부 툴이 도면 이미지를 분석하여 낸 객체 인식 결과(Recognition Output)를 CAD 도면에 실제 적용하고 후처리하기 위한 전용 자동화 서브파트입니다.

* **자동 분석 및 실시간 프리뷰 (`image_to_cad/auto`)**:
  - `auto-analyze-active`: ZWCAD에서 활성화된 도면을 직접 고속 스캔하고, 레이어 매핑 후보를 분석하여 리포트를 작성합니다 (`active_analyzer.py`).
  - `auto-preview-remap`: 특정 임계 신뢰도(예: 0.82 이상)의 고신뢰도 레이어 재매핑(Layer Remap) 프리뷰 결과를 실제 영구 저장하기 전에 CAD 화면에 실시간으로 반영합니다 (`live_preview.py`).
* **실행 안전장치 (Undo Guard)**:
  - `auto-undo-preview`: 실시간 프리뷰를 적용하기 전 ZWCAD 상에 **UNDO MARK**를 자동 지정하고, 검토 후 마음에 들지 않으면 이전 상태로 즉각 안전하게 원복시킵니다 (`undo_guard.py`).
* **인식 객체 도면 자동 맞춤 (`auto-fit-image-result`)**:
  - AI가 도면 이미지를 분석하여 도출한 각종 객체 인식 정보를 실제 캐드 좌표 공간으로 일치시키는 물리적 보정 장치입니다.
  - 기준점 지정(`--base-point`), 축척 배율 조정(`--scale`), 회전각(`--rotation`) 등을 CAD 도면 조건에 최적화(Auto-fit)하여 삽입 및 정렬을 가이드합니다 (`image_result_auto_fit.py`).

---

## 4. 고도화된 도면 시각적 분석 및 검증 툴 (Active Drawing Visual Analysis)
CAD 데이터베이스 속성만으로는 감지하기 어려운 **실제 출력물(PDF/이미지) 기준의 시각적 형상 괴리**를 AI와 크로스 체크하기 위해 특별 제작된 도면 진단 도구입니다 (`tools/` 디렉토리 내 독립 실행 가능).

* **시각적 품질 검사 툴 (`analyze_active_drawing_visuals.py`)**:
  - **도면의 PDF 출력 및 고해상도 렌더링**: ZWCAD Layout Plot 설정을 호출하여 도면 레이아웃들을 PDF로 고속 내보내기하고, `PyMuPDF(fitz)` 모듈을 통해 고해상도 PNG 이미지로 변환합니다.
  - **시각적 분석 규칙 (Visual Check Rules)**:
    1. **도곽 자동 감지 신뢰도 검사 (Title Block Detection)**: CAD 상에 도곽이 존재하더라도, 출력 시 실제 도곽 테두리 영역(Border Bounding Box)과 시각적 구도가 올바른지 대조.
    2. **Layer 0 개체 검출 (Zero Layer Visual Risk)**: CAD의 Layer 0에 방치된 다수의 잔여 개체들을 시각적으로 추출하고, 이들이 외곽선, 심볼, 또는 텍스트인지 분류하여 최적의 레이어로 매핑할 가이드를 마련.
    3. **선 종류 및 두께 불일치 진단 (Lineweight/Linetype Mismatch)**: COM 상에는 실선(Continuous)으로 기록되어 있으나, 실질적으로 점선(Dashed)이나 배팅선(Batting) 등 시각적 표현이 올바르게 출력되는지 확인.
    4. **폰트 깨짐 및 가독성 진단 (Text Readability/Garbled Text)**: 폰트 누락 등으로 인해 실제 출력물 상에서 한글이 깨져 나오거나(Broken Korean Text) 치수선과 텍스트가 겹치는 결함을 실시간 검출.
    5. **외부참조 및 블록 레이아웃 매치 (Xref/Block Sheet Content)**: CAD 외부참조 도면이나 반복되는 심볼들이 페이지 출력 구도와 일치하는지 지능형 매치.
* **도곽 유효 설계 영역 자동 측정 툴 (`measure_zium_sheet_usable_area.py`)**:
  - 지움건축의 표준 도곽 블록(`ZIUM_sheet_architect`)의 실제 도곽 외곽 경계(Outer Border)와 타이틀 클러스터의 영역을 자동으로 인식·분석합니다.
  - 이를 통해 도곽선 내부에서 실제 도면이 그려질 수 있는 안전한 **유효 설계 영역(Usable Drawing Area)**의 경계 박스를 추출하고 리포팅합니다.

---

## 5. XiCAD 연동 및 Safe Bridge 안전 제어 (Third-party Integration)
건축 도면 작업에 널리 활용되는 서드파티 리습 패키지인 **XiCAD**와 안전하게 유기적으로 연동합니다.

* **단축키(Shortkey) 카탈로그 파싱**: XiCAD의 단축키 관리 파일(`xiShortkey.key`)을 분석하여 단축 명령어 매핑 관계 분석.
* **LISP 명령어 자동 큐잉**: 내부 코드를 변경하지 못하는 외부 컴파일 리습 명령(`WAL`, `COL`, `D1`, `W1` 등)을 ZWCAD 명령줄(CommandLine)에 동적으로 전달하여 연동.
* **XiCAD Safe Bridge 격리 확장 레이어**:
  - AI가 대화형(Interactive) 혹은 고위험(High-Risk) 리습 명령을 호출하기 전, 안전 계획을 먼저 수립하여 필터링.
  - `allow_interactive` 및 `allow_high_risk` 플래그 및 건전성(Sanity Check) 검증을 거친 뒤 실행.

---

## 6. 도면 작성 문법 학습 (Drawing Grammar Learning)
도면을 획일적으로 표준화하는 수준을 넘어, **지움건축(ZIUM)** 등 특정 설계사무소의 고유한 도면 작성 스타일을 실시간으로 파악하여 정합성을 유지합니다.

* **레이어 보존 및 무변경 관찰 (Layer Integrity)**: 기존 도면의 고유 레이어 구조(예: `wall1`, `중심선`, `치수`)를 임의 변경하지 않고 감지한 상태에서 신규 객체를 동일 레이어에 자동으로 배정.
* **도곽 블록 재사용 (Title Sheet Reuse)**: 도면 내에 존재하는 표준 도곽 블록(`ZIUM_sheet_architect` 등)을 탐색하여 원점 좌표와 축척(Scale) 정보를 자동 바인딩.
* **주변 속성 샘플링 (Drafting Attributes Sampling)**: 신규 객체 생성 시 주변에 인접한 기존 객체들의 색상, 선종류(Linetype), 선가중치(Lineweight), 텍스트 스타일 등을 실시간 추출(Sampling)하여 도면 고유의 표현 일관성을 완벽히 충족.
* **관련 도구**:
  - `tools/fast_scan_active.py`: 활성 도면의 레이어(수백 개) 및 블록 상태를 초고속 스캔.
  - `tools/analyze_active_form_sample.py`: 도면 중심선, 벽체 표현, 주석 스타일 등 사무소 표준을 1회 패스로 추출해 `sampled_drawing_grammar.json`에 저장.

---

## 7. 프로젝트 테스트 및 검증 체계
* **유닛 테스트 구축**: `pytest`를 기반으로 아키텍처 분석 기능, 예시 JSON 파일들의 사양 검증, ZWCAD 어댑터 인터페이스 정상 동작 여부를 확인하는 테스트(20여 개) 통과 완료.
* **ZWCAD 버전 호환성 준비**: ZWCAD 2025 ~ 2026/2027 등 다중 버전에 대한 동작 검증 시나리오 및 테스트 기틀 마련.
