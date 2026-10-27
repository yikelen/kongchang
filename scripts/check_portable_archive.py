"""Check that a portable ZIP includes the app, Agent Skill and installer."""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


REQUIRED_FILES = (
    "kongchang/启动.bat",
    "kongchang/安装Agent技能.bat",
    "kongchang/src/main.py",
    "kongchang/scripts/run_app.py",
    "kongchang/scripts/agent_ctl.py",
    "kongchang/scripts/install_kongchang_skill.py",
    "kongchang/skills/kongchang-control/SKILL.md",
    "kongchang/skills/kongchang-control/scripts/agent_ctl.py",
    "kongchang/skills/kongchang-control/references/api.md",
    "kongchang/vendor/python/pythonw.exe",
    "kongchang/vendor/mpv/mpv.exe",
)


def check_archive(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        names = {name.replace("\\", "/") for name in archive.namelist()}
    return [name for name in REQUIRED_FILES if name not in names]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        missing = check_archive(args.archive)
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"无法读取便携包：{exc}", file=sys.stderr)
        return 1
    if missing:
        print("便携包缺少必需文件：\n" + "\n".join(missing), file=sys.stderr)
        return 1
    print("便携包包含程序、Agent Skill、CLI 和安装工具。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
