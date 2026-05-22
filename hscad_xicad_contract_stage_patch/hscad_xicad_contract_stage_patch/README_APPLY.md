# HS-CAD XiCAD Contract Verification Stage Patch

이 패치는 Stage-1 안전 정책(default-deny, auto_run=False)이 `main`에 푸시된 상태를 전제로,  
**Stage-2: 실제 ZWCAD + XiCAD 명령 인자 계약 검증**을 위한 안전한 코드 레이어를 추가합니다.

핵심 원칙:

- XiCAD 명령을 자동 실행하지 않습니다.
- 검증 전에는 어떤 명령도 `scriptable=True`로 승격하지 않습니다.
- 실제 ZWCAD 테스트 결과는 JSON evidence로 기록합니다.
- evidence가 충분한 경우에도 registry를 바로 수정하지 않고 **promotion candidate**만 생성합니다.
- 최종 `verified=True`, `scriptable=True` 반영은 사람이 리뷰 후 별도 커밋합니다.

## 적용 방법

HS-CAD 저장소 루트에서 압축 해제 후:

```powershell
python hscad_xicad_contract_stage_patch/scripts/apply_xicad_contract_stage_patch.py --repo-root .
```

## 검증 명령

```powershell
python -m src.main --help

python -m src.main xicad-contract-plan --aliases WAL,D1,W1,INS,COL,BE --out-dir outputs/xicad_contracts

python -m src.main xicad-contract-summary --contracts outputs/xicad_contracts/xicad_contract_plan.json

python -m src.main xicad-contract-record --alias WAL --status failed --notes "manual test pending" --out outputs/xicad_contracts/WAL_record.json

python -m src.main xicad-contract-validate --record outputs/xicad_contracts/WAL_record.json

pytest -q tests/test_xicad_contract_registry.py
pytest -q tests/test_xicad_contract_validation.py
pytest -q tests/test_xicad_contract_cli_model.py
```

## 생성 파일

- `src/orchestrator/xicad_contracts.py`
- `src/orchestrator/xicad_contract_test_plan.py`
- `src/orchestrator/xicad_contract_validator.py`
- `src/orchestrator/xicad_contract_report.py`
- `src/app/xicad_contract_cli.py`
- `docs/25_xicad_contract_verification_stage.md`
- 관련 테스트 파일

## Stage-2 의미

Stage-2는 자동 실행 단계가 아닙니다.  
Stage-2는 **ZWCAD + XiCAD 환경에서 명령별 인자 계약을 확인하고, 그 결과를 evidence로 축적하는 단계**입니다.
