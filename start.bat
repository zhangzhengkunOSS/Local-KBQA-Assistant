@echo off
chcp 65001 >nul
title 本地私有知识库问答助手
cd /d "%~dp0"

echo ========================================
echo   本地私有知识库语音问答助手
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10 或更高版本
    echo 即将为你打开下载页面，安装时请务必勾选 "Add Python to PATH"
    start "" "https://www.python.org/downloads/"
    pause
    exit /b 1
)

if not exist "venv" (
    echo [1/4] 正在创建 Python 虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 虚拟环境创建失败
        pause
        exit /b 1
    )
)

call venv\Scripts\activate.bat

if not exist "venv\.installed" (
    echo [2/4] 正在安装依赖（首次运行，请耐心等待）...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络
        pause
        exit /b 1
    )
    echo done > venv\.installed
) else (
    echo [2/4] 依赖已安装，跳过
)

echo [3/4] 正在检查环境与知识库...
python init_project.py
if errorlevel 1 (
    echo.
    echo 初始化未完成，请按上面的提示处理后重新运行
    pause
    exit /b 1
)

echo [4/4] 启动服务并打开浏览器...
start "" "http://127.0.0.1:8000"
python code\web_server.py

pause