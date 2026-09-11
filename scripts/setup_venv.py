"""旧入口：改为安装便携 Python 到 vendor/python。"""
from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("setup_portable_python.py")), run_name="__main__")
