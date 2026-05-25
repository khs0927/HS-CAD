@echo off
set "INSTALL_DIR=C:\Program Files\ZWSOFT\ZWCAD 2026"
set "EXTRACT_DIR=c:\CODE\HS-CAD\scratch\temp_extract"

taskkill /f /im ZWCAD.exe >nul 2>&1
copy /y "%EXTRACT_DIR%\ZWCAD.exe" "%INSTALL_DIR%\ZWCAD.exe"
