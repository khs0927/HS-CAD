# XiCAD Manual Recording Wizard

## 목적

Contract Workbench는 세션 템플릿과 리뷰 매트릭스를 만들었습니다.  
이번 Wizard는 실제 ZWCAD에서 사람이 관찰한 내용을 빠짐없이 evidence JSON으로 저장하도록 돕습니다.

## 흐름

```text
1. xicad-contract-session으로 체크리스트 확인
2. ZWCAD에서 사람이 직접 alias 입력
3. 프롬프트 순서 관찰
4. Wizard 실행
5. Wizard 질문에 관찰 내용 입력
6. evidence JSON 생성
7. 즉시 validate_contract_evidence로 검증
```

## 안전 원칙

- Wizard는 ZWCAD를 제어하지 않습니다.
- SendCommand를 호출하지 않습니다.
- 도면을 저장/삭제/폭파하지 않습니다.
- recipe_registry.py를 수정하지 않습니다.
- promotion은 사람이 review pack을 본 뒤 별도로 수행합니다.
