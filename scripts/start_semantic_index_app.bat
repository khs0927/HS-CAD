@echo off
setlocal
cd /d "%~dp0\.."

if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)

%PYTHON% -m src.main semantic-index gui --db "outputs\semantic_index\semantic.sqlite3"
if errorlevel 1 (
  echo.
  echo HS-CAD Semantic Index failed to start.
  pause
)
endlocal
