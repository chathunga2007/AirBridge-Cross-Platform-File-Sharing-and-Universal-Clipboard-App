@echo off
title AirBridge - Cross-Device Hub
echo Starting AirBridge by Chathunga...
python main.py
if errorlevel 1 (
    echo.
    echo An error occurred while running AirBridge.
    pause
)
