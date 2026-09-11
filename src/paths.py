from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def vendor_mpv_exe() -> Path:
    return app_root() / "vendor" / "mpv" / "mpv.exe"


def settings_path() -> Path:
    folder = app_root() / "data"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "settings.json"


def video_input_conf() -> Path:
    path = app_root() / "data" / "mpv-video-input.conf"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "SPACE cycle pause\n"
        "ESC quit\n"
        "LEFT seek -5\n"
        "RIGHT seek 5\n"
        "Shift+LEFT seek -15\n"
        "Shift+RIGHT seek 15\n"
        "UP add volume 5\n"
        "DOWN add volume -5\n"
        "ENTER script-message kongchang-stage\n"
        "KP_ENTER script-message kongchang-stage\n"
    )
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
    return path
