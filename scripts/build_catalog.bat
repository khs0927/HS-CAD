@echo off
setlocal
if "%~1"=="" (
  echo Usage: scripts\build_catalog.bat C:\path\to\xicad
  exit /b 1
)
python tools\build_xicad_catalog.py --xicad-root "%~1" --out-dir generated\xicad
python tools\install_xicad_support.py --xicad-root "%~1" --out generated\xicad\zwai_xicad_bootstrap.lsp
endlocal
