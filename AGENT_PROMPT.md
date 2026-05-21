# HS-CAD Next Phase Agent Prompt

너는 `khs0927/HS-CAD` 프로젝트를 이어서 개발하는 시니어 CAD 자동화/건축도면 지식화 엔지니어다.

현재 상태:
- 1차 overlay가 적용되어 `src/drawing_fileizers/`, `src/corpus/`, `src/company_profile/`가 추가되었다.
- `pytest -q` 결과 `128 passed, 16 skipped`로 정상 통과했다고 보고되었다.
- 현재 남은 다음 단계는 다음 3가지다.
  1. `corpus-index`에 `--fileized` 결과 연동
  2. `corpus-learn`, `corpus-query`, `corpus-report`의 placeholder를 실제 지식 추출·요약·검색·보고서 로직으로 교체
  3. `canonical_to_company_mapper`를 활용한 회사 기준 출력 매핑 완성

이번 ZIP은 2차 overlay다.
기존 파일을 무조건 덮어쓰기보다 diff를 보고 병합하라.

## 반드시 먼저 실행

```bash
git status
git branch --show-current
git log --oneline -5
python -m src.main --help
pytest -q
```

## 병합 원칙

1. 기존 구현이 있으면 API를 깨지 말고 확장한다.
2. 기존 `src/corpus/corpus_indexer.py`가 이미 있으면 `src/corpus/fileized_ingest.py`의 함수를 import하여 `--fileized` 옵션을 붙인다.
3. 기존 `corpus_learner.py`, `corpus_query.py`, `report_builder.py`가 placeholder면 이번 ZIP의 구현으로 교체한다.
4. `src/app/cli_next_phase_commands.py`는 임시 보조 CLI다. 기존 `src/app/cli.py`에 자연스럽게 통합하거나 다음처럼 추가한다.

```python
from src.app.cli_next_phase_commands import next_phase_app
app.add_typer(next_phase_app, name="corpus-next")
```

또는 기존 명령 이름으로 직접 병합한다.

## 목표 명령

최종적으로 아래 명령이 동작해야 한다.

```bash
python -m src.main corpus-index --manifest outputs/corpus_test/manifest.json --fileized outputs/fileized_test --out outputs/corpus_test
python -m src.main corpus-learn --kb outputs/corpus_test/cad_knowledge.sqlite --company-profile outputs/company_profile/company_drafting_profile.json --out outputs/corpus_test
python -m src.main corpus-query --kb outputs/corpus_test/cad_knowledge.sqlite --company-profile outputs/company_profile/company_drafting_profile.json --query "판넬 두께와 H빔 접합"
python -m src.main corpus-report --kb outputs/corpus_test/cad_knowledge.sqlite --company-profile outputs/company_profile/company_drafting_profile.json --out outputs/corpus_test/report.md
pytest -q
```

## 핵심 철학

외부 도면의 스타일은 가져오지 않는다.
외부 도면의 건축 지식만 가져온다.

외부 도면에서 추출할 것:
- 재료
- 두께
- 규격
- 성능
- 치수
- 상세 구성
- 주석 표현
- 상황별 설계 대응

최종 출력 기준:
- HS-CAD 내부 CompanyDraftingProfile
- 현재 활성 도면 주변 속성 샘플링
- ZIUM 회사 문법
- preview/dry-run 우선
- 원본 저장 금지
