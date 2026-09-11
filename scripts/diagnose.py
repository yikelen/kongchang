# -*- coding: utf-8 -*-
"""环境检测：在打不开的电脑上双击 环境检测.bat，把输出发回即可。"""
from __future__ import annotations

import os
import platform
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_DIR = ROOT / "vendor" / "python"
PYSIDE = PY_DIR / "Lib" / "site-packages" / "PySide6"


def main() -> int:
    lines: list[str] = []
    lines.append(f"ROOT = {ROOT}")
    lines.append(f"Python exe = {sys.executable}")
    lines.append(f"Python = {sys.version}")
    lines.append(f"Platform = {platform.platform()} / {platform.machine()}")
    lines.append(f"Windows = {platform.win32_ver()}")
    lines.append("")

    checks = [
        PY_DIR / "pythonw.exe",
        PY_DIR / "python312.dll",
        PY_DIR / "vcruntime140.dll",
        PY_DIR / "vcruntime140_1.dll",
        PY_DIR / "msvcp140.dll",
        PYSIDE / "QtWidgets.pyd",
        PYSIDE / "Qt6Widgets.dll",
        PYSIDE / "Qt6Gui.dll",
        PYSIDE / "Qt6Core.dll",
        PYSIDE / "d3dcompiler_47.dll",
        PYSIDE / "plugins" / "platforms" / "qwindows.dll",
    ]
    lines.append("文件检查：")
    for p in checks:
        lines.append(f"  [{'OK' if p.exists() else '缺'}] {p.relative_to(ROOT)}")
    lines.append("")

    # DLL 目录
    dirs = [PY_DIR, PYSIDE, PYSIDE / "plugins", PYSIDE / "plugins" / "platforms"]
    for d in dirs:
        if d.is_dir():
            try:
                os.add_dll_directory(str(d))
                lines.append(f"add_dll_directory OK: {d}")
            except Exception as exc:
                lines.append(f"add_dll_directory FAIL: {d} -> {exc}")
    lines.append("")

    lines.append("import PySide6.QtWidgets …")
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import qVersion
        import PySide6

        lines.append(f"  OK  PySide6={PySide6.__version__}  Qt={qVersion()}")
        app = QApplication([])
        lines.append(f"  OK  QApplication 平台={app.platformName()}")
        app.quit()
    except Exception:
        lines.append("  FAIL")
        lines.append(traceback.format_exc())

    text = "\n".join(lines)
    print(text)
    out = ROOT / "data" / "diagnose.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"\n已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
