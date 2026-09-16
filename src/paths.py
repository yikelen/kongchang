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


def hold_black_png() -> Path:
    """1x1 黑 PNG，没有封面图时当黑场用。"""
    folder = app_root() / "data"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "hold_black.png"
    if not path.exists() or path.stat().st_size < 20:
        path.write_bytes(
            bytes.fromhex(
                "89504E470D0A1A0A0000000D4948445200000001000000010802000000907753DE"
                "0000000C4944415408D76360000000020001E221BC330000000049454E44AE426082"
            )
        )
    return path


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
