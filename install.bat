@echo off
title install
set SCRIPT_DIR=%~dp0
set PYZIP=%SCRIPT_DIR%python-embed.zip
set PYDIR=%SCRIPT_DIR%_python
set PYTHON=%PYDIR%\python.exe
set PIP=%PYDIR%\Scripts\pip.exe

echo ======================================
echo   Law News Auto - Install
echo ======================================
echo.

if not exist "%PYTHON%" (
    if not exist "%PYZIP%" (
        echo [ERROR] python-embed.zip not found. Re-download the full package.
        pause
        exit /b 1
    )
    echo [*] Extracting Python...
    powershell -Command "Expand-Archive -Path '%PYZIP%' -DestinationPath '%PYDIR%' -Force"
    if errorlevel 1 ( echo [ERROR] Extraction failed. & pause & exit /b 1 )
    for %%f in ("%PYDIR%\python3*._pth") do (
        powershell -Command "(Get-Content '%%f') -replace '#import site','import site' | Set-Content '%%f'"
    )
    echo [OK] Python ready.
) else (
    echo [OK] Python already exists.
)

if not exist "%PIP%" (
    echo [*] Downloading pip...
    powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYDIR%\get-pip.py' -UseBasicParsing"
    if errorlevel 1 ( echo [ERROR] pip download failed. & pause & exit /b 1 )
    "%PYTHON%" "%PYDIR%\get-pip.py" --no-warn-script-location -q
    del "%PYDIR%\get-pip.py" 2>nul
    echo [OK] pip ready.
) else (
    echo [OK] pip already exists.
)

echo [*] Installing dependencies...
"%PIP%" install -r "%SCRIPT_DIR%requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 ( echo [ERROR] Install failed. Check network. & pause & exit /b 1 )
echo [OK] Done.

if not exist "%SCRIPT_DIR%config.toml" (
    copy "%SCRIPT_DIR%config.example.toml" "%SCRIPT_DIR%config.toml" >nul
    echo [OK] config.toml created.
)

if not exist "%SCRIPT_DIR%output" mkdir "%SCRIPT_DIR%output"
if not exist "%SCRIPT_DIR%input" mkdir "%SCRIPT_DIR%input"

echo.
echo [Optional] Install Playwright browser (~150MB)? y=yes, Enter=skip
set /p INSTALL_PW=Choice:
if /i "%INSTALL_PW%"=="y" (
    "%PYDIR%\Scripts\playwright.exe" install chromium
)

echo [*] Creating desktop shortcut...
powershell -Command "$s=New-Object -com WScript.Shell;$lnk=$s.CreateShortcut([Environment]::GetFolderPath('Desktop')+'\法讯自动化.lnk');$lnk.TargetPath='%SCRIPT_DIR%法讯自动化.bat';$lnk.IconLocation='%SCRIPT_DIR%icon.ico';$lnk.WorkingDirectory='%SCRIPT_DIR%';$lnk.Save()"
echo [OK] Shortcut created.

echo.
echo ======================================
echo   Install complete!
echo ======================================
echo   1. Edit config.toml - fill in API Key
echo   2. Run: 法讯自动化.bat
echo   3. Open http://127.0.0.1:8000
echo.
pause