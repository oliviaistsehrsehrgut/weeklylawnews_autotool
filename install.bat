@echo off
chcp 65001 >nul
title 法讯自动化 - 安装程序
echo ======================================
echo   法讯自动化 - 安装程序
echo ======================================
echo.

REM --- 检查 Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.9 或更高版本。
    echo        下载地址：https://www.python.org/downloads/
    echo        安装时请勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

python -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>nul
if errorlevel 1 (
    echo [错误] Python 版本过低，请安装 3.9 或更高版本。
    python --version
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo [OK] 检测到 %%i

REM --- 创建虚拟环境 ---
if not exist .venv (
    echo [*] 正在创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境已创建。
) else (
    echo [OK] 虚拟环境已存在，跳过创建。
)

REM --- 安装依赖 ---
echo [*] 正在安装依赖（使用清华镜像，请耐心等待）...
.venv\Scripts\pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple -q
.venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败，请检查网络连接后重试。
    pause
    exit /b 1
)
echo [OK] 依赖安装完成。

REM --- 初始化配置文件 ---
if not exist config.toml (
    copy config.example.toml config.toml >nul
    echo [OK] 已创建 config.toml，请用记事本填写 API Key 后再启动程序。
) else (
    echo [OK] config.toml 已存在，跳过初始化。
)

REM --- 创建必要目录 ---
if not exist output mkdir output
if not exist input mkdir input

REM --- 可选：Playwright 浏览器内核 ---
echo.
echo [可选] 是否安装 Playwright 浏览器内核？（约 150MB）
echo   作用：访问极少数会拒绝自动程序的网站时的兜底方案。
echo   如跳过，绝大多数网站（微信公众号、政府官网等）仍可正常抓取。
echo.
set /p INSTALL_PW=  直接回车跳过，输入 y 再回车安装：
if /i "%INSTALL_PW%"=="y" (
    echo [*] 正在下载 Chromium，请耐心等待（可能需要数分钟）...
    .venv\Scripts\playwright install chromium
    if errorlevel 1 (
        echo [警告] 下载失败，可稍后手动运行以下命令补装：
        echo   .venv\Scripts\playwright install chromium
    ) else (
        echo [OK] Playwright 安装完成。
    )
) else (
    echo [跳过] 如需补装，运行：.venv\Scripts\playwright install chromium
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
