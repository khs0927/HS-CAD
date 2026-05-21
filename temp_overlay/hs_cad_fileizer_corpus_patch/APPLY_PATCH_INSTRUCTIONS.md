# HS-CAD Fileizer + Corpus Patch Overlay

이 ZIP은 기존 `khs0927/HS-CAD` 프로젝트 위에 **추가/확장**하는 patch overlay입니다.

## 적용 원칙

1. 기존 파일을 무조건 덮어쓰지 마세요.
2. 로컬에 이미 `src/corpus/`, `src/company_profile/` 초기 구현이 있으면 먼저 diff를 확인하고 병합하세요.
3. 이 패치의 새 핵심은 `src/drawing_fileizers/`입니다.
4. 기존 placeholder였던 `corpus_learner.py`, `corpus_query.py`, `report_builder.py`는 이 패치의 extractor/knowledge_store와 연결하도록 병합하세요.
5. 원본 도면 폴더에는 절대 쓰지 말고 `outputs/` 아래에만 결과를 저장하세요.

## 권장 적용 순서

```bash
# 1) 현재 상태 확인
git status
git branch --show-current
git log --oneline -10
git diff --name-status

# 2) ZIP 압축 해제 후 overlay 복사
# Windows PowerShell 예시:
# Expand-Archive .\hs-cad_fileizer_corpus_patch.zip -DestinationPath .\_patch
# robocopy .\_patch\hs_cad_fileizer_corpus_patch . /E

# 3) 테스트
pytest tests/test_fileizer_registry.py tests/test_dxf_fileizer.py
pytest tests/test_material_extractor.py tests/test_specification_extractor.py tests/test_situation_extractor.py

# 4) CLI 연결 후 최종 테스트
python -m src.main fileizer-check
python -m src.main fileize --input tests/fixtures/corpus/sample.dxf --out outputs/fileized_test
python -m src.main corpus-query --kb outputs/corpus_test/cad_knowledge.sqlite --query "판넬 두께와 H빔 접합"
pytest
```

## 포함 내용

- `src/drawing_fileizers/`: DWG/DXF/PDF/이미지/IFC를 표준 JSON으로 파일화하는 모듈
- `src/corpus/`: 재료·규격·치수·상황·상세 패턴 추출기
- `src/company_profile/`: HS-CAD 내부 문서에서 회사 도면 문법을 추출하고 canonical 지식을 회사 출력 기준으로 매핑
- `src/app/cli_fileizer_commands.py`: 기존 Typer CLI에 붙일 수 있는 fileizer 명령 모듈
- `docs/21~27_*.md`: 문서
- `tests/`: 기본 테스트
