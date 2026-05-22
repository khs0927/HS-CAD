# HS-CAD 운영 동기화 및 최종 도면 마감 프로세스

이 문서는 HS-CAD 작업을 시작할 때 GitHub 프로젝트를 안전하게 동기화하고, 도면 수정 후 문자 배치와 XiCAD 정렬까지 마무리하는 표준 절차입니다.

## 1. 실제 저장소 위치 확인

작업을 시작하기 전에 현재 폴더가 실제 Git 저장소인지 먼저 확인합니다. `C:\CODE\HS-CAD`처럼 상위 작업 폴더가 아니라, 실제 저장소인 `C:\CODE\HS-CAD\hs-cad`에서 명령을 실행해야 합니다.

```powershell
cd C:\CODE\HS-CAD\hs-cad
git rev-parse --show-toplevel
git remote -v
git status --short --branch
```

확인 기준:

- `git rev-parse --show-toplevel` 결과가 `C:/CODE/HS-CAD/hs-cad`여야 합니다.
- `origin`은 `https://github.com/khs0927/hs-cad.git` 또는 동일 프로젝트 원격을 가리켜야 합니다.
- `git status --short --branch`에서 예상하지 못한 로컬 변경이 없어야 합니다.

## 2. GitHub와 안전 동기화

작업 전에는 원격 상태를 먼저 가져오고, fast-forward 방식으로만 동기화합니다.

```powershell
git fetch origin
git log --oneline --left-right --graph HEAD...origin/main
git pull --ff-only origin main
```

운영 기준:

- 커밋 차이가 없으면 그대로 작업을 시작합니다.
- 원격이 앞서 있으면 `git pull --ff-only origin main`으로만 반영합니다.
- 로컬과 원격이 갈라져 있으면 즉시 병합하지 말고, 변경 내용을 확인한 뒤 별도 브랜치 또는 수동 병합 계획을 세웁니다.
- `C:\CODE\HS-CAD` 상위 폴더에서 Git 명령을 실행해 디스크 전체가 추적 후보로 잡히는 상태를 발견하면 작업을 중단하고 `C:\CODE\HS-CAD\hs-cad`로 이동합니다.

## 3. 도면 수정 전 준비

실제 DWG를 직접 수정하지 않고 복사본으로 작업합니다.

```powershell
python -m src.main connect
python -m src.main scan --dwg "C:/cad/sample_copy.dwg" --out "outputs/objects_before.json"
python -m src.main analyze-architecture --dwg "C:/cad/sample_copy.dwg" --out-dir "outputs/architecture_before"
```

준비 기준:

- ZWCAD COM 연결이 정상이어야 합니다.
- 수정 전 객체, 레이어, 블록, 문자 상태를 스캔해 기준 데이터를 남깁니다.
- XiCAD가 필요한 작업이면 먼저 XiCAD 경로와 로더를 확인합니다.

```powershell
python -m src.main detect-xicad --xicad-root "C:/xicad"
python -m src.main load-xicad --dwg "C:/cad/sample_copy.dwg" --xicad-root "C:/xicad"
```

## 4. 도면 수정 실행

자동 수정은 먼저 dry-run으로 계획을 검토한 뒤 실행합니다.

```powershell
python -m src.main run-command --dwg "C:/cad/sample_copy.dwg" --command "examples/commands/replace_text.json" --dry-run
python -m src.main run-command --dwg "C:/cad/sample_copy.dwg" --command "examples/commands/replace_text.json" --execute --save-as "C:/cad/sample_modified.dwg"
```

XiCAD 명령은 Safe Bridge 또는 명령 카탈로그에 등록된 alias만 사용합니다. 대화형 명령은 ZWCAD 화면에서 프롬프트를 확인하며 마무리합니다.

## 5. 마지막 문자 칸 맞춤 검증

수정이 끝나면 반드시 문자와 표/칸의 관계를 육안 및 스캔 결과로 검증합니다.

검증 항목:

- 모든 문자 객체가 의도한 칸, 표 셀, 도형 내부에 들어가 있는지 확인합니다.
- 긴 문자가 칸 경계선을 넘거나 다른 문자, 치수선, 지시선과 겹치지 않는지 확인합니다.
- 문자 기준점, 높이, 폭 비율, 회전각이 주변 도면 문법과 맞는지 확인합니다.
- 수정 후 스캔을 다시 실행해 전후 비교용 결과를 남깁니다.

```powershell
python -m src.main texts --dwg "C:/cad/sample_modified.dwg"
python -m src.main scan --dwg "C:/cad/sample_modified.dwg" --out "outputs/objects_after.json"
python -m src.main analyze-architecture --dwg "C:/cad/sample_modified.dwg" --out-dir "outputs/architecture_after"
```

합격 기준:

- 칸 안에 들어가야 하는 글자는 모두 칸 내부에 위치합니다.
- 좌측 정렬 대상은 좌측 기준선에 맞고, 중앙 정렬 대상은 칸 중심에 맞고, 우측 정렬 대상은 우측 기준선에 맞습니다.
- 문자 겹침, 칸 밖 이탈, 표 경계 침범이 남아 있지 않습니다.

## 6. XiCAD TOA 문자 정렬 마감

최종 마감 단계에서 XiCAD 단축어 `TOA`를 사용해 문자 정렬을 완료합니다. 현재 XiCAD 카탈로그에서 `TOA`는 "문자열을 도형의 중심에 일괄 정렬" 명령으로 확인됩니다.

기본 실행:

```powershell
python -m src.main run-xicad --dwg "C:/cad/sample_modified.dwg" --xicad-root "C:/xicad" --load-first --alias TOA
```

정렬 운영 방식:

- 좌측 정렬: 좌측 정렬이 필요한 문자와 기준 도형/칸을 선택하고, ZWCAD 명령줄의 TOA 프롬프트에서 좌측 기준을 적용합니다.
- 중앙 정렬: 표 셀, 박스, 도형 중심에 맞출 문자를 선택하고, TOA로 중심 기준 정렬을 적용합니다.
- 우측 정렬: 우측 경계 기준으로 붙어야 하는 문자와 기준 칸을 선택하고, TOA 프롬프트에서 우측 기준을 적용합니다.

주의 사항:

- TOA는 대화형 XiCAD 명령이므로 실행 후 ZWCAD 화면의 프롬프트를 확인하며 선택과 옵션 입력을 완료합니다.
- 한 번에 전체 도면을 선택하지 말고, 좌측/중앙/우측 정렬 그룹을 나누어 처리합니다.
- TOA 실행 후 다시 문자 칸 맞춤 검증을 수행합니다.

## 7. 완료 확인

최종 완료 전에 아래 항목을 확인합니다.

```powershell
git status --short --branch
```

완료 기준:

- 작업 산출 DWG는 원본이 아닌 복사본 또는 명시한 `save-as` 파일입니다.
- 수정 전/후 스캔 또는 리포트가 남아 있습니다.
- 문자 칸 맞춤 검증과 TOA 좌측/중앙/우측 정렬이 완료되었습니다.
- 코드나 문서 변경이 있었다면 Git 상태를 확인하고 필요한 파일만 커밋 대상으로 분리합니다.
