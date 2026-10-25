@echo off
rem Chuyen tu 2 tool cu (FacebookUpStt + FacebookMonitor) sang tool gop. Chay 1 lan. Can quyen Admin -> tu xin.
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chuyen_sang.ps1" -Action chuyen
echo.
pause
