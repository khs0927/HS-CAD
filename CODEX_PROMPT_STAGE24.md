# CODEX / 안티그래비티 프롬프트
## Stage 24: Preview Lifecycle + DXF Style Rewriter + QA/Merge Plan

너는 Python, ZWCAD COM, ezdxf, CAD 안전 자동화, 이미지→CAD 후처리, 기존 DWG preview lifecycle 관리에 능숙한 시니어 개발자다.

작업 대상 저장소:
khs0927/HS-CAD

현재 브랜치:
stage-23-style-context-bridge

현재 상태:
- Stage 23 적용 완료
- Stage 23 tests: 15 passed
- Full pytest: 104 passed, 16 skipped
- `src/hs_style_context/`와 `src/neuro_seq_cad_bridge/` 적용 완료
- ZWCAD 실제 `insert-preview --allow-execute`는 아직 실행하지 않음

이번 단계 이름:
stage_24_preview_lifecycle_and_dxf_style_rewriter

목표:
1. `result_wallsolid.dxf` / `result_centerline.dxf`를 style_context 기준으로 후처리한다.
2. 후처리된 DXF를 `styled_result_wallsolid.dxf` / `styled_result_centerline.dxf`로 저장한다.
3. ZWCAD에 삽입한 preview block의 handle/session을 추적한다.
4. preview block을 삭제/교체할 수 있는 lifecycle manager를 만든다.
5. QA markup과 low confidence review를 생성한다.
6. 실제 병합은 하지 않고 merge_candidate_plan.json만 만든다.

절대 원칙:
- 기존 `src/main.py`, `src/cad_core/`, `src/adapters/`, `src/extensions/xicad_safe_bridge/`를 깨지 않는다.
- 원본 DWG Save/SaveAs 금지.
- Purge/Delete/Explode 금지.
- Block definition 내부 수정 금지.
- 기존 객체 bulk delete 금지.
- 삭제 가능한 것은 preview_session.json에 기록된 block reference handle뿐이다.
- 실제 실행은 반드시 `--allow-execute`가 있을 때만 한다.
- 기본 명령은 dry-run이다.
- ZWCAD 없는 테스트 환경에서도 기본 pytest가 통과해야 한다.
- ezdxf가 없어도 테스트가 실패하면 안 된다. 없는 경우 copy/report fallback으로 처리한다.

추가 모듈:
- `src/dxf_style_rewriter/`
- `src/preview_lifecycle/`
- `src/qa_visual_review/`
- `src/merge_planner/`

테스트:
PowerShell:
```powershell
$files = Get-ChildItem tests\test_stage24_*.py | Select-Object -ExpandProperty FullName
python -m pytest @files
```

주요 CLI:
```powershell
python -m src.dxf_style_rewriter.cli rewrite-dxf --source-dxf outputs/demo/result_wallsolid.dxf --styled-result generated/neuro_bridge/styled_result.json --style-context generated/style_context/style_context.json --out generated/stage24
python -m src.preview_lifecycle.cli create-session --plan generated/neuro_bridge/preview_insert_plan.json --insert-result generated/neuro_bridge/insert_preview_result.json --out generated/stage24
python -m src.qa_visual_review.cli build-review --styled-result generated/neuro_bridge/styled_result.json --preview-session generated/stage24/preview_session.json --out generated/stage24
python -m src.merge_planner.cli build-merge-candidate --preview-session generated/stage24/preview_session.json --style-context generated/style_context/style_context.json --styled-result generated/neuro_bridge/styled_result.json --out generated/stage24
```

완료 후 보고:
1. 생성/수정한 파일 목록
2. DXF rewrite 동작 방식
3. preview session 구조
4. remove/replace preview 안전장치
5. QA markup 구조
6. merge candidate plan 구조
7. dry-run 정책
8. 테스트 결과
9. 실제 ZWCAD 검증 명령
10. 현재 한계
11. 다음 단계 제안
