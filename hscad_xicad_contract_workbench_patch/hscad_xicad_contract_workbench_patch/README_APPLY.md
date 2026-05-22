# HS-CAD XiCAD Contract Workbench Patch

이 패치는 이미 적용된 `Stage-2 Contract Verification Layer` 위에,  
실제 ZWCAD + XiCAD 수동 검증을 빠짐없이 반복하기 위한 **Contract Workbench**를 추가합니다.

## 목적

- 명령별 수동 검증 세션 템플릿 생성
- 기록된 `_record.json` 파일들을 일괄 검증
- promotion candidate 후보들을 한 번에 리뷰할 수 있는 패키지 생성
- `xicad_recipe_registry.py`는 절대 자동 수정하지 않음
- ZWCAD 없이도 테스트 통과

## 적용

```powershell
python hscad_xicad_contract_workbench_patch/scripts/apply_xicad_contract_workbench_patch.py --repo-root .
```

## 주요 명령

```powershell
python -m src.main xicad-contract-session --alias WAL --out-dir outputs/xicad_sessions

python -m src.main xicad-contract-review-matrix --aliases WAL,D1,W1,INS,COL,BE --out-dir outputs/xicad_sessions

python -m src.main xicad-contract-bundle-validate --records-dir outputs/xicad_contracts --out-dir outputs/xicad_contracts/bundle

python -m src.main xicad-contract-review-pack --records-dir outputs/xicad_contracts --out-dir outputs/xicad_contracts/review_pack
```

## 검증

```powershell
pytest -q tests/test_xicad_contract_workbench.py
pytest -q tests/test_xicad_contract_bundle.py
pytest -q tests/test_xicad_promotion_review.py
```
