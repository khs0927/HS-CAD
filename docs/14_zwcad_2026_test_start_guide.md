# ZWCAD 2026 실테스트 시작 가이드

이 문서는 ZWCAD 2026이 설치된 Windows PC에서 `zwcad-ai-modifier`를 실제 DWG 도면과 연결해 검증하는 절차입니다.

## 1. 권장 폴더

```powershell
C:\cad-ai\zwcad-ai-modifier
C:\cad-test\sample.dwg
C:\xicad
```

원본 DWG는 직접 수정하지 말고 항상 복사본으로 테스트하세요.

## 2. Python 가상환경 설치

프로젝트 루트에서 실행합니다.

```powershell
cd C:\cad-ai\zwcad-ai-modifier
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\01_setup_venv.ps1
.\.venv\Scripts\Activate.ps1
```

수동 설치가 필요하면 다음을 사용하세요.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3. 먼저 ZWCAD를 수동 실행

COM 연결 확인 전 ZWCAD 2026을 한 번 직접 실행하세요.
빈 도면 하나를 열어둔 상태에서 아래를 실행하면 `GetActiveObject` 연결 성공 가능성이 높습니다.

```powershell
python -m src.main env-check --out-dir outputs/zwcad2026_env_check
```

ZWCAD를 자동으로 시작해도 괜찮다면:

```powershell
python -m src.main env-check --start-zwcad --out-dir outputs/zwcad2026_env_check
```

동일 기능을 독립 도구로 실행하려면:

```powershell
python tools/verify_zwcad2026_environment.py --start-zwcad --out-dir outputs/zwcad2026_env_check
```

결과 파일:

```text
outputs/zwcad2026_env_check/environment_check.json
outputs/zwcad2026_env_check/environment_check.md
```

확인할 핵심 항목:

- `comtypes` 사용 가능 여부
- `ZWCAD.Application` COM 연결 여부
- Python 경로
- Windows 버전
- XiCAD 경로 감지 여부

## 4. 샘플 DWG 스캔

```powershell
python -m src.main scan --dwg "C:/cad-test/sample.dwg" --out "outputs/objects.json"
```

생성된 `outputs/objects.json`에서 다음 객체들이 나오는지 확인합니다.

- LINE
- LWPOLYLINE / POLYLINE
- TEXT / MTEXT
- INSERT / BLOCKREFERENCE
- CIRCLE / ARC
- DIMENSION

## 5. 레이어 기반 객체 의미 분석

```powershell
python -m src.main classify-objects --dwg "C:/cad-test/sample.dwg" --out "outputs/object_semantics.json"
```

사용자 레이어 표준 기준으로 다음이 분류되는지 확인합니다.

- `COL`: 구조체
- `WAL1`: 경량벽체
- `WAL2`: 조적벽체
- `DOOR`: 문
- `WIN`: 창문
- `STAIR`: 계단
- `DIM`: 치수선
- `CEN/CEN1/CEN2`: 중심선
- `DEFPOINTS`: 출력 제외 가이드
- `A-FORM`: 도곽

## 6. 건축 분석 리포트 생성

```powershell
python -m src.main analyze-architecture --dwg "C:/cad-test/sample.dwg" --out-dir "outputs/architecture_report"
```

주요 출력:

```text
outputs/architecture_report/objects.json
outputs/architecture_report/object_semantics.json
outputs/architecture_report/semantic_summary.json
outputs/architecture_report/drawing_semantic_summary.md
outputs/architecture_report/quantity.xlsx
```

## 7. 디버그 번들 생성

문제가 생기면 이 명령으로 공유용 로그를 만듭니다.

```powershell
python -m src.main collect-debug --dwg "C:/cad-test/sample.dwg" --xicad-root "C:/xicad" --out-dir "outputs/debug_bundle"
```

전체 도면을 모두 저장하지 않고 최대 200개 객체 샘플만 저장합니다.

## 8. 안전 통합 테스트 플랜 실행

```powershell
python tools/run_zwcad2026_test_plan.py --dwg "C:/cad-test/sample.dwg" --xicad-root "C:/xicad" --start-zwcad --out-dir "outputs/zwcad2026_test_plan"
```

생성 결과:

```text
outputs/zwcad2026_test_plan/environment_check.json
outputs/zwcad2026_test_plan/objects.json
outputs/zwcad2026_test_plan/object_semantics.json
outputs/zwcad2026_test_plan/architecture_report/
outputs/zwcad2026_test_plan/debug_bundle/
outputs/zwcad2026_test_plan/test_plan_result.md
```

## 9. 복사본 DWG에서 최소 수정 테스트

이 테스트는 원본을 복사한 뒤 복사본만 수정합니다. 처음에는 이동량을 0으로 두고 저장 흐름만 확인하세요.

```powershell
python tools/run_zwcad2026_test_plan.py --dwg "C:/cad-test/sample.dwg" --start-zwcad --execute-smoke --move-layer MARK --dx 0 --dy 0
```

실제로 이동 테스트를 하려면 복사본에서만 작은 값을 사용하세요.

```powershell
python tools/run_zwcad2026_test_plan.py --dwg "C:/cad-test/sample.dwg" --start-zwcad --execute-smoke --move-layer MARK --dx 100 --dy 0
```

## 10. XiCAD 확인

```powershell
python -m src.main detect-xicad --xicad-root "C:/xicad"
python -m src.main xicad-catalog --xicad-root "C:/xicad"
```

XiCAD 로드는 복사본 DWG에서 진행하세요.

```powershell
python -m src.main load-xicad --dwg "C:/cad-test/sample_copy.dwg" --xicad-root "C:/xicad"
```

대화형 XiCAD 명령은 자동 입력이 아니라 ZWCAD 화면에서 사용자가 이어서 입력할 수 있습니다.

```powershell
python -m src.main run-xicad --dwg "C:/cad-test/sample_copy.dwg" --xicad-root "C:/xicad" --load-first --alias WAL
```

## 11. 문제가 생겼을 때 확인 순서

1. ZWCAD 2026을 수동 실행했는지 확인
2. `python -m src.main env-check --start-zwcad` 실행
3. `environment_check.md`의 COM probe 확인
4. 샘플 DWG 경로가 존재하는지 확인
5. 한글 경로에서 문제가 생기면 영문 경로로 복사해서 테스트
6. 관리자 권한 차이로 COM 연결이 실패하면 ZWCAD와 PowerShell 권한 수준을 맞춤
7. 백신/보안 정책이 COM 자동화를 막는지 확인

## 12. 다음에 개발자가 받아야 하는 결과물

테스트 후 아래 파일을 개발자에게 전달하면 문제 분석이 빨라집니다.

```text
outputs/zwcad2026_env_check/environment_check.json
outputs/debug_bundle/debug_summary.md
outputs/debug_bundle/zwcad_connection.json
outputs/objects.json
outputs/object_semantics.json
outputs/architecture_report/drawing_semantic_summary.md
```
