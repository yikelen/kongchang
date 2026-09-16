"""创建带软件图标的 .lnk，方便从桌面启动。"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from src.paths import app_root

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _icon_path() -> Path:
    root = app_root()
    for name in ("app_v3.ico", "app.ico"):
        path = root / "assets" / name
        if path.exists():
            return path
    return root / "assets" / "app_v3.ico"


def _desktop_dir() -> Path:
    for key in ("USERPROFILE", "HOME"):
        raw = os.environ.get(key, "").strip()
        if raw:
            desktop = Path(raw) / "Desktop"
            if desktop.is_dir():
                return desktop
    return Path.home() / "Desktop"


def create_shortcuts() -> tuple[Path, Path]:
    """桌面一份、软件目录一份。返回 (桌面lnk, 本地lnk)。"""
    root = app_root()
    bat = root / "启动.bat"
    if not bat.exists():
        raise OSError(f"找不到启动脚本：{bat}")
    icon = _icon_path()
    desktop = _desktop_dir()
    desktop.mkdir(parents=True, exist_ok=True)
    desktop_lnk = desktop / "简易控场.lnk"
    local_lnk = root / "简易控场.lnk"

    def _q(path: Path) -> str:
        return str(path).replace("'", "''")

    script = f"""
$ws = New-Object -ComObject WScript.Shell
function Write-Lnk($path) {{
  $s = $ws.CreateShortcut($path)
  $s.TargetPath = '{_q(bat)}'
  $s.WorkingDirectory = '{_q(root)}'
  $s.WindowStyle = 7
  $s.Description = '简易控场'
  $s.IconLocation = '{_q(icon)},0'
  $s.Save()
}}
Write-Lnk '{_q(desktop_lnk)}'
Write-Lnk '{_q(local_lnk)}'
"""
    subprocess.check_call(
        ["powershell", "-NoProfile", "-STA", "-Command", script],
        creationflags=_CREATE_NO_WINDOW,
    )
    if not desktop_lnk.exists() and not local_lnk.exists():
        raise OSError("快捷方式没有写出来，请检查是否允许创建 .lnk")
    return desktop_lnk, local_lnk
