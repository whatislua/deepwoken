@echo off
rem Runs Elgansito Demolisher Macro straight from the Python files in this folder - no exe,
rem so antivirus has nothing to flag. First run installs Python 3.12 (from Microsoft's winget)
rem and the libraries in requirements.txt into %LOCALAPPDATA%\ElgansitoDemolisher\venv
rem (a short path: PySide6's deep folders break Windows' 260-character path limit otherwise).
title Elgansito Demolisher Macro
cd /d "%~dp0"
set "VENV=%LOCALAPPDATA%\ElgansitoDemolisher\venv"

where py >nul 2>nul
if errorlevel 1 (
    echo Python isn't installed - installing Python 3.12 with winget...
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    echo.
    echo Python installed. Close this window and double-click "Run from source.bat" again.
    pause
    exit /b
)

if not exist "%VENV%\Scripts\python.exe" (
    echo First run: setting up, this takes a few minutes...
    py -3.12 -m venv "%VENV%" || py -3 -m venv "%VENV%"
)
echo Checking libraries...
"%VENV%\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 (
    echo Installing the libraries failed - check your internet connection and try again.
    pause
    exit /b
)
start "" "%VENV%\Scripts\pythonw.exe" app.py
