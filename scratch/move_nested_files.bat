@echo off
set "INSTALL_DIR=C:\Program Files\ZWSOFT\ZWCAD 2026"
set "NESTED_DIR=C:\Program Files\ZWSOFT\ZWCAD 2026\ZWCAD 2026"
set "CRACK_DIR=C:\Users\user\Downloads\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64) [FileCR]\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64)\crack"

echo Moving files from nested directory...
xcopy /s /e /y "%NESTED_DIR%\*" "%INSTALL_DIR%\" > "c:\CODE\HS-CAD\scratch\move_log.txt" 2>&1

echo Applying crack...
copy /y "%CRACK_DIR%\ZWCAD.exe" "%INSTALL_DIR%\ZWCAD.exe"
copy /y "%CRACK_DIR%\flxNetCommon.dll" "%INSTALL_DIR%\flxNetCommon.dll"

echo Cleaning up nested directory...
rmdir /s /q "%NESTED_DIR%"

echo Done!
