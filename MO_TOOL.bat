@echo off
rem Mo giao dien tool: cau hinh, dang nhap / doi / dang xuat tai khoan, xem nhat ky, tam dung.
rem Can quyen Admin de cap nhat lich chay khi bam Luu -> tu xin quyen neu chua co.
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -Action gui
if errorlevel 1 (echo. & echo  Chua cai dat tool. Hay chay CAI_DAT.bat truoc. & echo. & pause)
