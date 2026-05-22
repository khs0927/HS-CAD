# XiCAD Contract Verification Stage

## 목적

Stage-1에서 HS-CAD는 XiCAD recipe를 모두 default-deny 상태로 잠갔습니다.  
Stage-2는 실제 ZWCAD + XiCAD 환경에서 명령별 인자 계약을 검증하고, 검증 증거를 축적하는 단계입니다.

## 중요한 원칙

- XiCAD 명령 자동 실행 금지
- recipe registry 직접 승격 금지
- evidence 기반 promotion candidate만 생성
- Save/Delete/Purge/Explode 자동 실행 금지
- verified/scriptable 승격은 사람이 리뷰 후 별도 커밋

## 검증 대상 우선순위

1. WAL / xiDrawWall / 벽체
2. D1 / xiDoor1 / 문
3. W1 / xiWin1 / 창
4. INS / xiInsul / 단열
5. COL / xiDrawColumn / 기둥
6. BE / xiBE / H빔
7. AE / xiAE / 면적
8. LC / xiChangeLayer / 레이어 변경

## 명령

```powershell
python -m src.main xicad-contract-plan --aliases WAL,D1,W1,INS,COL,BE --out-dir outputs/xicad_contracts
python -m src.main xicad-contract-summary --contracts outputs/xicad_contracts/xicad_contract_plan.json
python -m src.main xicad-contract-record --alias WAL --status failed --notes "manual test pending" --out outputs/xicad_contracts/WAL_record.json
python -m src.main xicad-contract-validate --record outputs/xicad_contracts/WAL_record.json
```

## Promotion 조건

아래 조건을 모두 만족해야 promotion candidate 생성이 가능합니다.

- status == passed
- ZWCAD version 기록
- XiCAD version 또는 XiCAD root 기록
- prompt sequence 기록
- accepted argument pattern 기록
- output observation 기록
- rollback observation 기록
- safety observation 기록
- no_save_confirmed=True
- no_delete_confirmed=True
- no_explode_confirmed=True

## 다음 단계

충분한 evidence가 쌓이면 사람이 promotion_candidate.json을 리뷰하고, 검증된 명령만 recipe_registry에서 verified=True, scriptable=True로 승격합니다.
