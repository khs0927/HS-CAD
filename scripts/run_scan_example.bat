@echo off
setlocal
if "%~1"=="" (
  echo Usage: scripts\run_scan_example.bat C:\cad\sample.dwg
  exit /b 1
)
python -m src.main scan --dwg "%~1" --out outputs\objects.json
python -m src.main layers --dwg "%~1"
python -m src.main blocks --dwg "%~1"
python -m src.main texts --dwg "%~1" --out outputs\texts.json
endlocal
