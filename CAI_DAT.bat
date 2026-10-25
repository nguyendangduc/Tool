@echo off
rem Cai dat / sua loi tool: cai phan con thieu, dang nhap neu can, cap nhat lich chay.
rem Can quyen Admin de tao lich -> tu xin quyen neu chua co.
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
title Cai dat tool Facebook
cd /d "%~dp0"
echo.
echo  ============================================================
echo   CAI DAT / SUA LOI TOOL
echo   - Lan dau dung tool
echo   - Khi tool bi loi, bi vang dang nhap
echo  ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -Action install
echo.
pause
