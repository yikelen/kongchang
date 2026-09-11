# -*- coding: utf-8 -*-
"""独立进程闪屏：不受主程序加载 Qt/DPI 影响，避免跳动或叠两个窗。"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLAG = ROOT / "data" / "splash.close"
PID_FILE = ROOT / "data" / "splash.pid"


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    FLAG.parent.mkdir(parents=True, exist_ok=True)
    try:
        if FLAG.exists():
            FLAG.unlink()
    except OSError:
        pass
    try:
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass

    # 进程内尽早声明 DPI，避免自身再被缩放跳动
    try:
        import ctypes

        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

    from scripts.splash_win import Splash

    splash = Splash("简易控场", "正在加载，请稍候…")
    deadline = time.time() + 120
    try:
        while time.time() < deadline:
            if FLAG.exists():
                break
            time.sleep(0.05)
    finally:
        try:
            splash.close()
        except Exception:
            pass
        for path in (FLAG, PID_FILE):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
