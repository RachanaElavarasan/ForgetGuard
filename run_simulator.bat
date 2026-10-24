@echo off
title ForgetGuard - ESP32 Hardware Simulator
color 0B
echo ===================================================
echo     FORGETGUARD - ESP32 SENSOR SIMULATOR
echo ===================================================
echo.
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXEC=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXEC=python"
)

echo Broadcasting continuous telemetry to http://127.0.0.1:5000 ...
echo Press Ctrl+C at any time to halt simulator.
echo ===================================================
echo.
%PYTHON_EXEC% simulate\simulate.py --loop
pause
