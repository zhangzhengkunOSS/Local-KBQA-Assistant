@echo off
chcp 65001 >nul
title 卸载 - 恢复到初始状态
cd /d "%~dp0"

echo ========================================
echo   卸载本地私有知识库语音问答助手
echo   目标：恢复到下载/克隆后的初始状态
echo ========================================
echo.
echo 项目目录: %CD%
echo.
echo 将清理的运行时产物：
echo   [venv]           Python 虚拟环境
echo   [data]           知识库向量与索引
echo   [models]         Vosk 语音模型
echo   [.env]           配置文件
echo   [__pycache__]    Python 缓存
echo.
echo 将保留：
echo   源代码、requirements.txt、README.md、
echo   .env.example、.gitignore、documents/sample.txt
echo.
echo ^!^! 如果你往 documents/ 里添加过自己的文档，
echo     请先备份！选择完全恢复会删除它们。
echo.

set /p CONFIRM="继续卸载？[y/N]: "
if /i not "%CONFIRM%"=="y" (
    echo 已取消
    pause
    exit /b 0
)
echo.

set "HAS_GIT=0"
set "HAS_GIT_REPO=0"
where git >nul 2>&1
if not errorlevel 1 set "HAS_GIT=1"
if exist ".git" set "HAS_GIT_REPO=1"

if "%HAS_GIT%"=="1" if "%HAS_GIT_REPO%"=="1" (
    echo 检测到 Git 仓库，可用 Git 精确还原到 clone 状态。
    set /p USE_GIT="使用 Git 完全恢复？[Y/n]: "
    if /i not "%USE_GIT%"=="n" (
        call :do_git_restore
        goto :done
    )
)

call :do_manual_restore
goto :done

:do_git_restore
echo.
echo [Git 恢复] 丢弃所有本地修改...
git reset --hard HEAD >nul 2>&1
echo [Git 恢复] 删除所有未跟踪文件（含 ignored）...
git clean -fdx
echo.
echo 已恢复到 git clone 时的状态
exit /b 0

:do_manual_restore
echo.
echo [1/4] 删除运行时目录...
if exist venv rmdir /s /q venv
if exist data rmdir /s /q data
if exist models rmdir /s /q models

echo [2/4] 删除配置文件...
if exist .env del /q .env

echo [3/4] 清理缓存...
if exist __pycache__ rmdir /s /q __pycache__
if exist code\__pycache__ rmdir /s /q code\__pycache__
for /r %%f in (*.pyc) do del /q "%%f" >nul 2>&1

echo [4/4] 清理 documents 下用户添加的内容...
if exist documents (
    for /f "delims=" %%f in ('dir /b /a-d "documents\*" 2^>nul') do (
        if /i not "%%f"=="sample.txt" del /q "documents\%%f"
    )
    for /f "delims=" %%d in ('dir /b /ad "documents\*" 2^>nul') do (
        rmdir /s /q "documents\%%d"
    )
)
echo.
echo 已清理完毕
exit /b 0

:done
echo.
echo ========================================
echo   卸载完成，项目已恢复到初始状态
echo ========================================
echo.
echo 如需彻底删除项目，请手动删除文件夹：
echo   %CD%
echo.
echo 提示：
echo   - Python 与 Ollama 本体不会自动卸载
echo   - Ollama 模型仍在本地，可通过 ollama list 查看
echo     如需删除本项目用过的模型，运行：ollama rm 模型名
echo.
pause
exit /b 0