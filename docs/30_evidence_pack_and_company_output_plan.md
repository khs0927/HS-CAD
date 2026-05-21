# 30. Evidence Pack and Company Output Plan

## Evidence Pack

`evidence_pack`은 사용자의 질문에 대한 근거 묶음이다.

포함 내용:

- query
- expanded terms
- matched tables
- source file ids
- evidence text
- score
- confidence

용도:

- 설계 검토
- 유사 사례 확인
- 도면 생성 전 체크리스트 구성
- CompanyOutputPlan 입력

## Company Output Plan

`company_output_plan`은 Evidence Pack을 HS-CAD 내부 회사 기준으로 옮기는 계획이다.

포함 내용:

- 사용할 도곽 후보
- 치수 스타일 후보
- 문자 스타일 후보
- canonical element별 회사 레이어 후보
- drafting notes
- warnings

## 주의

외부 도면에서 나온 레이어명, 도곽명, 문자 스타일은 출력 기준으로 쓰지 않는다.

출력 기준 우선순위:

1. 현재 활성 도면 주변 속성 샘플링
2. HS-CAD CompanyDraftingProfile
3. canonical fallback
4. QA-REVIEW
