너는 HS-CAD review output quality v7 작업을 로컬에서 안전하게 적용/검증하는 코딩 에이전트다.

브랜치:
- clean branch: feature/review-output-quality-v2
- base: feature/evidence-bridge-schema-golden

중요:
- 중간 브랜치 feature/review-dxf-output-fidelity 는 사용하지 않는다.
- 원본 입력 파일은 수정하지 않는다.
- outputs, cache, zip, runtime CAD 파일은 커밋하지 않는다.

목표:
1. review output helper를 추가한다.
2. QA label과 low-confidence marker를 생성한다.
3. review output manifest를 생성한다.
4. focused tests를 통과시킨다.

검증:

```powershell
python -X utf8 -m pytest -q tests/test_review_dxf_output_v7.py
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

완료 후 보고:
- 적용 파일
- 테스트 결과
- 생성 artifact
- 커밋 제외 파일 확인
- 안전 확인
