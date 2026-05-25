# HS-CAD Upgrade Framework Plan v1.0

**프로젝트**: ZWCAD AI Architectural Modifier (HS-CAD)
**작성일**: 2026-05-25
**버전**: 1.0
**목적**: 각 기능의 상호작용 분석 및 체계적인 업그레이드 로드맵 제공

---

## 1. Executive Summary

HS-CAD는 ZWCAD 환경에서 기존 DWG 도면을 자동 스캔·분석하고, 안전한 JSON 기반 명령으로 수정하는 AI 지원 건축 도면 자동화 프레임워크입니다.

현재는 **COM 기반 ZWCAD 어댑터 + XiCAD Safe Bridge + Drawing Grammar 학습**이 핵심이며, pytest 37+ 통과, dry-run 완벽 지원, 광범위한 테스트 인프라를 보유하고 있습니다.

**주요 업그레이드 방향**:
- PyRx / ZRX 네이티브 연동으로 성능·안정성 대폭 향상
- LLM 기반 JSON 명령 생성기 (MCP 연동)
- 데스크톱 UI (PySide6)
- Multi-CAD 지원 (AutoCAD, BricsCAD, GstarCAD)
- Drawing Grammar 자동 학습 고도화

---

## 2. Current Architecture Overview

### 2.1 Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer (Typer)                       │
│  src/app/cli.py + *_cli.py (run-command, xicad-safe-*, analyze) │
├─────────────────────────────────────────────────────────────┤
│                     AI / Planning Layer                        │
│  src/ai/ (command_parser, validator, safety_guard)             │
│  src/extensions/xicad_safe_bridge/ (planner, executor, registry)│
├─────────────────────────────────────────────────────────────┤
│                    Adapter / Core Layer                        │
│  src/adapters/ (ZWCADCOMAdapter, XiCADAdapter, PyRx, ezdxf)    │
│  src/cad_core/base.py (추상 인터페이스)                         │
├─────────────────────────────────────────────────────────────┤
│                   Modifier / Generator Layer                   │
│  src/modifiers/architectural_modifier.py (planned actions)     │
│  src/scanners/, src/reports/, neuro_seq_cad/                   │
├─────────────────────────────────────────────────────────────┤
│                      Integration Layer                         │
│  src/integrations/ (XiCAD catalog, manifest, workflows)        │
│  src/integration/reviewcontext_dxf_merge.py (최근 추가)        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 주요 컴포넌트 상호작용 흐름

**기본 실행 흐름 (run-command 예시)**:
1. `cli.run_command()` → `load_command()` + `validate_allowed()`
2. `prepare_safety()` (Safe Bridge)
3. `get_adapter()` → `ZWCADCOMAdapter.connect()` (lazy COM)
4. `adapter.scan_modelspace()` → JSON 추출
5. `execute_planned_actions()` 또는 `move_layer()`, `replace_block()` 등
6. `adapter.save_as()` + 리포트 생성

**XiCAD Safe Bridge 흐름** (격리형):
`XicadSafePlanner` → `XicadSafeExecutor` → `adapter.run_command()` (alias만 전달)

**Drawing Grammar 흐름**:
`tools/fast_scan_active.py` → `sample_style_near_handle.py` → `architectural_modifier` planned actions

---

## 3. Functional Interaction Analysis

| 컴포넌트              | 상호작용 대상                          | 주요 의존성                  | 업그레이드 포인트                  |
|-----------------------|---------------------------------------|------------------------------|------------------------------------|
| ZWCADCOMAdapter      | COM, cli, modifiers                  | comtypes, logger (lazy)     | PyRx 전환, vertex-level 제어      |
| XiCAD Safe Bridge    | XiCAD alias, planner, executor       | registry, json_io           | 고위험 명령 자동 차단 강화        |
| Architectural Modifier | scanners, planned actions            | geometry utils              | Polyline vertex 직접 수정         |
| neuro_seq_cad        | floorplan pipeline, VLM              | image_to_cad                | VLM refinement 고도화             |
| ReviewContext DXF    | DXF QA, integration (최근 머지)      | ezdxf                       | no-COM 환경 QA 강화               |
| CLI (Typer)          | 모든 모듈                            | rich, typer                 | PySide6 GUI 전환 준비             |

---

## 4. Current Status & Resolved Issues (2026-05-25 기준)

**해결 완료**:
- Circular import (ZWCADCOMAdapter ↔ app.cli) → `fix/circular-import-logger-20260525` 브랜치에서 lazy import로 해결
- pytest collection 14 errors → 정상화
- dry-run 완전 지원 (ZWCAD 없이도 실행 가능)

**남은 주요 이슈**:
- PR #39: 로컬 PR38 megapack validation 미푸시
- ZWCAD 2026 실기기 full test plan 미완료
- PyRx 어댑터 skeleton만 존재, 실제 연동 미구현

