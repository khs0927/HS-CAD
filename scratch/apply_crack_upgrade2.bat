@echo off
set INSTALL_DIR=C:\Program Files\ZWSOFT\ZWCAD 2026
set ZIP_FILE=C:\Users\user\AppData\Local\Temp\ZWCAD_2026_Eng_Win_64bit\msi\ZWCAD\ZWCAD.7z
set SEVEN_ZIP=C:\Users\user\AppData\Local\Temp\ZWCAD_2026_Eng_Win_64bit\7z.exe
set CRACK_DIR=C:\Users\user\Downloads\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64) [FileCR]\ZWCAD Professional 2026 v26.10 Build 2025.09.05 (x64)\crack

echo Extracting 26.8 DLLs...
"%SEVEN_ZIP%" x "%ZIP_FILE%" -o"%INSTALL_DIR%" -y -aoa > "c:\CODE\HS-CAD\scratch\7z_log.txt" 2>&1

echo Applying crack...
copy /y "%CRACK_DIR%\ZWCAD.exe" "%INSTALL_DIR%\ZWCAD.exe"
copy /y "%CRACK_DIR%\flxNetCommon.dll" "%INSTALL_DIR%\flxNetCommon.dll"

echo Done!
