작업 대상:
- GitHub 저장소: khs0927/HS-CAD
- 현재 상태:
  - Stage-1 safety lock / recipe registry default-deny 완료
  - Stage-2 Contract Verification Layer 완료
  - Contract Workbench 완료 및 main push 완료
  - xicad-contract-session, review-matrix, bundle-validate, review-pack 사용 가능
- 이번 목표:
  - 사람이 실제 ZWCAD에서 XiCAD 명령을 관찰한 내용을 빠짐없이 기록할 수 있도록 interactive/manual recorder를 추가한다.

중요 원칙:
1. XiCAD/ZWCAD 명령 자동 실행 금지.
2. SendCommand 사용 금지.
3. recipe registry 자동 수정 금지.
4. verified/scriptable 자동 승격 금지.
5. 사용자가 입력한 관찰 내용만 evidence JSON으로 저장.
6. 저장 직후 validate_contract_evidence로 BLOCKED/PASS를 보여준다.
7. ZWCAD 없는 환경에서도 테스트 통과.

적용:
python hscad_xicad_manual_recorder_patch/scripts/apply_xicad_manual_recorder_patch.py --repo-root .

추가 파일:
- src/orchestrator/xicad_manual_recorder.py
- src/app/xicad_manual_recorder_cli.py
- docs/27_xicad_manual_recording_wizard.md
- tests/test_xicad_manual_recorder.py
- tests/test_xicad_manual_record_templates.py

추가 CLI:
1. xicad-contract-wizard
   - alias별 대화형 수동 기록 wizard
   - 예:
     python -m src.main xicad-contract-wizard --alias WAL --out-dir outputs/xicad_contracts

2. xicad-contract-record-template
   - 수동 입력용 record template JSON 생성
   - 예:
     python -m src.main xicad-contract-record-template --alias WAL --out outputs/xicad_contracts/WAL_record_template.json

3. xicad-contract-record-command
   - 긴 xicad-contract-record 명령 예시를 alias별로 출력
   - 예:
     python -m src.main xicad-contract-record-command --alias WAL

검증:
python -m src.main --help
python -m src.main xicad-contract-record-template --alias WAL --out outputs/xicad_contracts/WAL_record_template.json
python -m src.main xicad-contract-record-command --alias WAL
pytest -q tests/test_xicad_manual_recorder.py tests/test_xicad_manual_record_templates.py

완료 보고:
1. 추가 파일
2. 추가 CLI
3. wizard가 자동 실행하지 않음을 확인
4. template/command 출력 확인
5. 테스트 결과
6. 다음 단계 제안
