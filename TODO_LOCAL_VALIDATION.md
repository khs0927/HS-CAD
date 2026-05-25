# HS-CAD Megapack Local Validation TODO

이 파일은 로컬 개발환경에서만 수행해야 하는 작업을 모아둔 체크리스트입니다.

## 전제

현재 원격 스택은 다음 순서입니다.

1. PR #66: `feature/main-code-pipeline-overlay`
2. PR #68: `feature/evidence-bridge-schema-golden`
3. PR #70: `feature/review-output-quality-v2`
4. Megapack branch: `feature/hs-cad-megapack-finalization`

## 로컬에서만 해야 하는 이유

다음 작업은 실제 파일 시스템, 전체 테스트 환경, optional dependency, runtime output 생성 여부 확인이 필요합니다.

- 전체 pytest 재실행
- ruff critical 재실행
- review output v7 구현 zip 적용
- runtime output 생성 후 commit 제외 확인
- 실제 CAD 파일을 열지 않는 범위에서 output 파일 구조 검사
- `_incoming/**`, `outputs/**`, cache, runtime artifact 정리

## 로컬 작업 순서

```powershell
cd C:\CODE\HS-CAD-main-code-overlay
git fetch origin --prune
git switch -c feature/hs-cad-megapack-finalization-local origin/feature/hs-cad-megapack-finalization
```

### 1. v7 zip 적용

다운로드 받은 zip:

```text
hs_cad_review_dxf_output_v7.zip
```

압축 해제:

```powershell
mkdir _incoming -Force
mkdir _incoming\review_output_v7 -Force
Expand-Archive -Path "$env:USERPROFILE\Downloads\hs_cad_review_dxf_output_v7.zip" -DestinationPath .\_incoming\review_output_v7 -Force
```

적용 후 테스트:

```powershell
python -X utf8 -m pytest -q tests/test_review_dxf_output_v7.py
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

### 2. runtime artifact 제외 확인

```powershell
git status --short
git status --short | findstr /R "outputs/ _incoming/ __pycache__ .pytest_cache .ruff_cache .zip .dwg .dxf .sqlite3"
```

아래는 커밋하지 않습니다.

```text
outputs/**
_incoming/**
__pycache__/**
.pytest_cache/**
.ruff_cache/**
*.zip
*.dwg
runtime *.dxf
*.sqlite3
```

### 3. stack PR 순서

```text
PR #66 merge
→ PR #68 retarget/merge
→ PR #70 retarget/merge
→ Megapack branch retarget/merge
→ v7 implementation PR
```

## 완료 보고 형식

```text
[HS-CAD Megapack Local Validation Result]

1. 작업 브랜치
-

2. 적용한 zip
-

3. 테스트 결과
- review output v7:
- ruff:
- src.main help:
- full pytest:

4. 생성 산출물
-

5. 커밋 제외 확인
-

6. 안전 확인
- 원본 입력 변경 없음:
- runtime output commit 없음:
```
