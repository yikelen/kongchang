@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== 简易控场：准备便携运行环境 =====
echo 需要本机已安装任意 Python 3.11+（仅首次引导下载用）
echo.

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set "PYLAUNCH=py -3"
) else (
  where python >nul 2>&1
  if %ERRORLEVEL%==0 (
    set "PYLAUNCH=python"
  ) else (
    echo 未找到 Python。请先安装 Python 3.11+：
    echo https://www.python.org/downloads/
    echo 安装时勾选 Add python.exe to PATH
    pause
    exit /b 1
  )
)

echo [1/2] 下载便携 Python + PySide6 ...
%PYLAUNCH% "%~dp0scripts\setup_portable_python.py"
if errorlevel 1 (
  echo 失败：setup_portable_python.py
  pause
  exit /b 1
)

echo [2/2] 下载便携 mpv ...
%PYLAUNCH% "%~dp0scripts\download_mpv.py"
if errorlevel 1 (
  echo 失败：download_mpv.py
  pause
  exit /b 1
)

echo.
echo 完成。请双击 启动.bat
echo 演示工程：examples\demo_show.json （工程 → 打开）
pause
