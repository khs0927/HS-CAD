# HS-CAD 프로젝트 아키텍처 개요

## 프로젝트 목적
ZWCAD AI Architectural Modifier는 Windows + ZWCAD 환경에서 기존 DWG 도면을 열고, 객체를 스캔하고, 좌표/레이어/블록/문자 정보를 JSON으로 추출한 뒤, 안전하게 검증된 JSON 명령으로 도면을 수정하는 Python 프레임워크입니다.

## 엔진 구조
1. **메인 후보: PyRx / cad-pyrx**
   - ZWCAD ZRX 2025–2027 기반 고급 객체 제어용
   - 현재는 Adapter 뼈대 제공
   - 실제 설치 환경에 맞춰 `src/adapters/pyrx_adapter.py` 확장

2. **실제 MVP 동작 엔진: ZWCAD COM / ActiveX**
   - `comtypes`로 `ZWCAD.Application` 연결
   - DWG 열기, 저장, ModelSpace 스캔, 레이어 이동, 문자 치환 지원

3. **선택 보조: pyzwcad**
   - 설치되어 있으면 사용 가능하도록 래퍼 제공
   - 실패 시 COM Adapter로 fallback 권장

4. **검증 보조: ezdxf**
   - DXF 분석, 테스트 도면 생성, 비교 검증용
   - 최종 DWG 수정은 ZWCAD 내부 API/COM/PyRx 사용

## 주요 구성 요소

### 1. 소스 코드 조직 (src/)
- **adapters/**: CAD 백엔드 통합 (ZWCAD COM, PyRx, pyzwcad, ezdxf, XiCAD 등)
- **ai/**: 명령 파싱, 검증, 계획 수립, 안전 가드
- **analysis/**: 분석 워커 및 파이프라인 (Phase 1~12, 메인 머지 준비 결정 등)
- **app/**: CLI 명령 인터페이스 (typer 기반)
- **cad_core/**: CAD 핵심 추상화 (문서, 엔티티, 트랜잭션 등)
- **extensions/**: 확장 기능 (XiCAD Safe Bridge 등)
- **integrations/**: 외부 시스템 통합 (XiCAD 워크플로우, 규칙 엔진 등)
- **modifiers/**: 도면 수정 기능 (레이어, 블록, 텍스트 등)
- **neuro_seq_cad/**: 이미지-to-CAD 변환 파이프라인
- **ocr/**: OCR 기능
- **orchestrator/**: 워크플로우 오케스트레이션
- **pdf_raster/**: PDF 래스터화
- **reports/**: 보고서 생성
- **scanners/**: 객체 스캐너 (블록, 경계, 차원, 레이어, 객체, 텍스트)
- **semantics/**: 의미 분석 (레이어 택소노미, 객체 분류)
- **spatial/**: 공간 처리
- **testing/**: 테스트 인프라
- **ui/**: UI 스텁
- **utils/**: 유틸리티 함수
- **workers/**: 분석 워커 구현

### 2. 설정 파일 (config/)
- **app_config.yaml**: 애플리케이션 설정 (어댑터 우선순위, 백업/출력 디렉토리)
- **command_schema.json**: 허용된 명령 목록
- **layer_rules.yaml**: 건축 레이어 매핑 표준
- **worker_manifest*.json**: 워커 매니페스트 및 패치
- **xicad_*.yaml**: XiCAD 관련 설정
- **zwcad_profiles.yaml**: ZWCAD 프로파일

### 3. CLI 명령 구조 (src/app/cli.py)
- **기본 스캔**: scan, layers, blocks, texts
- **명령 실행**: run-command (dry-run 및 실행 모드)
- **XiCAD 통합**: xicad-catalog, load-xicad, run-xicad
- **XiCAD Safe Bridge**: xicad-safe-catalog, xicad-safe-plan, xicad-safe-run
- **분석 명령**: analyze-architecture, quantity 등
- **플로어플랜**: floorplan-analyze (neuro_seq_cad 연동)

### 4. 어댑터 시스템
- **ZWCADCOMAdapter**: 주요 MVP 엔진 (COM/ActiveX 사용)
- **PyRxAdapter**: 미래 지향적 고급 객체 제어 (뼈대만 제공)
- **pyzwcad_adapter.py**: 선택적 래퍼
- **ezdxf_adapter.py**: 검증 및 분석용
- **xicad_adapter.py**: XiCAD 연동
- **lisp_adapter.py**: LISP 실행

### 5. 분석 모듈 (src/analysis/)
- **main_merge_readiness_decision.py**: 메인 머지 준비 결정 게이트
- **phase3_real_data_binding.py ~ phase12_manual_live_execution_candidate.py**: 단계별 분석 워커
- **post_pr53_main_merge_local_validation.py**: PR53 이후 로컬 검증
- **pipeline_execution_reporter.py**: 파이프라인 실행 보고서
- **validation_rule_engine_v2.py**: 검증 규칙 엔진

### 6. 확장 및 통합
- **extensions/xicad_safe_bridge/**: XiCAD 안전 실행 레이어
- **integrations/**: 외부 규칙 엔진, 워크플로우, 명령 카탈로그
- **neuro_seq_cad/**: 이미지-to-CAD 변환 파이프라인

### 7. 테스트 구조
- **unit 테스트**: 개별 모듈 테스트
- **integration 테스트**: 실제 ZWCAD 연동 테스트 (Windows 전용)
- **fixtures/**: 테스트용 샘플 파일
- **integration/**: 실제 도면 연동 테스트

## 워크플로우
1. 사용자가 DWG 파일 지정 및 명령 선택
2. CLI가 적절한 어댑터 초기화 및 연결
3. 객체 스캔 및 JSON 추출
4. 분석 워커를 통한 데이터 처리 및 의사결정
5. JSON 명령 생성 및 검증
6. 안전 검사 후 실행 (dry-run 옵션 지원)
7. 결과 보고서 및 백업 생성

## 안전 기능
- 수정 전 자동 백업 생성
- dry-run/preview 모드 지원
- 허용된 JSON 명령만 실행 가능
- 수정 전후 리포트 생성
- XiCAD Safe Bridge를 통한 추가 안전 레이어
- 인간 검토 필수 게이트 시스템

## 현재 지원 기능
- ZWCAD COM 연결 및 기본 작업 (열기/저장/스캔)
- 객체 스캔 및 JSON 내보내기
- 레이어별 객체 수 집계
- 블록명별 수량 집계
- 문자 추출
- 특정 레이어 전체 이동
- 문자 일괄 치환
- 건축용 planned actions 생성 (바운더리, 그리드, 기둥 배치)
- XiCAD 연동 및 안전 실행 레이어
- 도면 작성 문법 학습 및 적용 (ZIUM 표준 기반)

## 향후 개발 계획
- PyRx/cad-pyrx 실제 ZWCAD ZRX 연동
- BlockReference 교체 실행
- Polyline vertex 직접 수정
- LISP 실행 연동 강화
- ZWCAD .NET/ZRX Add-in 패널화
- AI 명령 서버/MCP 연동
- AutoCAD/GstarCAD/BricsCAD Adapter 추가