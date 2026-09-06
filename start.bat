@echo off
chcp 65001 >nul
title 法讯自动化

set SCRIPT_DIR=%~dp0
set PYTHON=%SCRIPT_DIR%_python\python.exe

if not exist "%PYTHON%" (
    echo [错误] 未找到 Python 运行环境，请先双击 install.bat 完成安装。
    pause
    exit /b 1
)

echo [*] 正在启动服务器...
echo [*] 稍后浏览器将自动打开，也可手动访问 http://127.0.0.1:8000
echo [*] 关闭此窗口即停止程序。
echo.

start /b cmd /c "timeout /t 2 >nul && start http://127.0.0.1:8000"

"%PYTHON%" "%SCRIPT_DIR%app.py"
