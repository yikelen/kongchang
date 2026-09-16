@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%~dp0vendor\python\python.exe"
if exist "%PY%" (
  "%PY%" -c "from src.shortcut import create_shortcuts; d,l=create_shortcuts(); print('桌面:', d); print('本夹:', l)"
) else (
  py -3 -c "from src.shortcut import create_shortcuts; d,l=create_shortcuts(); print('桌面:', d); print('本夹:', l)"
)
if errorlevel 1 (
  echo 创建失败。
  pause
  exit /b 1
)
echo.
echo 已在桌面和本文件夹生成「简易控场」图标。
pause
