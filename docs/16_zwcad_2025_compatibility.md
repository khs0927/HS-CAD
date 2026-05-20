# ZWCAD 2025 호환성 정리

이 패키지는 ZWCAD 2025를 기본 테스트 대상으로 다시 정리한 버전입니다. 기존 ZWCAD 2026용 도구도 남겨 두어 2025/2026 모두 확인할 수 있습니다.

## 핵심 변경

- COM ProgID 후보에 `ZWCAD.Application.2025`를 추가했습니다.
- 기본 환경 점검 출력 폴더를 `outputs/zwcad2025_env_check`로 변경했습니다.
- `tools/verify_zwcad2025_environment.py`를 추가했습니다.
- `tools/run_zwcad2025_test_plan.py`를 추가했습니다.
- ZWCAD 2025용 PowerShell wrapper를 추가했습니다.
- ZWCAD 2025 시작/문제 해결 문서를 추가했습니다.

## 권장 시작 명령

```powershell
cd C:\cad-ai\zwcad-ai-modifier
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\01_setup_venv.ps1
.\.venv\Scripts\Activate.ps1
python -m src.main env-check --start-zwcad --out-dir outputs/zwcad2025_env_check
python tools\verify_zwcad2025_environment.py --start-zwcad --out-dir outputs/zwcad2025_env_check
```

## 안전 테스트 플랜

```powershell
python tools\run_zwcad2025_test_plan.py --dwg "C:/cad-test/sample.dwg" --start-zwcad --out-dir "outputs/zwcad2025_test_plan"
```

## 복사본 최소 수정 테스트

```powershell
python tools\run_zwcad2025_test_plan.py --dwg "C:/cad-test/sample.dwg" --start-zwcad --execute-smoke --move-layer MARK --dx 0 --dy 0
```

원본 DWG는 수정하지 않고 복사본에서만 테스트합니다.
# ZWCAD 2025/2026 Compatibility Notes

The current adapter and environment checker support shared and versioned ProgIDs:

- `ZWCAD.Application`
- `ZwCAD.Application`
- `ZWCAD.Application.2025`
- `ZwCAD.Application.2025`
- `ZWCAD.Application.2026`
- `ZwCAD.Application.2026`

`--version 2025` prioritizes the 2025 ProgIDs. `--version 2026` prioritizes the 2026 ProgIDs. Without `--start-zwcad`, the checker only attaches to an active instance. With `--start-zwcad`, it may create a new COM instance.

Use:

```powershell
python -m src.main env-check --version 2025 --out-dir outputs/zwcad2025_env_check
python -m src.main env-check --version 2026 --start-zwcad --out-dir outputs/zwcad2026_env_check
```

If COM fails, run ZWCAD once as administrator, confirm Python and ZWCAD are both 64-bit, then retry. If multiple ZWCAD versions are installed, always pass the intended `--version`.
