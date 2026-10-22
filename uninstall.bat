@echo off
chcp 65001 >nul
title Uninstall - Restore to initial state
cd /d "%~dp0"

echo ========================================
echo   Uninstall Local KBQA Assistant
echo   Target: Restore to initial state
echo ========================================
echo.
echo Project Directory: %CD%
echo.
echo Will clean the following:
echo   [venv]           Python virtual environment
echo   [data]           Vector DB and index
echo   [models]         Vosk speech model
echo   [.env]           Configuration
echo   [__pycache__]    Python cache
echo.
echo Will KEEP:
echo   Source code, requirements.txt, README.md,
echo   .env.example, .gitignore, documents/sample.txt
echo.
echo !! If you added your own documents to documents/,
echo    backup them first! Full restore will delete them.
echo.

set /p CONFIRM="Continue uninstallation? [y/N]: "
if /i not "%CONFIRM%"=="y" goto CANCEL
echo.

set "HAS_GIT=0"
set "HAS_GIT_REPO=0"

where git >nul 2>&1
if not errorlevel 1 set "HAS_GIT=1"
if exist ".git" set "HAS_GIT_REPO=1"

if "%HAS_GIT%"=="0" goto MANUAL
if "%HAS_GIT_REPO%"=="0" goto MANUAL

echo Found Git repository. Can use Git to restore.
set /p USE_GIT="Use Git full restore? [Y/n]: "
if /i "%USE_GIT%"=="n" goto MANUAL

echo.
echo [Git] Discarding local changes...
git reset --hard HEAD >nul 2>&1
echo [Git] Removing untracked files...
git clean -fdx
echo.
echo Restored to git clone state.
goto DONE

:MANUAL
echo.
echo [1/4] Removing runtime directories...
if exist venv rmdir /s /q venv
if exist data rmdir /s /q data
if exist models rmdir /s /q models

echo [2/4] Removing config files...
if exist .env del /q .env

echo [3/4] Cleaning cache...
if exist __pycache__ rmdir /s /q __pycache__
if exist code\__pycache__ rmdir /s /q code\__pycache__
for /r %%f in (*.pyc) do del /q "%%f" >nul 2>&1

echo [4/4] Cleaning user documents...
if exist documents (
    for %%f in (documents\*) do (
        if /i not "%%~nxf"=="sample.txt" del /q "%%f"
    )
)
echo.
echo Cleanup finished.
goto DONE

:CANCEL
echo Cancelled.
pause
exit /b 0

:DONE
echo.
echo ========================================
echo   Uninstallation complete.
echo   Project restored to initial state.
echo ========================================
echo.
echo To delete the project completely, remove the folder:
echo   %CD%
echo.
echo Notes:
echo   - Python and Ollama are NOT uninstalled.
echo   - Ollama models remain locally (run 'ollama list').
echo     To delete models used by this project:
echo     ollama rm deepseek-r1:8b
echo     ollama rm bge-m3
echo.
pause
exit /b 0