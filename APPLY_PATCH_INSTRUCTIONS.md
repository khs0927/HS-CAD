# 적용 방법

1. 이 ZIP을 HS-CAD 저장소 루트에서 압축 해제한다.
2. 파일을 바로 `Copy-Item -Recurse -Force`로 덮어쓰기 전에 diff를 확인한다.
3. 아래 파일은 기존 구현과 병합이 필요할 수 있다.
   - `src/corpus/knowledge_store.py`
   - `src/corpus/corpus_learner.py`
   - `src/corpus/corpus_query.py`
   - `src/corpus/report_builder.py`
   - `src/company_profile/canonical_to_company_mapper.py`
   - `src/app/cli.py`

4. 새로 추가되는 핵심 파일:
   - `src/corpus/fileized_ingest.py`
   - `src/app/cli_next_phase_commands.py`
   - `tests/test_fileized_ingest_and_knowledge.py`
   - `tests/test_corpus_learn_query_report_next.py`

5. 적용 후 실행:

```bash
pytest -q
python -m src.main corpus-next index-fileized --fileized outputs/fileized_test --out outputs/corpus_test
python -m src.main corpus-next learn --kb outputs/corpus_test/cad_knowledge.sqlite --out outputs/corpus_test
python -m src.main corpus-next query --kb outputs/corpus_test/cad_knowledge.sqlite --query "판넬 두께와 H빔 접합"
python -m src.main corpus-next report --kb outputs/corpus_test/cad_knowledge.sqlite --out outputs/corpus_test/report.md
```

6. 정상 동작이 확인되면 기존 `corpus-index`, `corpus-learn`, `corpus-query`, `corpus-report` 명령에 이 로직을 병합한다.