---

## 5. Upgrade Roadmap (3단계)

### Phase 1: Stabilization (1~2주)
**목표**: 안정성 확보 + 테스트 커버리지 90% 이상

- [ ] `fix/circular-import...` 브랜치 main 머지
- [ ] PR38 로컬 작업 푸시 + validation
- [ ] ZWCAD 2026 전체 테스트 플랜 실행 (`tools/run_zwcad2026_test_plan.py`)
- [ ] `tests/` 50+ 테스트 중 integration 테스트 추가 (실제 DWG fixture)
- [ ] 환경 체크 스크립트 강화 (Windows + ZWCAD 2026/2025 호환성)

**산출물**: 안정화된 v0.9 릴리스

### Phase 2: Core Enhancement (3~5주)
**목표**: 성능·기능 대폭 향상

- [ ] **PyRx / ZRX 네이티브 어댑터 완성** (가장 중요)
  - `src/adapters/pyrx_adapter.py` 실제 구현
  - BlockReference vertex 편집, Polyline 직접 수정
- [ ] **LLM JSON Planner** (MCP 또는 local LLM)
  - `src/ai/llm_planner.py` 추가
  - "도면을 이렇게 수정해줘" → 검증된 JSON만 생성
- [ ] Drawing Grammar 자동 학습 고도화
  - `docs/18~20` 문서 기반 rule engine 강화
- [ ] Desktop UI (PySide6) 프로토타입

**산출물**: v1.0 베타

### Phase 3: Multi-CAD & AI Expansion (2~3개월)
**목표**: 범용 건축 자동화 플랫폼화

- [ ] Multi-CAD Adapter (AutoCAD, BricsCAD, GstarCAD)
- [ ] ZWCAD .NET / ZRX Add-in 패널 개발
- [ ] AI Command Server (MCP Server) 구축
- [ ] 대형 DWG + 클라우드 배치 처리
- [ ] Drawing Grammar 학습 모델 (fine-tuning)

**산출물**: v2.0 정식 릴리스 + 오픈소스 준비

---

## 6. Technical Recommendations

| 영역               | 현재 기술          | 추천 업그레이드          | 우선순위 |
|--------------------|--------------------|--------------------------|----------|
| CAD 연동           | COM (느림, 불안정) | PyRx / ZRX (네이티브)    | ★★★★★   |
| 명령 생성          | 수동 JSON          | LLM + Safety Validator   | ★★★★★   |
| UI                 | CLI (Typer)        | PySide6 Desktop + CLI    | ★★★★    |
| XiCAD 연동         | Safe Bridge (우수) | 고위험 명령 자동 학습    | ★★★★    |
| 테스트             | 단위 테스트 중심   | Real DWG + Integration   | ★★★★    |
| 문서화             | 산발적             | Architecture Decision Records (ADR) | ★★★     |

---

## 7. Testing & Validation Strategy

- **단계별 테스트**:
  1. Unit (이미 37+ 통과)
  2. Integration (실제 DWG fixture + XiCAD)
  3. E2E (Windows + ZWCAD 2026 full plan)
  4. Performance (대형 DWG 10MB+ 기준)
- **안전 검증**: 모든 mutation은 `--dry-run` + backup 필수
- **롤백 전략**: Git 브랜치 + tagged release + revert commit

---

## 8. Risk Management & Rollback Plan

**주요 리스크**:
- PyRx 설치/버전 호환성
- LLM hallucination (Safety Guard로 차단)
- 대형 DWG 메모리 누수

**롤백 계획**:
- 모든 변경은 `feature/upgrade-xxx` 브랜치에서 진행
- main은 항상 안정 버전 유지
- Critical 이슈 발생 시 `git revert` + hotfix 브랜치

---

## 9. Resource & Timeline (예상)

| 단계     | 기간     | 담당          | 필요 리소스          |
|----------|----------|---------------|----------------------|
| Phase 1 | 1~2주   | 1인           | Windows + ZWCAD 2026 |
| Phase 2 | 3~5주   | 1~2인         | LLM API, PySide6     |
| Phase 3 | 2~3개월 | 2~3인         | Multi-CAD 환경       |

---

## 10. Next Immediate Actions (2026-05-25 ~ 05-30)

1. `fix/circular-import-logger-20260525` → main 머지 (PR 생성)
2. PR #39 로컬 작업 푸시 요청
3. `docs/31_upgrade_framework_plan.md` 리뷰 및 피드백 수렴
4. ZWCAD 2026 full test plan 1회 실행 및 결과 공유
5. PyRx 어댑터 skeleton 코드 리뷰 미팅

---

**문서 버전 관리**: 이 문서는 `docs/31_upgrade_framework_plan.md`로 GitHub에 저장되며, 매 주요 마일스톤마다 업데이트됩니다.

**작성자**: Grok (xAI) + khs0927
