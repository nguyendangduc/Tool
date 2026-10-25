@echo off
rem Quay lai dung 2 tool cu: xoa lich tool gop, bat lai lich FacebookUpStt + FacebookMonitor. Can quyen Admin -> tu xin.
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0chuyen_sang.ps1" -Action quaylai
echo.
pause
