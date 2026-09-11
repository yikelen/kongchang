from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _prepare_dll_search() -> None:
    """Python 3.8+ 加载 Qt 扩展时不靠 PATH，需登记 DLL 目录。"""
    py_dir = ROOT / "vendor" / "python"
    pyside = py_dir / "Lib" / "site-packages" / "PySide6"
    dirs = [py_dir, pyside, pyside / "plugins", pyside / "plugins" / "platforms"]
    for d in dirs:
        if d.is_dir():
            try:
                os.add_dll_directory(str(d))
            except (OSError, AttributeError):
                pass
    prefix = os.pathsep.join(str(d) for d in dirs if d.is_dir())
    os.environ["PATH"] = prefix + os.pathsep + os.environ.get("PATH", "")
    os.environ.setdefault("QT_PLUGIN_PATH", str(pyside / "plugins"))
    os.environ.setdefault(
        "QT_QPA_PLATFORM_PLUGIN_PATH", str(pyside / "plugins" / "platforms")
    )


_prepare_dll_search()

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from src.instance import start_singleton_server, take_over
from src.ui.main_window import MainWindow


def _append_crash(text: str) -> None:
    log = ROOT / "data" / "crash.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block = f"===== {stamp} =====\n{text.rstrip()}\n\n"
    previous = ""
    if log.exists():
        try:
            previous = log.read_text(encoding="utf-8")
        except OSError:
            previous = ""
    merged = previous + block
    if len(merged) > 200_000:
        merged = merged[-100_000:]
        cut = merged.find("===== ")
        if cut > 0:
            merged = merged[cut:]
    log.write_text(merged, encoding="utf-8")


def _excepthook(exc_type, exc, tb) -> None:
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        _append_crash(text)
    except Exception:
        pass
    try:
        QMessageBox.critical(None, "未处理错误", text)
    except Exception:
        sys.stderr.write(text)


def main(on_ready=None) -> int:
    """直接运行 main.py 时的入口（无闪屏）。正常请用 启动.bat → run_app.py。"""
    sys.excepthook = _excepthook
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("简易控场")
    if not take_over():
        return 0
    project_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    window = MainWindow(project_path)
    server = start_singleton_server(window.bring_to_front, window.force_close)
    app.aboutToQuit.connect(window.controller.shutdown)
    if on_ready is not None:
        try:
            on_ready()
        except Exception:
            pass
    window.show()
    window.raise_()
    window.activateWindow()
    code = app.exec()
    del server
    return code


if __name__ == "__main__":
    raise SystemExit(main())
