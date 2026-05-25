# HS-CAD Main Code Overlay Progress Report

## 기준 상태

이 패키지는 PR #58 검증 이후 단계로, 기존 safety/process PR에 next-stage 코드를 섞지 않고 별도 PR 후보로 적용하기 위한 main-code overlay입니다.

## 현재 진행도 판단

| 영역 | 상태 | 진행도 |
|---|---:|---:|
| PR #58 safety/process 검증 | 완료 | 100% |
| safety flags false 유지 | 완료 | 100% |
| next-stage architecture skeleton | 완료 | 100% |
| fileizer 공통 모델 | 이번 패키지에서 실구현 강화 | 75% |
| DXF parsing | minimal parser + optional ezdxf 경계 구현 | 65% |
| DWG 처리 | ODAFC boundary 구현, COM full scan 배제 | 45% |
| analyzer graph | layer/text/area/spatial composite 구현 | 55% |
| evidence fusion | FUSION_MATRIX/CROSS_VALIDATION writer 구현 | 60% |
| domain rules | plan-only rule runner 구현 | 55% |
| DXF outputs | centerline/wallsolid/qa_overlay writer 구현 | 50% |
| SQLite evidence index | local store 구현 | 50% |
| FINAL_REPORT.md | markdown writer 구현 | 45% |
| 기존 src.main CLI 통합 | 아직 미연결, 안전상 별도 CLI 유지 | 15% |
| 실제 CAD live runner | 의도적으로 미구현 | 0% |

## 이번 overlay가 추가하는 것

- `hscad.pipelines.main_code_pipeline`
- DXF fileizer, DWG→DXF conversion boundary
- layer/text/area/spatial analyzers
- evidence fusion and cross-validation output
- plan-only domain rule runner
- review-only DXF outputs
- SQLite evidence index
- Markdown report writer
- safety policy guard

## 남은 메인 코드 작업

1. 기존 `src.main` CLI에 `main-code-pipeline` 명령 연결
2. 기존 analyzer/exporter 산출물을 새 evidence model로 점진 연결
3. `ezdxf` 설치 환경에서 실제 DXF writer 품질 강화
4. PDF/Image adapter를 optional dependency로 분리 구현
5. Shapely topology analyzer를 이번 composite analyzer에 연결
6. 기존 PR #58 safety docs와 충돌 없이 별도 PR로 제출
