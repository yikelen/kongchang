@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 从 GitHub 更新简易控场源码（不下载 Python/mpv，不改 data）...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update_from_github.ps1"
echo.
pause
