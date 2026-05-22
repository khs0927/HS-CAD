작업 대상:
- GitHub 저장소: khs0927/HS-CAD
- 현재 상태:
  - Stage-1 XiCAD safety lock + recipe registry default-deny 완료
  - Stage-2 Contract Verification Layer 적용 및 push 완료
  - xicad-contract-plan / record / validate / promotion-candidate CLI 동작 확인
  - 테스트 통과

이번 목표:
실제 ZWCAD + XiCAD에서 명령별 인자 계약을 사람이 검증할 때, 누락 없이 기록하고 여러 evidence를 일괄 검증하며, promotion candidate를 사람이 리뷰할 수 있는 패키지로 묶는 Contract Workbench를 추가한다.

중요 원칙:
1. XiCAD/ZWCAD 명령 자동 실행 금지.
2. recipe registry 자동 수정 금지.
3. verified=True, scriptable=True 자동 반영 금지.
4. promotion candidate는 사람이 리뷰할 JSON/MD 패키지로만 생성.
5. Save/Delete/Explode/Purge 자동 실행 금지.
6. ZWCAD 없는 환경에서도 테스트 통과.

적용할 패치:
- hscad_xicad_contract_workbench_patch.zip 압축 해제
- 실행:
  python hscad_xicad_contract_workbench_patch/scripts/apply_xicad_contract_workbench_patch.py --repo-root .

추가 파일:
- src/orchestrator/xicad_contract_workbench.py
- src/orchestrator/xicad_contract_bundle.py
- src/orchestrator/xicad_promotion_review.py
- src/app/xicad_contract_workbench_cli.py
- docs/26_xicad_contract_workbench.md
- tests/test_xicad_contract_workbench.py
- tests/test_xicad_contract_bundle.py
- tests/test_xicad_promotion_review.py

추가 CLI:
1. xicad-contract-session
   - alias별 수동 검증 템플릿 생성
   - 예:
     python -m src.main xicad-contract-session --alias WAL --out-dir outputs/xicad_sessions

2. xicad-contract-review-matrix
   - 여러 alias의 검증 체크리스트 matrix 생성
   - 예:
     python -m src.main xicad-contract-review-matrix --aliases WAL,D1,W1,INS,COL,BE --out-dir outputs/xicad_sessions

3. xicad-contract-bundle-validate
   - records-dir 안의 *_record.json을 모두 검증
   - 예:
     python -m src.main xicad-contract-bundle-validate --records-dir outputs/xicad_contracts --out-dir outputs/xicad_contracts/bundle

4. xicad-contract-review-pack
   - 검증 가능한 record를 promotion candidate와 review matrix로 묶음
   - recipe_registry.py 직접 수정 금지
   - 예:
     python -m src.main xicad-contract-review-pack --records-dir outputs/xicad_contracts --out-dir outputs/xicad_contracts/review_pack

검증 명령:
python -m src.main --help
python -m src.main xicad-contract-session --alias WAL --out-dir outputs/xicad_sessions
python -m src.main xicad-contract-review-matrix --aliases WAL,D1,W1,INS,COL,BE --out-dir outputs/xicad_sessions
pytest -q tests/test_xicad_contract_workbench.py tests/test_xicad_contract_bundle.py tests/test_xicad_promotion_review.py

완료 보고:
1. 추가 파일
2. 추가 CLI
3. 생성되는 세션/매트릭스/번들 리포트
4. recipe registry 자동 수정 없음 확인
5. 테스트 결과
6. 실제 수동 검증 진행 방법
