@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=%~dp0vendor\python\python.exe"
set "PATH=%~dp0vendor\python;%~dp0vendor\python\Lib\site-packages\PySide6;%PATH%"
echo ===== 控场环境检测 =====
echo.
if not exist "%PY%" (
  echo 找不到 vendor\python\python.exe
  echo 请确认拷贝了整个「控场」文件夹。
  pause
  exit /b 1
)
"%PY%" "%~dp0scripts\diagnose.py"
echo.
echo 若上面有 FAIL：请先安装 VC++ x64 运行库
echo https://aka.ms/vs/17/release/vc_redist.x64.exe
echo.
echo 检测结果也写在 data\diagnose.txt
pause
