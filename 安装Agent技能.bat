@echo off
setlocal
chcp 65001 >nul
"%~dp0vendor\python\python.exe" "%~dp0scripts\install_kongchang_skill.py"
echo.
pause
