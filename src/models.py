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
    "节目单里的音视频会自动镜像到 library（source_id 指向原条目，分类为「默认」，放在列表最底、顺序同节目单），"
    "方便拿节目单垫乐去叠无声视频。"
    "category 可选，临时媒体按分类分组显示（如 颁奖/茶歇/过场）。"
    "library_play_modes 按分类记录播放模式：default 默认（选中谁播谁，跟条目 loop），"
    "repeat_one 单曲循环，sequence 顺序播放（同类播完即停），repeat_all 列表循环。"
    "hold_cover 可选，相对本 json 的封面图；视频播完（不循环）后投这张图，避免停在最后一帧。"
)

LIB_PLAY_DEFAULT = "default"
LIB_PLAY_ONE = "repeat_one"
LIB_PLAY_SEQ = "sequence"
LIB_PLAY_ALL = "repeat_all"
LIB_PLAY_MODES = (LIB_PLAY_DEFAULT, LIB_PLAY_ONE, LIB_PLAY_SEQ, LIB_PLAY_ALL)

_LIB_PLAY_LABELS = {
    LIB_PLAY_DEFAULT: "默认",
    LIB_PLAY_ONE: "单曲",
    LIB_PLAY_SEQ: "顺序",
    LIB_PLAY_ALL: "列表",
}
_LIB_PLAY_TIPS = {
    LIB_PLAY_DEFAULT: "默认：选中谁播谁。按该条「音频/视频循环」；不循环则播完即停，不自动下一首",
    LIB_PLAY_ONE: "单曲循环：当前条循环，不切下一首",
    LIB_PLAY_SEQ: "顺序播放：同分类、同类型播完一首切下一首，到列表末尾停下",
    LIB_PLAY_ALL: "列表循环：同分类、同类型列表循环",
}
_LIB_PLAY_ALIASES = {
    "default": LIB_PLAY_DEFAULT,
    "默认": LIB_PLAY_DEFAULT,
    "repeat_one": LIB_PLAY_ONE,
    "one": LIB_PLAY_ONE,
    "单曲": LIB_PLAY_ONE,
    "单曲循环": LIB_PLAY_ONE,
    "sequence": LIB_PLAY_SEQ,
    "sequential": LIB_PLAY_SEQ,
    "顺序": LIB_PLAY_SEQ,
    "顺序播放": LIB_PLAY_SEQ,
    "repeat_all": LIB_PLAY_ALL,
    "loop": LIB_PLAY_ALL,
    "列表": LIB_PLAY_ALL,
    "列表循环": LIB_PLAY_ALL,
}


SHOW_MIRROR_CATEGORY = "默认"


def new_id() -> str:
    return uuid.uuid4().hex[:10]


def _as_sec(raw: object) -> float:
    try:
        value = float(raw or 0)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, value)


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
    source_id: str = ""
    trim_in: float = 0.0
    trim_out: float = 0.0
    fade_in: float = 0.0
    fade_out: float = 0.0

    def label(self) -> str:
        return TYPE_LABELS.get(self.type, self.type)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # 节目单条目一般不用分类；空分类不写进 json，保持干净
        if not (data.get("category") or "").strip():
            data.pop("category", None)
        if not (data.get("source_id") or "").strip():
            data.pop("source_id", None)
        for key in ("trim_in", "trim_out", "fade_in", "fade_out"):
            try:
                if float(data.get(key) or 0) <= 0:
                    data.pop(key, None)
            except (TypeError, ValueError):
                data.pop(key, None)
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
            source_id=str(data.get("source_id") or "").strip(),
            trim_in=_as_sec(data.get("trim_in")),
            trim_out=_as_sec(data.get("trim_out")),
            fade_in=_as_sec(data.get("fade_in")),
            fade_out=_as_sec(data.get("fade_out")),
        )


def cue_category_key(cue: Cue) -> str:
    return (cue.category or "").strip()


