@echo off
setlocal enabledelayedexpansion

echo TwitchAdAvoider GUI Launcher
echo ============================

cd /d "%~dp0"

:: Check if Python is installed
python --version >nul 2>&1
if !errorlevel! neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.6+ from https://python.org
    pause
    exit /b 1
)

:: Check for existing virtual environments
set "VENV_PATH="
if exist "venv\pyvenv.cfg" (
    echo Using existing virtual environment: venv
    set "VENV_PATH=venv"
) else if exist ".venv\pyvenv.cfg" (
    echo Using existing virtual environment: .venv
    set "VENV_PATH=.venv"
) else (
    echo Creating virtual environment...
    python -m venv venv
    if !errorlevel! neq 0 (
        echo Error: Failed to create virtual environment
        pause
        exit /b 1
    )
    set "VENV_PATH=venv"
    echo Virtual environment created successfully
)

:: Activate virtual environment
echo Activating virtual environment...
call "%VENV_PATH%\Scripts\activate.bat"
if !errorlevel! neq 0 (
    echo Error: Failed to activate virtual environment
    pause
    exit /b 1
)

:: Install dependencies
if exist "requirements.txt" (
    echo Installing dependencies...
    pip install -r requirements.txt --quiet
    if !errorlevel! neq 0 (
        echo Warning: Some dependencies may not have installed correctly
    )
)

:: Check tkinter availability
echo Checking tkinter availability...
python -c "import tkinter; print('tkinter available')" >nul 2>&1
if !errorlevel! neq 0 (
    echo Error: tkinter is not available
    echo tkinter should be included with Python on Windows
    echo If you installed Python from python.org, tkinter should be available
    echo Try reinstalling Python with "Add Python to PATH" option checked
    pause
    exit /b 1
)

:: Launch GUI
echo Launching TwitchAdAvoider GUI...
echo ==================================
python run_gui.py

if !errorlevel! neq 0 (
    echo Error: GUI failed to start
    pause
    exit /b 1
)

echo GUI session completed
pause