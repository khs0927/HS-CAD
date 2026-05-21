# HS-CAD XiCAD Rule Engine v2 + PR Conflict Fix 적용 가이드

이 ZIP은 업로드된 `Summarizing HS-CAD Project Features.md`의 XiCAD Rule Engine v2 설명과 현재 GitHub PR 상태를 비교하여 만든 보강 패키지입니다.

## 확인된 차이

1. 요약 파일에는 `src/integrations/xicad_rule_engine.py`, `tests/test_xicad_rule_engine.py`, `tests/verify_p0_p1_p2_integrity.py`가 구현된 것으로 되어 있으나, 현재 PR 브랜치에는 해당 파일이 없습니다.
2. `.gitignore`에는 `generated/`, `outputs/`, `temp_overlay/`, `*.zip` 규칙이 이미 있지만, PR에는 `generated/xicad/*` 산출물이 아직 tracked 상태로 남아 있습니다.

## 적용

```powershell
git checkout stage-23-style-context-bridge
```

ZIP의 `src`, `tests`, `docs`, `scripts`를 HS-CAD 루트에 병합합니다.

## 테스트

```powershell
python -m pytest tests/test_xicad_rule_engine.py
python -m pytest
```

## 실제 C:\xicad 검증

```powershell
python tests/verify_p0_p1_p2_integrity.py --xicad-root C:\xicad --out outputs/xicad_integrity_report.json
```

## tracked runtime artifacts 정리

```powershell
python scripts/cleanup_pr_runtime_artifacts.py
python scripts/cleanup_pr_runtime_artifacts.py --apply
```