def next_library_in_category(
    library: list[Cue],
    current: Cue,
    *,
    wrap: bool = True,
    playable: Callable[[Cue], bool] | None = None,
) -> Cue | None:
    """同分类、同类型的下一首。顺序与 library 数组一致（即界面分组内顺序）。

    不跨分类，也不把音频/视频混成一条队列。
    wrap=True 时播完最后一首回到该分类第一首。
    """
    key = cue_category_key(current)
    group = [
        cue
        for cue in library
        if cue.type == current.type and cue_category_key(cue) == key
    ]
    if not group:
        return None

    def ok(cue: Cue) -> bool:
        return playable is None or playable(cue)

    try:
        idx = next(i for i, cue in enumerate(group) if cue.id == current.id)
    except StopIteration:
        candidates = [cue for cue in group if ok(cue)]
        return candidates[0] if candidates else None

    rest = group[idx + 1 :]
    if wrap:
        rest = rest + group[: idx + 1]
    for cand in rest:
        if cand.id == current.id:
            return cand if wrap and ok(cand) else None
        if ok(cand):
            return cand
    return None


def normalize_library_play_mode(raw: object) -> str:
    text = str(raw or LIB_PLAY_DEFAULT).strip()
    return _LIB_PLAY_ALIASES.get(text, _LIB_PLAY_ALIASES.get(text.lower(), LIB_PLAY_DEFAULT))


def library_play_label(mode: str) -> str:
    return _LIB_PLAY_LABELS.get(normalize_library_play_mode(mode), _LIB_PLAY_LABELS[LIB_PLAY_DEFAULT])


def library_play_tip(mode: str) -> str:
    return _LIB_PLAY_TIPS.get(normalize_library_play_mode(mode), _LIB_PLAY_TIPS[LIB_PLAY_DEFAULT])


def next_library_play_mode(current: str) -> str:
    cur = normalize_library_play_mode(current)
    idx = LIB_PLAY_MODES.index(cur)
    return LIB_PLAY_MODES[(idx + 1) % len(LIB_PLAY_MODES)]


def category_storage_key(title: str) -> str:
    text = (title or "").strip()
    if not text or text == "未分类":
        return ""
    return text


def rebuild_library_from_visual(
    library_by_id: dict[str, Cue],
    visual: list[tuple[str, str]],
    *,
    uncategorized: str = "未分类",
) -> list[Cue]:
    """按界面行顺序重建 library，并把条目归入最近的分类头。"""
    result: list[Cue] = []
    cat = ""
    seen_header = False
    for kind, value in visual:
        if kind == "header":
            cat = "" if (not value or value == uncategorized) else str(value).strip()
            seen_header = True
            continue
        cue = library_by_id.get(value)
        if cue is None:
            continue
        cue.category = cat if seen_header else ""
        result.append(cue)
    return result


