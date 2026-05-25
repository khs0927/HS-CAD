@echo off
set INSTALL_DIR=C:\Program Files\ZWSOFT\ZWCAD 2026
set CRACK_DIR=C:\Users\user\Downloads\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64) [FileCR]\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64)\crack

taskkill /f /im ZWCAD.exe >nul 2>&1
copy /y "%CRACK_DIR%\ZWCAD.exe" "%INSTALL_DIR%\ZWCAD.exe"
copy /y "%CRACK_DIR%\flxNetCommon.dll" "%INSTALL_DIR%\flxNetCommon.dll"
