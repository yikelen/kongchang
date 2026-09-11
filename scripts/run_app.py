# -*- coding: utf-8 -*-
"""启动入口。闪屏由独立进程显示；此处只负责在主界面就绪后关掉它。"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_DIR = ROOT / "vendor" / "python"
PYSIDE = PY_DIR / "Lib" / "site-packages" / "PySide6"
SPLASH_FLAG = ROOT / "data" / "splash.close"


def _msg(title: str, text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:
        sys.stderr.write(f"{title}\n{text}\n")


def _add_dll_dirs() -> None:
    dirs = [
        PY_DIR,
        PYSIDE,
        PYSIDE / "plugins",
        PYSIDE / "plugins" / "platforms",
    ]
    for d in dirs:
        if d.is_dir():
            try:
                os.add_dll_directory(str(d))
            except (OSError, AttributeError):
                pass
    prefix = os.pathsep.join(str(d) for d in dirs if d.is_dir())
    os.environ["PATH"] = prefix + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("QT_PLUGIN_PATH", str(PYSIDE / "plugins"))
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(PYSIDE / "plugins" / "platforms"))


def _close_splash() -> None:
    try:
        SPLASH_FLAG.parent.mkdir(parents=True, exist_ok=True)
        SPLASH_FLAG.write_text("1", encoding="utf-8")
    except OSError:
        pass


def _friendly_import_error(exc: BaseException) -> str:
    return (
        "控场无法启动：界面组件（PySide6/Qt）加载失败。\n\n"
        f"错误：{type(exc).__name__}: {exc}\n\n"
        "常见原因与处理（按顺序试）：\n"
        "1. 确认拷贝的是整个「控场」文件夹（含 vendor\\python），不要只拷 src。\n"
        "2. 必须是 64 位 Windows 10/11（不要用 32 位系统）。\n"
        "3. 安装微软运行库 VC++ 2015–2022 x64 后重开：\n"
        "   https://aka.ms/vs/17/release/vc_redist.x64.exe\n"
        "4. 右键 启动.bat → 以管理员身份运行一次；或把文件夹放到非桌面/非网盘路径再试\n"
        "   （例如 D:\\控场）。\n"
        "5. 仍不行：在本文件夹双击「环境检测.bat」，把窗口里的文字发给管理员。\n\n"
        "详细堆栈已写入 data\\crash.log"
    )


def main() -> int:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    _add_dll_dirs()

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
    except Exception as exc:
        _close_splash()
        text = _friendly_import_error(exc) + "\n\n" + traceback.format_exc()
        try:
            log = ROOT / "data" / "crash.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(text, encoding="utf-8")
        except OSError:
            pass
        _msg("控场无法启动", _friendly_import_error(exc))
        return 1

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("简易控场")
    app.setOrganizationName("简易控场")

    # 应用图标（任务栏 / 标题栏）
    try:
        from PySide6.QtGui import QIcon

        icon_path = ROOT / "assets" / "app_v3.ico"
        if not icon_path.exists():
            icon_path = ROOT / "assets" / "app.ico"
        if not icon_path.exists():
            icon_path = ROOT / "assets" / "app_v3.png"
        if not icon_path.exists():
            icon_path = ROOT / "assets" / "app.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
    except Exception:
        pass

    try:
        from src.instance import start_singleton_server, take_over
        from src.ui.main_window import MainWindow

        if not take_over():
            _close_splash()
            return 0

        project_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
        window = MainWindow(project_path)
        if not app.windowIcon().isNull():
            window.setWindowIcon(app.windowIcon())
        server = start_singleton_server(window.bring_to_front, window.force_close)
        app.aboutToQuit.connect(window.controller.shutdown)

        _close_splash()
        window.show()
        window.raise_()
        window.activateWindow()
        code = app.exec()
        del server
        return int(code or 0)
    except Exception:
        _close_splash()
        raise
    finally:
        _close_splash()


if __name__ == "__main__":
    raise SystemExit(main())
