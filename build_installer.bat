@echo off
title AirBridge - Build Executable & Installer
cd /d "%~dp0"

echo =======================================================
echo   AirBridge Build & Packaging System
echo   Next-Gen Local AirDrop & Universal Clipboard Hub
echo   Created by Chathunga
echo =======================================================
echo.

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

:: 2. Check PyInstaller
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

:: 3. Clean previous build artifacts
echo [1/3] Cleaning previous build artifacts...
if exist "build" rd /s /q "build"
if exist "dist" rd /s /q "dist"

:: 4. Build Standalone Application via PyInstaller
echo [2/3] Compiling AirBridge standalone executable with PyInstaller...
python -m PyInstaller --clean --noconfirm AirBridge.spec
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller compilation failed!
    pause
    exit /b 1
)

:: 5. Compile Inno Setup Installer
echo [3/3] Compiling Inno Setup Setup Installer...
set "ISCC_PATH="
if exist "C:\Program Files\Inno Setup 7\ISCC.exe" set "ISCC_PATH=C:\Program Files\Inno Setup 7\ISCC.exe"
if not defined ISCC_PATH if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined ISCC_PATH (
    where iscc.exe >nul 2>&1
    if %errorlevel% equ 0 set "ISCC_PATH=iscc.exe"
)

if defined ISCC_PATH (
    echo Using Inno Setup Compiler: "%ISCC_PATH%"
    "%ISCC_PATH%" installer_script.iss
    if %errorlevel% equ 0 (
        echo.
        echo =======================================================
        echo   [SUCCESS] AirBridge-Setup-v1.1.0.exe generated!
        echo   Ready for GitHub Release!
        echo =======================================================
    ) else (
        echo [ERROR] Inno Setup compilation failed!
    )
) else (
    echo [WARNING] Inno Setup compiler (ISCC.exe) not found in standard paths.
    echo Standalone executable built successfully in: dist\AirBridge\AirBridge.exe
    echo Please install Inno Setup 6 or 7 to compile the setup wizard installer.
)

echo.
pause
