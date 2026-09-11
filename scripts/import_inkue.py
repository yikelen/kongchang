"""从 Inkue 工程抽出本软件能用的 cue（音频/视频/备注）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.models import Cue, Project, new_id

KEEP = {"audio", "video", "memo"}
TYPE_MAP = {"memo": "note", "audio": "audio", "video": "video"}


def convert(inkue_path: Path, out_path: Path) -> Project:
    data = json.loads(inkue_path.read_text(encoding="utf-8"))
    cues: list[Cue] = []
    for lst in data.get("cue_lists", []):
        for raw in lst.get("cues", []):
            src_type = raw.get("cue_type") or raw.get("type")
            if src_type not in KEEP:
                continue
            path = str(raw.get("file_path") or "")
            dest_type = TYPE_MAP[src_type]
            cues.append(
                Cue(
                    id=new_id(),
                    name=str(raw.get("name") or ""),
                    type=dest_type,
                    notes=str(raw.get("notes") or raw.get("memo_text") or ""),
                    path=path,
                    loop=dest_type == "audio",
                )
            )
    project = Project(path=out_path, cues=cues, dirty=False)
    project.save(out_path)
    return project


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/import_inkue.py <输入.inkue> [输出.json]")
        raise SystemExit(2)
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2] if len(sys.argv) > 2 else src.with_name("show.json"))
    project = convert(src, dest)
    print(f"写出 {dest}  共 {len(project.cues)} 条")
    for i, cue in enumerate(project.cues, 1):
        print(f"{i:02d}  {cue.label():4}  {cue.name}  {cue.path}")
