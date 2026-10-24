@echo off
title ForgetGuard - Space Sentinel Hub
color 0A
echo ===================================================
echo     FORGETGUARD - IoT EDGE & CLOUD SENTINEL HUB
echo ===================================================
echo.
echo [1/2] Verifying Python Environment...
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXEC=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXEC=python"
)

echo [2/2] Launching ForgetGuard Web Server on http://127.0.0.1:5000 ...
echo.
echo Default Admin Credentials:
echo   Username: admin
echo   Password: admin123
echo.
echo Press Ctrl+C in this terminal window to stop the server.
echo ===================================================
echo.
start http://127.0.0.1:5000
%PYTHON_EXEC% app.py
pause
