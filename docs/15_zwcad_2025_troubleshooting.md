# ZWCAD 2025 COM 테스트 문제 해결

## COM 연결 실패

증상:

```text
Failed to connect to ZWCAD COM. Is ZWCAD installed?
```

확인:

```powershell
python -m src.main env-check --start-zwcad
```

조치:

1. ZWCAD 2025을 직접 실행합니다.
2. PowerShell을 ZWCAD와 같은 권한 수준으로 실행합니다. 예: 둘 다 일반 권한 또는 둘 다 관리자 권한.
3. `ZWCAD.Application` ProgID가 등록되어 있는지 확인합니다.
4. 한 번 재부팅 후 다시 시도합니다.

## DWG 열기 실패

확인:

- 파일 경로가 맞는지
- 네트워크 드라이브가 아닌 로컬 경로인지
- 파일이 다른 사용자가 잠근 상태인지
- 한글/공백 경로 문제가 있는지

처음에는 다음처럼 단순한 경로를 권장합니다.

```text
C:\cad-test\sample.dwg
```

## 객체 스캔은 되지만 일부 속성이 비어 있음

ZWCAD COM 객체별로 제공하는 속성이 다를 수 있습니다. 이 경우 정상입니다. 프로그램은 없는 속성을 `None`으로 처리하고 계속 진행합니다.

## XiCAD 명령이 실행되지 않음

1. XiCAD를 ZWCAD에서 수동 로드했을 때 작동하는지 먼저 확인합니다.
2. `detect-xicad`로 폴더 구조를 확인합니다.
3. `xicad-catalog`로 alias가 파싱되는지 확인합니다.
4. XiCAD 대화형 명령은 SendCommand 이후 ZWCAD 화면에서 사용자가 이어서 입력해야 할 수 있습니다.

## 화면 캡처 실패

화면 캡처는 보조 기능입니다. 실패해도 CAD 객체 분석에는 영향이 없어야 합니다. 원격 데스크톱, 잠금 화면, 권한 문제로 실패할 수 있습니다.
