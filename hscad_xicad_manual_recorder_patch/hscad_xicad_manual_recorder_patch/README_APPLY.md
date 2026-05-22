# HS-CAD XiCAD Manual Recorder Patch

이 패치는 Contract Workbench 이후 단계입니다.  
실제 ZWCAD + XiCAD 명령을 사람이 테스트하면서, 프롬프트 순서/인자 패턴/출력/UNDO/안전 확인을 빠짐없이 기록하도록 돕는 **대화형 수동 기록기**를 추가합니다.

## 핵심 원칙

- XiCAD/ZWCAD 명령을 자동 실행하지 않습니다.
- 사용자가 관찰한 내용을 질문 방식으로 입력받아 evidence JSON을 생성합니다.
- 생성 직후 기존 `validate_contract_evidence`로 검증합니다.
- recipe registry를 자동 수정하지 않습니다.
- promotion candidate도 자동 반영하지 않습니다.

## 적용

```powershell
python hscad_xicad_manual_recorder_patch/scripts/apply_xicad_manual_recorder_patch.py --repo-root .
```

## 주요 명령

```powershell
python -m src.main xicad-contract-wizard --alias WAL --out-dir outputs/xicad_contracts
python -m src.main xicad-contract-record-template --alias WAL --out outputs/xicad_contracts/WAL_record_template.json
python -m src.main xicad-contract-record-command --alias WAL
```

## 테스트

```powershell
pytest -q tests/test_xicad_manual_recorder.py
pytest -q tests/test_xicad_manual_record_templates.py
```
