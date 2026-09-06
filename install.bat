@echo off
chcp 65001 >nul
title 法讯自动化 - 安装程序

set SCRIPT_DIR=%~dp0
set PYZIP=%SCRIPT_DIR%python-embed.zip
set PYDIR=%SCRIPT_DIR%_python
set PYTHON=%PYDIR%\python.exe
set PIP=%PYDIR%\Scripts\pip.exe

echo ======================================
echo   法讯自动化 - 安装程序
echo ======================================
echo.

REM --- 解压内置 Python ---
if not exist "%PYTHON%" (
    if not exist "%PYZIP%" (
        echo [错误] 未找到 python-embed.zip，请重新下载完整压缩包。
        pause
        exit /b 1
    )
    echo [*] 正在解压 Python 运行环境...
    powershell -Command "Expand-Archive -Path '%PYZIP%' -DestinationPath '%PYDIR%' -Force"
    if errorlevel 1 (
        echo [错误] 解压失败。
        pause
        exit /b 1
    )
    REM 启用 site-packages，让 pip 可以正常工作
    for %%f in ("%PYDIR%\python3*._pth") do (
        powershell -Command "(Get-Content '%%f') -replace '#import site','import site' | Set-Content '%%f'"
    )
    echo [OK] Python 运行环境准备完成。
) else (
    echo [OK] Python 运行环境已存在，跳过解压。
)

REM --- 初始化 pip ---
if not exist "%PIP%" (
    echo [*] 正在初始化 pip（需要联网，约 2MB）...
    powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%PYDIR%\get-pip.py' -UseBasicParsing"
    if errorlevel 1 (
        echo [错误] 下载 pip 失败，请检查网络连接后重试。
        pause
        exit /b 1
    )
    "%PYTHON%" "%PYDIR%\get-pip.py" --no-warn-script-location -q
    del "%PYDIR%\get-pip.py" 2>nul
    echo [OK] pip 初始化完成。
) else (
    echo [OK] pip 已存在，跳过初始化。
)

REM --- 安装依赖 ---
echo [*] 正在安装依赖（使用清华镜像，请耐心等待）...
"%PIP%" install -r "%SCRIPT_DIR%requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败，请检查网络连接后重试。
    pause
    exit /b 1
)
echo [OK] 依赖安装完成。

REM --- 初始化配置文件 ---
if not exist "%SCRIPT_DIR%config.toml" (
    copy "%SCRIPT_DIR%config.example.toml" "%SCRIPT_DIR%config.toml" >nul
    echo [OK] 已创建 config.toml，请用记事本填写 API Key 后再启动程序。
) else (
    echo [OK] config.toml 已存在，跳过初始化。
)

REM --- 创建必要目录 ---
if not exist "%SCRIPT_DIR%output" mkdir "%SCRIPT_DIR%output"
if not exist "%SCRIPT_DIR%input" mkdir "%SCRIPT_DIR%input"

REM --- 可选：Playwright 浏览器内核 ---
echo.
echo [可选] 是否安装 Playwright 浏览器内核？（约 150MB）
echo   作用：访问极少数会拒绝自动程序的网站时的兜底方案。
echo   如跳过，绝大多数网站（微信公众号、政府官网等）仍可正常抓取。
echo.
set /p INSTALL_PW=  直接回车跳过，输入 y 再回车安装：
if /i "%INSTALL_PW%"=="y" (
    echo [*] 正在下载 Chromium，请耐心等待...
    "%PYDIR%\Scripts\playwright.exe" install chromium
    if errorlevel 1 (
        echo [警告] 下载失败，可稍后手动运行：
        echo   _python\Scripts\playwright.exe install chromium
    ) else (
        echo [OK] Playwright 安装完成。
    )
) else (
    echo [跳过] 如需补装，运行：_python\Scripts\playwright.exe install chromium
)

echo.
echo ======================================
echo   安装完成！
echo ======================================
echo.
echo 接下来请：
echo   1. 用记事本打开 config.toml，填写 API Key 和模型名
echo   2. 双击 start.bat 启动程序
echo   3. 浏览器访问 http://127.0.0.1:8000
echo.
pause
