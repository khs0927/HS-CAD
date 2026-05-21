# HS-CAD 코딩 에이전트용 최종 프롬프트

너는 `khs0927/HS-CAD` 프로젝트를 이어서 개발하는 시니어 CAD 자동화/건축도면 지식화 엔지니어다.

## 0. 현재 상태 먼저 확인

작업 시작 전 반드시 다음을 실행한다.

```bash
git status
git branch --show-current
git log --oneline -10
git diff --name-status
git ls-files src/corpus src/company_profile src/drawing_fileizers tests | sort
```

사용자가 보고한 초기 구현이 로컬에 있으면 절대 삭제하지 말고 확장한다.

이미 있는 것으로 간주할 초기 구현:
- `src/corpus/`
- `src/company_profile/`
- `src/corpus/models.py`
- `src/company_profile/models.py`
- `src/corpus/file_discovery.py`
- `src/corpus/manifest.py`
- `src/corpus/corpus_indexer.py`
- `src/company_profile/hs_cad_profile_loader.py`
- `src/corpus/canonical_schema.py`
- `src/corpus/file_classifier.py`
- `src/corpus/dwg_reader.py`
- `src/corpus/dxf_reader.py`
- `src/app/cli.py`의 corpus/company-profile 명령
- `corpus_learner.py`, `corpus_query.py`, `report_builder.py`는 placeholder일 수 있음

## 1. 목표

이번 작업의 본질은 “AI fine-tuning”이 아니라 다음 흐름이다.

```text
도면정보 파일화
→ 구조화
→ 검색 가능화
→ 건축설계 지식화
→ HS-CAD 내부 회사 도면 문법으로 변환
```

외부 도면은 재료·두께·규격·성능·상세 구성·주석 표현·상황별 설계 대응 지식만 제공한다.  
최종 출력 기준은 HS-CAD 내부의 `CompanyDraftingProfile`과 현재 도면의 주변 속성 샘플링이다.

외부 도면의 레이어명/도곽명/블록명/문자스타일/색상 규칙을 회사 표준으로 삼지 마라.

## 2. 이번 ZIP overlay를 병합하는 방식

이 ZIP에 포함된 파일은 다음 목적이다.

- `src/drawing_fileizers/`: 도면 파일을 JSON/Markdown/SQLite로 파일화
- `src/corpus/*_extractor.py`: 재료·규격·치수·상황·상세 패턴 추출
- `src/company_profile/`: repo 내부 자료에서 회사 기준 추출, canonical-to-company 매핑
- `src/app/cli_fileizer_commands.py`: 기존 Typer CLI에 import해서 붙일 fileizer 명령

기존 파일과 충돌하면:
1. 기존 구현을 먼저 읽는다.
2. 공개 API를 유지한다.
3. 이 ZIP의 기능을 추가 병합한다.
4. 테스트를 보강한다.

## 3. CLI 연결

`src/app/cli.py`가 Typer 기반이면 다음 방식으로 fileizer 명령을 연결한다.

```python
from src.app.cli_fileizer_commands import fileizer_app
app.add_typer(fileizer_app)
```

또는 기존 구조가 단일 app이 아니면 `fileizer-check`, `fileize`, `fileize-folder` 세 명령을 기존 패턴에 맞게 직접 이식한다.

필수 명령:

```bash
python -m src.main fileizer-check
python -m src.main fileize --input tests/fixtures/corpus/sample.dxf --out outputs/fileized_test
python -m src.main fileize-folder --root tests/fixtures/corpus --out outputs/fileized_test --resume
```

## 4. 구현 우선순위

1. 현재 초기 구현과 이 overlay 병합
2. `drawing_fileizers` 테스트 통과
3. `material/specification/dimension/situation` extractor 테스트 통과
4. `knowledge_store.py`를 기존 `corpus_indexer.py`에 연결
5. placeholder `corpus_learner.py`, `corpus_query.py`, `report_builder.py`를 실제 구현으로 교체
6. `company_profile` extractor와 `canonical_to_company_mapper.py` 연결
7. docs와 README 업데이트
8. 전체 pytest

## 5. 완료 조건

```bash
python -m src.main fileizer-check
python -m src.main fileize --input tests/fixtures/corpus/sample.dxf --out outputs/fileized_test
python -m src.main fileize-folder --root tests/fixtures/corpus --out outputs/fileized_test --resume

python -m src.main company-profile-build --repo-root . --out outputs/company_profile
python -m src.main company-profile-show --profile outputs/company_profile/company_drafting_profile.json

python -m src.main corpus-scan --root tests/fixtures/corpus --out outputs/corpus_test
python -m src.main corpus-index --manifest outputs/corpus_test/manifest.json --fileized outputs/fileized_test --out outputs/corpus_test
python -m src.main corpus-learn --kb outputs/corpus_test/cad_knowledge.sqlite --company-profile outputs/company_profile/company_drafting_profile.json --out outputs/corpus_test
python -m src.main corpus-query --kb outputs/corpus_test/cad_knowledge.sqlite --company-profile outputs/company_profile/company_drafting_profile.json --query "판넬 두께와 H빔 접합"
python -m src.main corpus-report --kb outputs/corpus_test/cad_knowledge.sqlite --company-profile outputs/company_profile/company_drafting_profile.json --out outputs/corpus_test/report.md
pytest
```

## 6. 커밋 전략

작은 커밋으로 나눠라.

1. `Add drawing fileizer base models and DXF fileizer`
2. `Add optional DWG and document fileizer adapters`
3. `Implement material specification situation and dimension extractors`
4. `Expand corpus knowledge store learner query and report`
5. `Extract company drafting profile from HS-CAD sources`
6. `Add canonical to company mapping recommendations`
7. `Document drawing fileizer and corpus workflows`
