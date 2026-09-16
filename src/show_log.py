"""演出日志：每次 GO / 停止 / 切歌追加一行。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.paths import app_root


def log_path() -> Path:
    folder = app_root() / "data"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "show_log.txt"


def log(event: str, detail: str = "") -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{event}\t{detail}\n"
    try:
        with log_path().open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass
