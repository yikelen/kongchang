from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from collections.abc import Callable
from typing import Any

CUE_TYPES = ("audio", "video", "note", "stop")

TYPE_LABELS = {
    "audio": "音频",
    "video": "视频",
    "note": "备注",
    "stop": "停止",
}

TYPE_ALIASES = {
    "audio": "audio",
    "video": "video",
    "note": "note",
    "stop": "stop",
    "音频": "audio",
    "视频": "video",
    "备注": "note",
    "停止": "stop",
    "memo": "note",
}

PROJECT_README = (
    "cues 按数组从上到下播放；index 可写可不写，有则按 index 排序。"
    "id 可省略（打开时自动生成，不要重复）。"
    "type 用 audio / video / note，也可用 音频 / 视频 / 备注。"
    "path 相对本 json 所在目录（如 audio/warmup.mp3），备注条 path 留空。"
    "音频不写 loop 时默认循环。"
    "library 是临时音视频库，不进节目单顺序；"
    "category 可选，临时音频按分类分组显示（如 颁奖/茶歇/过场）。"
)


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def _index_key(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 10**9


@dataclass
class Cue:
    id: str
    name: str
    type: str
    notes: str = ""
    path: str = ""
    loop: bool = False
    category: str = ""

    def label(self) -> str:
        return TYPE_LABELS.get(self.type, self.type)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # 节目单条目一般不用分类；空分类不写进 json，保持干净
        if not (data.get("category") or "").strip():
            data.pop("category", None)
        return data

    @staticmethod
    def from_dict(data: dict[str, Any]) -> Cue:
        raw_type = str(data.get("type") or "note").strip()
        cue_type = TYPE_ALIASES.get(raw_type, TYPE_ALIASES.get(raw_type.lower(), "note"))
        raw_cat = data.get("category", data.get("分类", ""))
        return Cue(
            id=str(data.get("id") or "").strip() or new_id(),
            name=str(data.get("name") or ""),
            type=cue_type,
            notes=str(data.get("notes") or ""),
            path=str(data.get("path") or "").replace("\\", "/"),
            loop=bool(data["loop"]) if "loop" in data else cue_type == "audio",
            category=str(raw_cat or "").strip(),
        )


@dataclass
class Project:
    path: Path | None = None
    cues: list[Cue] = field(default_factory=list)
    library: list[Cue] = field(default_factory=list)
    dirty: bool = False
    on_dirty: Callable[[], None] | None = field(default=None, repr=False, compare=False)

    @property
    def directory(self) -> Path | None:
        return self.path.parent if self.path else None

    def mark_dirty(self) -> None:
        self.dirty = True
        callback = self.on_dirty
        if callback is not None:
            callback()

    def resolve_media(self, cue: Cue) -> Path | None:
        raw = (cue.path or "").strip()
        if not raw:
            return None
        candidate = Path(raw)
        if candidate.is_absolute():
            return candidate
        if self.directory is None:
            return candidate
        return (self.directory / candidate).resolve()

    def store_path(self, file_path: Path) -> str:
        resolved = file_path.resolve()
        if self.directory is not None:
            try:
                return str(resolved.relative_to(self.directory.resolve()))
            except ValueError:
                pass
        return str(resolved)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "readme": PROJECT_README,
            "cues": [
                {
                    "index": i + 1,
                    **cue.to_dict(),
                }
                for i, cue in enumerate(self.cues)
            ],
            "library": [item.to_dict() for item in self.library],
        }

    def save(self, path: Path | None = None) -> None:
        target = path or self.path
        if target is None:
            raise ValueError("工程路径未设置")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.path = target
        self.dirty = False

    @staticmethod
    def load(path: Path) -> Project:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = [item for item in (data.get("cues") or []) if isinstance(item, dict)]
        if any("index" in item for item in raw):
            raw = sorted(raw, key=lambda item: _index_key(item.get("index")))
        cues = [Cue.from_dict(item) for item in raw]
        seen: set[str] = set()
        for cue in cues:
            if not cue.id or cue.id in seen:
                cue.id = new_id()
            seen.add(cue.id)
        library = []
        for item in data.get("library") or []:
            if not isinstance(item, dict):
                continue
            cue = Cue.from_dict(item)
            if cue.type not in ("audio", "video"):
                continue
            if not cue.id or cue.id in seen:
                cue.id = new_id()
            seen.add(cue.id)
            library.append(cue)
        return Project(path=path, cues=cues, library=library, dirty=False)

    @staticmethod
    def create(path: Path) -> Project:
        project = Project(path=path, cues=[], dirty=False)
        project.save(path)
        return project
