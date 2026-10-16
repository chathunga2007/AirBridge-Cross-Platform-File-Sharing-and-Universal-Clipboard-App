@echo off
title AirBridge Launcher
cd /d "%~dp0"

:: Look for pythonw.exe in standard paths or PATH
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw main.py
    exit /b 0
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    start "" python main.py
    exit /b 0
)

echo Python was not found in your PATH. Please install Python 3.11+.
pause