@dataclass
class Project:
    path: Path | None = None
    cues: list[Cue] = field(default_factory=list)
    library: list[Cue] = field(default_factory=list)
    library_play_modes: dict[str, str] = field(default_factory=dict)
    hold_cover: str = ""
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

    def library_play_mode(self, category_key: str) -> str:
        key = category_storage_key(category_key)
        return normalize_library_play_mode(self.library_play_modes.get(key))

    def set_library_play_mode(self, category_key: str, mode: str) -> None:
        key = category_storage_key(category_key)
        normalized = normalize_library_play_mode(mode)
        current = self.library_play_mode(key)
        if normalized == current:
            return
        if normalized == LIB_PLAY_DEFAULT:
            self.library_play_modes.pop(key, None)
        else:
            self.library_play_modes[key] = normalized
        self.mark_dirty()

    def rename_library_play_mode(self, old_key: str, new_key: str) -> None:
        old = category_storage_key(old_key)
        new = category_storage_key(new_key)
        if old == new or old not in self.library_play_modes:
            return
        value = self.library_play_modes.pop(old)
        if new not in self.library_play_modes and normalize_library_play_mode(value) != LIB_PLAY_DEFAULT:
            self.library_play_modes[new] = normalize_library_play_mode(value)

    def _play_modes_for_save(self) -> dict[str, str]:
        keys = {cue_category_key(cue) for cue in self.library}
        saved: dict[str, str] = {}
        for key, raw in self.library_play_modes.items():
            mode = normalize_library_play_mode(raw)
            if mode == LIB_PLAY_DEFAULT or key not in keys:
                continue
            saved[key] = mode
        return saved

    def mirror_show_cue(self, cue: Cue) -> Cue | None:
        """把节目单音视频镜像到临时列表「默认」分类，顺序与节目单一致。"""
        if cue.type not in ("audio", "video"):
            return None
        for item in self.library:
            if item.source_id == cue.id:
                item.name = cue.name
                item.path = cue.path
                item.loop = cue.loop
                item.type = cue.type
                item.notes = cue.notes
                item.category = SHOW_MIRROR_CATEGORY
                item.trim_in = cue.trim_in
                item.trim_out = cue.trim_out
                item.fade_in = cue.fade_in
                item.fade_out = cue.fade_out
                return item
        copy = Cue(
            id=new_id(),
            name=cue.name,
            type=cue.type,
            notes=cue.notes,
            path=cue.path,
            loop=cue.loop,
            category=SHOW_MIRROR_CATEGORY,
            source_id=cue.id,
            trim_in=cue.trim_in,
            trim_out=cue.trim_out,
            fade_in=cue.fade_in,
            fade_out=cue.fade_out,
        )
        self.library.append(copy)
        return copy

    def drop_show_mirrors(self, cue_id: str) -> None:
        self.library = [item for item in self.library if item.source_id != cue_id]

    def sync_show_mirrors(self) -> bool:
        changed = False
        show_ids = {cue.id for cue in self.cues}
        kept = [item for item in self.library if not item.source_id or item.source_id in show_ids]
        if len(kept) != len(self.library):
            self.library = kept
            changed = True
        have = {item.source_id for item in self.library if item.source_id}
        for cue in self.cues:
            if cue.type not in ("audio", "video"):
                continue
            if cue.id not in have:
                self.mirror_show_cue(cue)
                changed = True
            else:
                self.mirror_show_cue(cue)
        show_order = {cue.id: index for index, cue in enumerate(self.cues)}
        mirrors = [item for item in self.library if item.source_id]
        others = [item for item in self.library if not item.source_id]
        mirrors.sort(key=lambda item: show_order.get(item.source_id, 10**9))
        reordered = others + mirrors
        if [item.id for item in reordered] != [item.id for item in self.library]:
            changed = True
        self.library = reordered
        return changed

    def resolve_hold_cover(self) -> Path | None:
        raw = (self.hold_cover or "").strip()
        if not raw:
            return None
        candidate = Path(raw)
        if not candidate.is_absolute() and self.directory is not None:
            candidate = self.directory / candidate
        candidate = candidate.resolve()
        return candidate if candidate.exists() else None

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
        data: dict[str, Any] = {
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
        modes = self._play_modes_for_save()
        if modes:
            data["library_play_modes"] = modes
        cover = (self.hold_cover or "").strip()
        if cover:
            data["hold_cover"] = cover.replace("\\", "/")
        return data

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
        play_modes: dict[str, str] = {}
        raw_modes = data.get("library_play_modes") or data.get("临时播放模式") or {}
        if isinstance(raw_modes, dict):
            for raw_key, raw_mode in raw_modes.items():
                key = category_storage_key(str(raw_key))
                mode = normalize_library_play_mode(raw_mode)
                if mode != LIB_PLAY_DEFAULT:
                    play_modes[key] = mode
        cover = str(data.get("hold_cover") or data.get("封面") or "").strip().replace("\\", "/")
        return Project(
            path=path,
            cues=cues,
            library=library,
            library_play_modes=play_modes,
            hold_cover=cover,
            dirty=False,
        )

    @staticmethod
    def create(path: Path) -> Project:
        project = Project(path=path, cues=[], dirty=False)
        project.save(path)
        return project
