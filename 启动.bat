@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PYW=%~dp0vendor\python\pythonw.exe"
set "PY=%~dp0vendor\python\python.exe"
set "RUN=%~dp0scripts\run_app.py"
set "SPLASH=%~dp0scripts\splash_process.py"
set "APP=%~dp0src\main.py"

rem 让本夹自带的 DLL 优先于系统里可能冲突的旧库
set "PATH=%~dp0vendor\python;%~dp0vendor\python\Lib\site-packages\PySide6;%~dp0vendor\python\Lib\site-packages\PySide6\plugins;%~dp0vendor\python\Lib\site-packages\PySide6\plugins\platforms;%PATH%"
set "QT_PLUGIN_PATH=%~dp0vendor\python\Lib\site-packages\PySide6\plugins"
set "QT_QPA_PLATFORM_PLUGIN_PATH=%~dp0vendor\python\Lib\site-packages\PySide6\plugins\platforms"

if not exist "%PYW%" (
  echo Portable Python missing. Trying to download into vendor\python ...
  echo 第一次启动要下载便携 Python 和界面库，请等它打印「完成」。
  echo.
  where py >nul 2>&1
  if %ERRORLEVEL%==0 (
    py -3 -u "%~dp0scripts\setup_portable_python.py"
  ) else (
    python -u "%~dp0scripts\setup_portable_python.py"
  )
  if errorlevel 1 (
    echo.
    echo 准备运行环境失败。可改双击「一键准备运行环境.bat」查看完整输出。
    pause
    exit /b 1
  )
)

if exist "%PYW%" if exist "%RUN%" (
  rem 先单独拉起一个闪屏进程（立刻有反馈，且不跟主程序 DPI 打架）
  if exist "%SPLASH%" (
    if exist "%~dp0data\splash.close" del /f /q "%~dp0data\splash.close" >nul 2>&1
    start "kongchang-splash" /D "%~dp0" "%PYW%" "%SPLASH%"
  )
  start "kongchang" /D "%~dp0" "%PYW%" "%RUN%"
  exit /b 0
)

if exist "%PYW%" if exist "%APP%" (
  start "kongchang" /D "%~dp0" "%PYW%" "%APP%"
  exit /b 0
)

echo 找不到 vendor\python\pythonw.exe。
echo 请拷贝整个「控场」文件夹，不要只拷 src；或双击「一键准备运行环境.bat」。
pause
exit /b 1
