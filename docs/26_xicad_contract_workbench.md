# XiCAD Contract Workbench

## 목적

이 단계는 실제 ZWCAD + XiCAD에서 명령별 인자 계약을 확인하는 실무 워크벤치입니다.

자동 실행을 하지 않고, 사람이 명령 창에서 직접 관찰한 내용을 빠짐없이 기록하도록 돕습니다.

## 흐름

```text
1. xicad-contract-session으로 alias별 검증 템플릿 생성
2. ZWCAD에서 사람이 직접 명령 실행 및 프롬프트 관찰
3. xicad-contract-record로 evidence 기록
4. xicad-contract-bundle-validate로 여러 record 일괄 검증
5. xicad-contract-review-pack으로 사람이 볼 promotion review pack 생성
6. 사람이 review 후 recipe_registry.py를 별도 커밋으로 수정
```

## 안전 원칙

- SendCommand 자동 실행 없음
- Save/Delete/Explode/Purge 자동 실행 없음
- recipe registry 자동 수정 없음
- promotion candidate는 후보일 뿐
- 최종 승격은 사람 리뷰 후 별도 수행

## 권장 우선순위

1. WAL / xiDrawWall
2. D1 / xiDoor1
3. W1 / xiWin1
4. INS / xiInsul
5. COL / xiDrawColumn
6. BE / xiBE
7. AE / xiAE
8. LC / xiChangeLayer
