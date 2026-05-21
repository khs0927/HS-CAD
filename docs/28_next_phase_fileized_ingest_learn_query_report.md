# 28. Fileized Ingest, Learn, Query, Report Next Phase

## 목적

1차 overlay는 도면정보 fileizer와 corpus/company profile의 기본 구조를 만들었다.
이번 단계는 fileizer 결과를 실제 지식베이스에 연결하고, placeholder였던 학습·쿼리·리포트를 실제 동작으로 강화한다.

## 새 흐름

```text
outputs/fileized/json/*.json
→ fileized_ingest.py
→ cad_knowledge.sqlite
→ corpus_learner.py
→ architectural_lessons
→ corpus_query.py
→ CompanyDraftingProfile 기반 출력 추천
→ report_builder.py
```

## 임시 보조 CLI

기존 CLI에 바로 병합하기 전 다음 보조 앱을 연결할 수 있다.

```python
from src.app.cli_next_phase_commands import next_phase_app
app.add_typer(next_phase_app, name="corpus-next")
```

명령:

```bash
python -m src.main corpus-next index-fileized --fileized outputs/fileized_test --out outputs/corpus_test
python -m src.main corpus-next learn --kb outputs/corpus_test/cad_knowledge.sqlite --out outputs/corpus_test
python -m src.main corpus-next query --kb outputs/corpus_test/cad_knowledge.sqlite --query "판넬 두께와 H빔 접합"
python -m src.main corpus-next report --kb outputs/corpus_test/cad_knowledge.sqlite --out outputs/corpus_test/report.md
```

## 기존 CLI에 병합할 때

- 기존 `corpus-index`에 `--fileized` 옵션을 추가한다.
- 기존 `corpus-learn`은 `learn_from_kb()`를 호출한다.
- 기존 `corpus-query`는 `query_kb()`를 호출한다.
- 기존 `corpus-report`는 `build_report()`를 호출한다.

## 원칙

외부 도면의 스타일은 가져오지 않는다.
외부 도면의 건축 지식만 가져온다.
최종 출력 추천은 HS-CAD 내부 CompanyDraftingProfile 기준으로 한다.
