# HS-CAD Windows 설치 및 배포

## 지원 환경

- Windows 10/11 64비트
- ZWCAD 2024, 2025 또는 2026 64비트
- 실제 DWG 수정은 ZWCAD COM/ActiveX가 정상 등록된 PC에서만 가능
- 설치본 사용자는 Python을 별도로 설치할 필요가 없음

## 일반 사용자 설치

1. GitHub Actions 또는 Release에서 `HS-CAD-Setup-<버전>.exe`를 내려받습니다.
2. 설치 파일을 실행합니다. 관리자 권한은 필요하지 않습니다.
3. 설치 후 PowerShell 또는 명령 프롬프트에서 다음을 실행합니다.

```powershell
hs-cad doctor
hs-cad --help
```

ZWCAD를 실행하고 도면을 하나 연 상태에서 COM 연결까지 확인하려면 다음을 실행합니다.

```powershell
hs-cad doctor --probe-com --strict
hs-cad connect
```

ZWCAD가 사용자 지정 폴더에 설치된 경우:

```powershell
$env:ZWCAD_EXE = "D:\ZWSOFT\ZWCAD 2026\ZWCAD.exe"
$env:ZWCAD_VERSION = "2026"
hs-cad doctor --probe-com
```

## 안전한 첫 테스트

원본 DWG가 아닌 복사본으로 먼저 실행합니다.

```powershell
hs-cad scan --dwg "C:\CAD\sample-copy.dwg" --out "C:\CAD\result\objects.json"
hs-cad run-command --dwg "C:\CAD\sample-copy.dwg" --command "examples\commands\move_layer.json" --dry-run
```

실제 실행은 `--execute`를 명시한 경우에만 수행합니다.

```powershell
hs-cad run-command `
  --dwg "C:\CAD\sample-copy.dwg" `
  --command "C:\CAD\commands\approved.json" `
  --execute `
  --save-as "C:\CAD\result\sample-modified.dwg"
```

## 개발자 설치

Python 3.11 권장:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python -m src.main doctor
```

## 단일 EXE 및 설치 프로그램 빌드

Inno Setup 6을 설치한 Windows PC에서 저장소 루트 PowerShell로 실행합니다.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_release.ps1 -Version 0.2.0
```

생성 파일:

- `dist\HS-CAD.exe`: Python이 필요 없는 포터블 단일 실행 파일
- `dist\HS-CAD.exe.sha256`: 무결성 확인값
- `dist\HS-CAD-Setup-0.2.0.exe`: 사용자별 설치 프로그램

설치 프로그램 없이 포터블 EXE만 만들려면:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows_release.ps1 -SkipInstaller
```

## GitHub Actions

- `CI` 워크플로는 Windows와 Linux에서 비-ZWCAD 단위 테스트를 실행합니다.
- `Build Windows Release` 워크플로는 포터블 EXE와 설치 EXE를 생성해 artifact로 보관합니다.
- `v*` 태그를 푸시하면 같은 빌드가 실행되며 배포용 artifact를 얻을 수 있습니다.

## 문제 해결

`doctor`에서 ZWCAD 설치는 보이지만 COM 연결이 실패하는 경우:

1. ZWCAD와 HS-CAD의 비트 수가 모두 64비트인지 확인합니다.
2. ZWCAD를 한 번 관리자 권한으로 실행했다가 종료합니다.
3. ZWCAD를 일반 권한으로 실행하고 도면을 연 뒤 `hs-cad doctor --probe-com`을 다시 실행합니다.
4. 여러 ZWCAD 버전이 설치된 경우 `ZWCAD_VERSION=2026`처럼 버전을 지정합니다.
5. 원격 자동화 전에 반드시 `--dry-run`과 복사본 DWG로 검증합니다.
