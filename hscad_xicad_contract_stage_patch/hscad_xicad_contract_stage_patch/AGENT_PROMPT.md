작업 대상:
- GitHub 저장소: khs0927/HS-CAD
- 현재 상태:
  - Stage-1 안전 정책 및 XiCAD recipe registry가 main에 푸시됨.
  - 모든 recipe는 default-deny 상태.
  - INS, AE, LC, WAL, D1, W1, BE 모두 verified=False, scriptable=False, auto_run_allowed=False.
  - 테스트 25 passed 확인됨.
- 이번 목표:
  - 실제 ZWCAD + XiCAD 환경에서 각 명령의 인자 계약을 검증하기 위한 Stage-2 Contract Verification 레이어를 추가한다.

중요 원칙:
1. XiCAD 명령을 자동 실행하지 말라.
2. ZWCAD SendCommand, Save, Delete, Purge, Explode 자동 실행 금지.
3. 검증 전에는 어떤 명령도 verified=True 또는 scriptable=True로 바꾸지 말라.
4. 이번 단계에서 recipe_registry를 직접 승격하지 말고 promotion candidate JSON만 생성하라.
5. 실제 승격은 사람이 evidence를 검토한 뒤 별도 커밋으로 수행한다.
6. ZWCAD가 없어도 테스트가 통과해야 한다.
7. Stage-1의 default-deny 정책을 유지하라.

적용할 패치:
- hscad_xicad_contract_stage_patch.zip 압축 해제
- 아래 명령 실행:

python hscad_xicad_contract_stage_patch/scripts/apply_xicad_contract_stage_patch.py --repo-root .

추가/수정 파일:
- src/orchestrator/xicad_contracts.py
- src/orchestrator/xicad_contract_test_plan.py
- src/orchestrator/xicad_contract_validator.py
- src/orchestrator/xicad_contract_report.py
- src/app/xicad_contract_cli.py
- docs/25_xicad_contract_verification_stage.md
- tests/test_xicad_contract_registry.py
- tests/test_xicad_contract_validation.py
- tests/test_xicad_contract_cli_model.py

추가 CLI:
1. xicad-contract-plan
   - 검증할 alias 목록을 받아 수동 테스트 계획 생성
   - 예:
     python -m src.main xicad-contract-plan --aliases WAL,D1,W1,INS,COL,BE --out-dir outputs/xicad_contracts

2. xicad-contract-summary
   - 계약 계획 또는 검증 결과 요약
   - 예:
     python -m src.main xicad-contract-summary --contracts outputs/xicad_contracts/xicad_contract_plan.json

3. xicad-contract-record
   - 실제 ZWCAD 수동 테스트 결과를 JSON으로 기록
   - 예:
     python -m src.main xicad-contract-record --alias WAL --status passed --notes "manual ZWCAD test done" --out outputs/xicad_contracts/WAL_record.json

4. xicad-contract-validate
   - record가 승격 가능한지 검증
   - 기본적으로 증거 부족이면 blocked
   - 예:
     python -m src.main xicad-contract-validate --record outputs/xicad_contracts/WAL_record.json

5. xicad-contract-promotion-candidate
   - 충분한 evidence가 있을 때만 promotion_candidate.json 생성
   - recipe_registry.py를 직접 수정하지 않음

구현 기준:
- xicad_contracts.py에는 dataclass를 둔다:
  - XiCADArgumentSpec
  - XiCADCommandContract
  - XiCADContractEvidence
  - XiCADPromotionCandidate
- 초기 계약 상태는 모두 UNVERIFIED.
- DEFAULT_TARGET_ALIASES:
  - WAL, D1, W1, INS, COL, BE, AE, LC
- validate_contract_evidence는 아래 조건을 만족해야 promotion 가능:
  - status == passed
  - manual_zwcad_version 존재
  - xicad_version 또는 xicad_root 존재
  - observed_prompt_sequence 1개 이상
  - accepted_argument_pattern 1개 이상
  - output_observation 존재
  - rollback_observation 존재
  - safety_observation 존재
  - no_save_confirmed=True
  - no_delete_confirmed=True
  - no_explode_confirmed=True
- 하나라도 부족하면 promotion blocked.

테스트:
python -m src.main --help
python -m src.main xicad-contract-plan --aliases WAL,D1,W1,INS,COL,BE --out-dir outputs/xicad_contracts
python -m src.main xicad-contract-summary --contracts outputs/xicad_contracts/xicad_contract_plan.json
pytest -q tests/test_xicad_contract_registry.py
pytest -q tests/test_xicad_contract_validation.py
pytest -q tests/test_xicad_contract_cli_model.py

완료 보고:
1. 추가 파일 목록
2. 추가 CLI 목록
3. contract validation 조건
4. promotion candidate 생성 방식
5. recipe registry 직접 수정 없음 확인
6. 테스트 결과
7. 다음 단계 제안
