from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.paths import settings_path, vendor_mpv_exe

RECENT_LIMIT = 12


def _int_list(raw: object) -> list[int]:
    if not isinstance(raw, list):
        return []
    result: list[int] = []
    for item in raw:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return result


def _theme_name(raw: object) -> str:
    text = str(raw or "dark").strip().lower()
    if text in ("light", "white", "白", "白色"):
        return "light"
    return "dark"


def _clamp_volume(raw: object) -> int:
    try:
        return max(0, min(100, int(raw)))
    except (TypeError, ValueError):
        return 100


@dataclass
class AppSettings:
    mpv_path: str = ""
    projection_screen: int = 0
    projection_device: str = ""
    last_project: str = ""
    recent_projects: list[str] = field(default_factory=list)
    window_geometry: str = ""
    splitter_main: list[int] = field(default_factory=list)
    splitter_library: list[int] = field(default_factory=list)
    output_volume: int = 100
    library_volume: int = 100
    theme: str = "dark"

    def resolved_mpv(self) -> Path:
        raw = (self.mpv_path or "").strip()
        if raw:
            return Path(raw)
        return vendor_mpv_exe()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def load() -> AppSettings:
        path = settings_path()
        if not path.exists():
            return AppSettings()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings()
        last_project = str(data.get("last_project") or "")
        recent: list[str] = []
        for item in data.get("recent_projects") or []:
            text = str(item).strip()
            if text and text not in recent:
                recent.append(text)
        if last_project and last_project not in recent:
            recent.insert(0, last_project)
        try:
            projection_screen = int(data.get("projection_screen") or 0)
        except (TypeError, ValueError):
            projection_screen = 0
        return AppSettings(
            mpv_path=str(data.get("mpv_path") or ""),
            projection_screen=max(0, projection_screen),
            projection_device=str(data.get("projection_device") or ""),
            last_project=last_project,
            recent_projects=recent[:RECENT_LIMIT],
            window_geometry=str(data.get("window_geometry") or ""),
            splitter_main=_int_list(data.get("splitter_main")),
            splitter_library=_int_list(data.get("splitter_library")),
            output_volume=_clamp_volume(data.get("output_volume")),
            library_volume=_clamp_volume(
                data["library_volume"] if "library_volume" in data else data.get("output_volume")
            ),
            theme=_theme_name(data.get("theme")),
        )

    def set_projection(self, index: int, device: str) -> None:
        index = max(0, int(index))
        device = (device or "").strip()
        if self.projection_screen == index and self.projection_device == device:
            return
        self.projection_screen = index
        self.projection_device = device
        self.save()

    def remember_project(self, path: Path) -> None:
        resolved = str(path.resolve())
        self.last_project = resolved
        self.recent_projects = [resolved] + [
            item for item in self.recent_projects if item != resolved
        ]
        self.recent_projects = self.recent_projects[:RECENT_LIMIT]
        self.save()

    def save(self) -> None:
        path = settings_path()
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
