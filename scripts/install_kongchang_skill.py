#!/usr/bin/env python3
"""Install the bundled Skill for the current user's Codex instance."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="安装简易控场 Agent Skill")
    parser.add_argument("--codex-home", type=Path, help="Codex 主目录，默认使用 CODEX_HOME 或 ~/.codex")
    parser.add_argument("--replace", action="store_true", help="替换已有 Skill，旧版本会保留为备份")
    args = parser.parse_args()

    app_dir = Path(__file__).resolve().parent.parent
    source = app_dir / "skills" / "kongchang-control"
    if not (source / "SKILL.md").is_file() or not (source / "scripts" / "agent_ctl.py").is_file():
        print("安装失败：软件目录中缺少 Skill 文件。", file=sys.stderr)
        return 1
    codex_home = (args.codex_home or Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")).expanduser().resolve()
    skills_dir = codex_home / "skills"
    destination = skills_dir / "kongchang-control"
    try:
        skills_dir.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            raise OSError("目标是符号链接，无法安全替换")
        if destination.exists() and not args.replace:
            print(f"安装失败：{destination} 已存在。若要更新并保留备份，请加 --replace。", file=sys.stderr)
            return 1
        with tempfile.TemporaryDirectory(prefix=".kongchang-install-", dir=skills_dir) as staging:
            staged = Path(staging) / "kongchang-control"
            shutil.copytree(source, staged, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "app-location.json"))
            (staged / "app-location.json").write_text(json.dumps({"app_dir": str(app_dir)}, ensure_ascii=False) + "\n", encoding="utf-8")
            backup = None
            if destination.exists():
                backup_dir = codex_home / "skill-backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                backup = backup_dir / f"kongchang-control-{uuid.uuid4().hex[:12]}"
                destination.rename(backup)
            try:
                staged.rename(destination)
            except OSError:
                if backup is not None:
                    backup.rename(destination)
                raise
        print(f"已安装：{destination}")
        print(f"软件目录：{app_dir}")
        if backup is not None:
            print(f"原 Skill 已备份：{backup}")
        print("新建 Codex 对话后可使用 $kongchang-control。")
        return 0
    except OSError as exc:
        print(f"安装失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
