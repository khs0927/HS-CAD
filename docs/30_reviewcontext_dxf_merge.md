# 30. ReviewContext + DXF Fast Analysis Merge

이 단계는 지금까지 만든 ReviewContext / RuleViolation / ActionCandidate 흐름을 기존 HS-CAD의 no-COM DXF 분석 경로와 연결합니다.

## 목적

기존의 빠른 경로는 다음과 같습니다.

```text
DWG -> DXF 변환 -> ezdxf 파싱 -> fileized JSON -> SQLite/index/report
```

이번 브릿지는 그 뒤에 QA 계층을 추가합니다.

```text
fileized JSON -> FileizedReviewAdapter -> ReviewContext -> SpatialQueryService -> DomainReviewEngine -> ActionCandidate
```

## 핵심 원칙

- Python COM ModelSpace 전체 스캔을 기본 경로로 사용하지 않습니다.
- 기존 `DXFEzdxfFileizer`와 `DWGToDXFEzdxfFileizer`를 수정하지 않고 재사용합니다.
- 기존 ZWCAD COM 명령과 안전 실행 구조는 보존합니다.
- 이번 브릿지는 실제 CAD 파일을 수정하지 않습니다.
- 출력은 review report와 dry-run command plan까지만 생성합니다.

## 추가 파일

```text
src/integration/reviewcontext_dxf_merge.py
src/app/reviewcontext_dxf_cli.py
```

## 사용 예시

```powershell
python -m src.main hscad-qa review-fileized --input outputs/corpus_workspace/fileized/json/sample.json --out outputs/qa/review_report.json
python -m src.main hscad-qa review-dxf --dxf C:/cad/sample.dxf --out outputs/qa/review_report.json
python -m src.main hscad-qa resolve --review outputs/qa/review_report.json --out outputs/qa/command_plan_report.json
```

## 주의

현재 브랜치에서는 `src/main.py`에 `src.app.reviewcontext_dxf_cli`를 import하는 등록 한 줄이 필요합니다. 자동 수정 요청이 도구 안전 검사에 막혀서, PR 검토 시 아래 한 줄을 `src/main.py`의 다른 CLI import 아래에 추가하면 됩니다.

```python
import src.app.reviewcontext_dxf_cli  # noqa: F401,E402
```

이 한 줄이 추가되면 위 `hscad-qa` 명령이 기존 Typer 앱에 등록됩니다.
