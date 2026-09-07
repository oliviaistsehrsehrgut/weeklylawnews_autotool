@echo off
title LawsNews
set SCRIPT_DIR=%~dp0
set BUNDLED=%SCRIPT_DIR%_python\python.exe

if exist "%BUNDLED%" (
    set PYTHON=%BUNDLED%
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found. Please run install.bat first.
        pause
        exit /b 1
    )
    set PYTHON=python
)

start http://127.0.0.1:8000
"%PYTHON%" "%SCRIPT_DIR%app.py"