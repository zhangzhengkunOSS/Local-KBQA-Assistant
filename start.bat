@echo off
chcp 65001 >nul
title Local KBQA Assistant
cd /d "%~dp0"

echo ========================================
echo   Local Knowledge Base Assistant
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 goto NO_PYTHON

if not exist "venv\Scripts\python.exe" goto CREATE_VENV
goto ACTIVATE_VENV

:CREATE_VENV
echo [1/4] Creating virtual environment...
python -m venv venv
if errorlevel 1 goto VENV_FAIL

:ACTIVATE_VENV
call venv\Scripts\activate.bat

if exist "venv\.installed" goto SKIP_PIP

echo [2/4] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 goto PIP_FAIL
echo done > venv\.installed
goto INIT_PROJECT

:SKIP_PIP
echo [2/4] Dependencies already installed, skipping...

:INIT_PROJECT
echo [3/4] Checking environment and knowledge base...
python init_project.py
if errorlevel 1 goto INIT_FAIL

echo [4/4] Starting server and opening browser...
start "" "http://127.0.0.1:8000"
python code\web_server.py
pause
exit /b 0

:NO_PYTHON
echo [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:VENV_FAIL
echo [ERROR] Failed to create virtual environment.
pause
exit /b 1

:PIP_FAIL
echo [ERROR] Failed to install dependencies. Please check your network.
pause
exit /b 1

:INIT_FAIL
echo [ERROR] Initialization failed. Please check the output above.
pause
exit /b 1