너는 Python, ZWCAD, XiCAD 리습 자산 파싱, Git PR 정리에 능숙한 시니어 CAD 자동화 개발자다.

작업 대상 저장소: khs0927/HS-CAD
현재 브랜치: stage-23-style-context-bridge

상황:
- Stage 23/24는 테스트 통과 및 ZWCAD preview cleanup 검증까지 완료됨.
- 업로드된 `Summarizing HS-CAD Project Features.md`에는 XiCAD Rule Engine v2가 구현됐다고 되어 있음.
- 하지만 현재 GitHub 브랜치에는 `src/integrations/xicad_rule_engine.py`, `tests/test_xicad_rule_engine.py`, `tests/verify_p0_p1_p2_integrity.py`가 없음.
- PR 변경 목록에는 `generated/xicad/*` 같은 generated artifacts가 포함되어 있음.

작업:
1. 이 ZIP의 XiCAD Rule Engine v2 파일을 적용한다.
2. `python -m pytest tests/test_xicad_rule_engine.py` 실행.
3. `python -m pytest` 실행.
4. `python scripts/cleanup_pr_runtime_artifacts.py --apply`로 tracked runtime artifacts 제거.
5. 변경사항을 커밋/푸시한다.

절대 원칙:
- 기존 Stage 23/24 모듈 삭제 금지.
- `src/main.py`, `src/cad_core/`, `src/adapters/`, `src/extensions/xicad_safe_bridge/`를 깨지 않는다.
- 실제 `C:\xicad`가 없어도 unit test는 통과해야 한다.
- 실제 `C:\xicad` 검증은 `tests/verify_p0_p1_p2_integrity.py`로 별도 실행한다.

커밋 예:
```powershell
git add src/integrations tests/test_xicad_rule_engine.py tests/verify_p0_p1_p2_integrity.py docs/28_xicad_rule_engine_v2.md scripts/cleanup_pr_runtime_artifacts.py APPLY_GUIDE_XICAD_V2_CONFLICT_FIX.md CODEX_PROMPT_XICAD_V2_AND_PR_CLEANUP.md
git add -u
git commit -m "Add XiCAD rule engine v2 and clean runtime artifacts"
git push origin stage-23-style-context-bridge
```
