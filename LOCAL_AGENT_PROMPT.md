너는 내 로컬 HS-CAD 저장소에서 `main-code overlay v5`를 안전하게 적용하고 검증하는 코딩 에이전트다.

현재 상황:
- v1/v2/v3는 `C:\CODE\HS-CAD-main-code-overlay` / `feature/main-code-pipeline-overlay`에서 검증 완료.
- v3 기준 full pytest는 `222 passed, 16 skipped`.
- v4는 review-only CLI 통합 및 PR hygiene 패치로 생성되었다.
- 이번 v5는 PR 커밋 직전 finalization 패치다.
- PR #58 worktree와 기존 `C:\CODE\HS-CAD`는 건드리지 않는다.
- 커밋/푸시는 내가 명시적으로 요청하기 전까지 하지 않는다.

이번 v5 목표:
1. PR readiness validator를 추가한다.
2. runtime artifact, cache, zip, DWG, runtime DXF가 커밋 후보에 섞였는지 차단한다.
3. PR body generator를 추가한다.
4. v5 테스트를 추가한다.
5. PR 제출 전 보고서를 생성한다.
6. 커밋/푸시는 하지 않고 결과 보고서만 작성한다.

절대 금지:
- PR #58 worktree 수정 금지
- 기존 `C:\CODE\HS-CAD` 미추적 파일 삭제 금지
- CAD 실행 금지
- ZWCAD COM 호출 금지
- SendCommand 실행 금지
- XiCAD alias 실행 금지
- original DWG mutation 금지
- outputs/** 커밋 금지
- _incoming/** 커밋 금지
- .zip, .dwg, runtime .dxf, __pycache__, .pytest_cache 커밋 금지

작업 순서:

```powershell
cd C:\CODE\HS-CAD-main-code-overlay
git status --short
git branch --show-current
```

zip 찾기:

```powershell
Get-ChildItem -Path C:\CODE, $env:USERPROFILE\Downloads -Filter hs_cad_main_code_overlay_v5.zip -Recurse -ErrorAction SilentlyContinue
```

압축 해제:

```powershell
mkdir _incoming -Force
mkdir _incoming\main_code_overlay_v5 -Force
Expand-Archive -Path "<찾은 zip 경로>\hs_cad_main_code_overlay_v5.zip" -DestinationPath .\_incoming\main_code_overlay_v5 -Force
```

Dry-run:

```powershell
python -X utf8 .\_incoming\main_code_overlay_v5\scripts\apply_hscad_main_code_overlay_v5.py `
  --overlay .\_incoming\main_code_overlay_v5 `
  --repo-root . `
  --dry-run
```

실제 적용:

```powershell
python -X utf8 .\_incoming\main_code_overlay_v5\scripts\apply_hscad_main_code_overlay_v5.py `
  --overlay .\_incoming\main_code_overlay_v5 `
  --repo-root .
```

v5 targeted tests:

```powershell
python -X utf8 -m pytest -q tests/test_pr_readiness_v5.py
```

PR readiness 검사:

```powershell
python -X utf8 scripts\validate_hscad_pr_ready.py --repo-root .
```

주의:
- 현재 `_incoming/**`, `outputs/**`, cache가 남아 있으면 이 명령은 실패하는 것이 정상이다.
- 실패하면 금지 파일 목록을 확인하고, 커밋 후보에서 제외해야 한다.
- 실제 삭제는 내가 요청하기 전까지 하지 말고, 먼저 보고하라.

PR body 생성:

```powershell
python -X utf8 scripts\generate_hscad_pr_body.py --repo-root . --out docs\35_main_code_overlay_pr_body.md
```

전체 검증:

```powershell
python -m ruff check . --select F821,E9,F63,F7,F82
python -X utf8 -m src.main --help
python -X utf8 -m pytest -q
```

커밋 후보 확인:

```powershell
git status --short
git diff --stat
```

보고 형식:

```text
[HS-CAD main-code overlay v5 적용 결과]

1. 작업 경로
-

2. 브랜치
-

3. 적용 파일
- 신규:
- 수정:
- 삭제:
- 충돌/미적용:

4. v5 검증
- v5 targeted tests:
- PR readiness validator:
- PR body generator:
- ruff critical:
- src.main help:
- full pytest:

5. PR body
- 생성 파일:
- 권장 PR title:

6. 커밋 금지 파일 감지
- outputs/**:
- _incoming/**:
- *.zip:
- *.dwg:
- runtime *.dxf:
- cache:
- sqlite:

7. 커밋 후보 정리 필요 사항
-

8. 안전 확인
- CAD 실행 없음:
- ZWCAD COM 호출 없음:
- SendCommand 없음:
- XiCAD alias 없음:
- original DWG mutation 없음:
- safety flags false 유지:

9. 커밋/푸시 여부
- 아직 커밋하지 않음
- 아직 푸시하지 않음
```

작업 완료 후 커밋/푸시하지 말고 보고서만 작성한 뒤 멈춰라.
