"""Main-thread business operations for the local agent interface.

No transport or dialogs live here. The owner dispatches every call on the Qt
GUI thread so project state, widgets and playback remain synchronized.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src import __version__
from src.models import Cue, Project, SHOW_MIRROR_CATEGORY, new_id
from PySide6.QtWidgets import QApplication


class AgentError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AgentAPI:
    """Validated operations on one live MainWindow; call only on its GUI thread."""

    METHODS = (
        "system.info", "state.get", "project.get", "project.open", "project.create", "project.save", "project.save_as",
        "cue.list", "cue.add", "cue.update", "cue.delete", "cue.move",
        "library.list", "library.add", "library.update", "library.delete", "library.move",
        "playback.play", "playback.pause", "playback.resume", "playback.stop", "playback.seek",
        "playback.panic", "playback.stage", "playback.unstage", "playback.mute", "playback.duck",
        "playback.hold", "system.show_mode", "volume.set",
    )
    _FIELDS = {"name", "notes", "path", "loop", "trim_in", "trim_out", "fade_in", "fade_out"}
    _SECS = {"trim_in", "trim_out", "fade_in", "fade_out"}

    def __init__(self, window: Any) -> None:
        self.window = window

    def dispatch(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not isinstance(method, str) or method not in self.METHODS:
            raise AgentError("method_not_found", f"不支持的操作：{method}")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise AgentError("invalid_request", "params 必须是对象")
        allowed_params = {
            "system.info": set(), "state.get": set(), "project.get": set(),
            "cue.list": set(), "library.list": set(),
            "project.open": {"path", "expected_revision"},
            "project.create": {"path", "expected_revision"},
            "project.save": {"expected_revision"},
            "project.save_as": {"path", "expected_revision"},
            "cue.add": self._FIELDS | {"type", "index", "expected_revision"},
            "library.add": self._FIELDS | {"type", "category", "index", "expected_revision"},
            "cue.update": {"id", "changes", "expected_revision"},
            "library.update": {"id", "changes", "expected_revision"},
            "cue.delete": {"id", "expected_revision"},
            "library.delete": {"id", "expected_revision"},
            "cue.move": {"id", "index", "expected_revision"},
            "library.move": {"id", "index", "expected_revision"},
            "playback.play": {"channel", "id"},
            "playback.pause": {"channel"}, "playback.resume": {"channel"},
            "playback.stop": {"channel"}, "playback.seek": {"channel", "ratio"},
            "playback.stage": {"channel", "id"}, "playback.unstage": {"channel"},
            "playback.panic": set(), "playback.mute": {"value"},
            "playback.duck": {"value"}, "playback.hold": {"value"},
            "system.show_mode": {"value"}, "volume.set": {"channel", "value"},
        }
        unknown = set(params) - allowed_params[method]
        if unknown:
            raise AgentError("invalid_request", "不支持字段：" + ", ".join(sorted(unknown)))
        read_only = {"system.info", "state.get", "project.get", "cue.list", "library.list"}
        if method not in read_only and method != "playback.panic" and QApplication.activeModalWidget() is not None:
            raise AgentError("modal_active", "当前有对话框待处理，请先关闭对话框")
        if method == "system.info":
            return {"name": "简易控场", "version": __version__, "methods": list(self.METHODS)}
        if method == "state.get":
            return self._state()
        if method == "project.get":
            return self._project()
        if method in ("cue.list", "library.list"):
            scope = method.split(".")[0]
            items = self.window.project.cues if scope == "cue" else self.window.project.library
            return {"items": [item.to_dict() for item in items], "revision": self._revision()}
        if method in ("project.open", "project.create"):
            self._check_revision(params)
            return self._switch_project(params, create=method == "project.create")
        if method == "project.save_as":
            self._check_revision(params)
            self._guard_editor()
            return self._save_as(params)
        if method == "project.save":
            self._check_revision(params)
            self._guard_editor()
            project = self.window.project
            if project.path is None:
                raise AgentError("project_required", "当前工程尚无保存路径，请先创建或打开工程")
            try:
                project.save()
            except OSError as exc:
                raise AgentError("save_failed", f"保存工程失败：{exc}") from exc
            self.window._refresh_project_label()
            return {"path": str(project.path), "revision": self._revision(), "dirty": False}
        if method.startswith(("cue.", "library.")):
            self._check_revision(params)
            self._guard_editor()
            return self._mutate(method, params)
        if method == "system.show_mode":
            value = self._boolean(params.get("value"), "value")
            if bool(self.window._show_mode) != value:
                self.window._set_show_mode(value)
            return {"show_mode": bool(self.window._show_mode)}
        if method.startswith("playback."):
            return self._playback(method, params)
        if method == "volume.set":
            return self._volume(params)
        raise AgentError("method_not_found", f"不支持的操作：{method}")

    def _revision(self) -> str:
        project = self.window.project
        value = {"path": str(project.path) if project.path else None, "content": project.to_dict()}
        blob = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _check_revision(self, params: dict[str, Any]) -> None:
        expected = params.get("expected_revision")
        if expected is not None:
            if not isinstance(expected, str):
                raise AgentError("invalid_request", "expected_revision 必须是字符串")
            if expected != self._revision():
                raise AgentError("revision_conflict", "工程已发生变化，请重新读取后重试")

    def _guard_editor(self) -> None:
        """Do not discard text typed into the current inspector but not committed."""
        w = self.window
        cue = w.active_cue()
        editor = getattr(w, "name_edit", None)
        if cue is not None and editor is not None and editor.hasFocus() and editor.text().strip() != cue.name:
            raise AgentError("editor_busy", "当前名称正在编辑，请先完成界面中的编辑")
        for name in ("trim_in_spin", "trim_out_spin", "fade_in_spin", "fade_out_spin"):
            spin = getattr(w, name, None)
            line = spin.lineEdit() if spin is not None else None
            if cue is not None and line is not None and line.hasFocus() and line.isModified():
                raise AgentError("editor_busy", "当前时间参数正在编辑，请先完成界面中的编辑")

    def _project(self) -> dict[str, Any]:
        project = self.window.project
        data = project.to_dict()
        data.update({"path": str(project.path) if project.path else None,
                     "dirty": project.dirty, "revision": self._revision()})
        return data

    def _state(self) -> dict[str, Any]:
        w, ctl = self.window, self.window.controller
        status = asdict(ctl.status())
        show_id, show_state = ctl.live_cue_state()
        audio_id, audio_state = ctl.live_audio_state()
        video_id, video_state = ctl.live_library_video_state()
        apos, adur = ctl.audio_progress()
        vpos, vdur = ctl.library_video_progress()
        return {
            "version": __version__, "project_path": str(w.project.path) if w.project.path else None,
            "project_dirty": w.project.dirty, "revision": self._revision(),
            "locked": bool(w._cues_locked), "show_mode": bool(w._show_mode),
            "selected_cue_id": w.current_cue().id if w.current_cue() else None,
            "selected_library_id": w.current_library_cue().id if w.current_library_cue() else None,
            "show": {"id": show_id, "state": show_state, **status},
            "library_audio": {"id": audio_id, "state": audio_state, "position": apos, "duration": adur},
            "library_video": {"id": video_id, "state": video_state, "position": vpos, "duration": vdur},
            "output_volume": ctl.output_volume, "library_volume": ctl.library_volume,
            "master_muted": ctl.master_muted, "ducked": ctl.ducked,
            "video_on_stage": ctl.video_on_stage, "hold_active": ctl.hold_active,
        }

    @staticmethod
    def _str(value: Any, field: str, *, nonempty: bool = False) -> str:
        if not isinstance(value, str):
            raise AgentError("invalid_request", f"{field} 必须是字符串")
        if nonempty and not value.strip():
            raise AgentError("invalid_request", f"{field} 不能为空")
        return value

    @staticmethod
    def _boolean(value: Any, field: str) -> bool:
        if not isinstance(value, bool):
            raise AgentError("invalid_request", f"{field} 必须是布尔值")
        return value

    @staticmethod
    def _index(value: Any, minimum: int, maximum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise AgentError("invalid_request", f"index 必须是 {minimum} 到 {maximum} 的整数（从 0 开始）")
        return value

    @staticmethod
    def _number(value: Any, field: str, low: float, high: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise AgentError("invalid_request", f"{field} 必须是 {low:g} 到 {high:g} 的有限数字")
        return float(value)

    def _check_switch(self) -> None:
        self._guard_editor()
        w, ctl = self.window, self.window.controller
        if w.project.dirty:
            raise AgentError("project_dirty", "当前工程有未保存的修改，请先保存")
        channels = ((ctl.audio, ctl.audio_cue_id), (ctl.lib_audio, ctl.lib_audio_cue_id),
                    (ctl.video, ctl.video_cue_id))
        active = any(client is not None and client.alive and
                     (ctl._is_active(client) or bool(cue_id and getattr(client, "is_loading", False)))
                     for client, cue_id in channels)
        if active or ctl._fading or ctl.hold_active or ctl.video_on_stage:
            raise AgentError("playback_active", "当前有声画或封面正在运行，请先停止")

    def _switch_project(self, params: dict[str, Any], *, create: bool) -> dict[str, Any]:
        self._check_switch()
        raw = self._str(params.get("path"), "path", nonempty=True)
        path = Path(raw)
        if not path.is_absolute():
            raise AgentError("invalid_request", "工程路径必须是绝对路径")
        if path.suffix.lower() != ".json":
            raise AgentError("invalid_request", "工程文件必须使用 .json 扩展名")
        if not path.parent.is_dir():
            raise AgentError("invalid_path", "工程所在目录不存在")
        try:
            if create:
                project = Project(path=path)
                # Exclusive creation prevents replacing an existing activity project.
                with path.open("x", encoding="utf-8") as stream:
                    json.dump(project.to_dict(), stream, ensure_ascii=False, indent=2)
            else:
                if not path.is_file():
                    raise AgentError("not_found", "工程文件不存在")
                project = Project.load(path)
        except FileExistsError as exc:
            raise AgentError("already_exists", "工程文件已存在，不会覆盖") from exc
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            raise AgentError("project_error", f"工程文件无法{'创建' if create else '打开'}：{exc}") from exc
        w = self.window
        w._autosave_timer.stop()
        w._adopt_project(project)
        # Undo snapshots belong to a single project; retaining them would let
        # Undo restore the previous project into the newly opened file.
        w._undo_stack.clear()
        w._redo_stack.clear()
        w._drop_stop_cues()
        w._remember_project(path)
        w.reload_table()
        w._refresh_status()
        return self._project()

    def _save_as(self, params: dict[str, Any]) -> dict[str, Any]:
        raw = self._str(params.get("path"), "path", nonempty=True)
        destination = Path(raw)
        if not destination.is_absolute() or destination.suffix.lower() != ".json":
            raise AgentError("invalid_request", "保存路径必须是 .json 绝对路径")
        if not destination.parent.is_dir():
            raise AgentError("invalid_path", "工程所在目录不存在")
        original = self.window.project
        # Paths in the original project are relative to its directory. Rebase
        # them before changing project.path so media still resolve after saving.
        def rebase(raw_path: str) -> str:
            if not raw_path:
                return ""
            source = Path(raw_path)
            if not source.is_absolute():
                source = (original.directory or Path.cwd()) / source
            source = source.resolve()
            try:
                return str(source.relative_to(destination.parent.resolve())).replace("\\", "/")
            except ValueError:
                return str(source).replace("\\", "/")

        def rebase_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
            if not isinstance(snapshot, dict):
                raise ValueError("工程快照不是对象")
            for group in ("cues", "library"):
                items = snapshot.get(group, [])
                if not isinstance(items, list):
                    raise ValueError(f"工程快照中的 {group} 无效")
                for item in items:
                    if not isinstance(item, dict):
                        raise ValueError(f"工程快照中的 {group} 条目无效")
                    path = item.get("path", "")
                    if not isinstance(path, str):
                        raise ValueError("工程快照中的媒体路径无效")
                    if path:
                        item["path"] = rebase(path)
            cover = snapshot.get("hold_cover", "")
            if not isinstance(cover, str):
                raise ValueError("工程快照中的封面路径无效")
            if cover:
                snapshot["hold_cover"] = rebase(cover)
            return snapshot

        # Undo/redo snapshots retain relative media paths too. Prepare all of
        # them before creating a file or changing the live project's path.
        try:
            snapshot = rebase_snapshot(original.to_dict())
            undo_stack = [json.dumps(rebase_snapshot(json.loads(raw)), ensure_ascii=False)
                          for raw in self.window._undo_stack]
            redo_stack = [json.dumps(rebase_snapshot(json.loads(raw)), ensure_ascii=False)
                          for raw in self.window._redo_stack]
        except (ValueError, TypeError, OSError, RuntimeError) as exc:
            raise AgentError("save_failed", f"无法转换工程或撤销历史中的路径：{exc}") from exc
        try:
            with destination.open("x", encoding="utf-8") as stream:
                json.dump(snapshot, stream, ensure_ascii=False, indent=2)
        except FileExistsError as exc:
            raise AgentError("already_exists", "工程文件已存在，不会覆盖") from exc
        except OSError as exc:
            raise AgentError("save_failed", f"保存工程失败：{exc}") from exc
        # Keep the live Cue objects and their selection, IDs, and playback state.
        for cue, saved in zip(original.cues, snapshot["cues"]):
            cue.path = saved.get("path", "")
        for cue, saved in zip(original.library, snapshot["library"]):
            cue.path = saved.get("path", "")
        original.hold_cover = snapshot.get("hold_cover", "")
        original.path = destination
        original.dirty = False
        self.window._undo_stack[:] = undo_stack
        self.window._redo_stack[:] = redo_stack
        self.window._autosave_timer.stop()
        self.window._remember_project(destination)
        self.window._missing_cache.clear()
        self.window._refresh_project_label()
        self.window._refresh_status()
        return {"path": str(destination), "revision": self._revision(), "dirty": False}

    def _validate_fields(self, changes: dict[str, Any], scope: str, cue_type: str) -> dict[str, Any]:
        allowed = self._FIELDS | ({"category"} if scope == "library" else set())
        unknown = set(changes) - allowed
        if unknown:
            raise AgentError("invalid_request", "不支持修改字段：" + ", ".join(sorted(unknown)))
        result: dict[str, Any] = {}
        for key, value in changes.items():
            if key in ("name", "notes", "path", "category"):
                value = self._str(value, key, nonempty=(key == "name"))
                if key == "category":
                    value = value.strip()
                    if value == SHOW_MIRROR_CATEGORY:
                        raise AgentError("reserved_category", "默认分类由节目单自动镜像，不能手动使用")
                if key == "path":
                    if cue_type == "note" and value.strip():
                        raise AgentError("invalid_request", "备注不能设置媒体路径")
                    value = value.strip().replace("\\", "/")
                    if value and Path(value).is_absolute():
                        value = self.window.project.store_path(Path(value)).replace("\\", "/")
            elif key == "loop":
                if not isinstance(value, bool):
                    raise AgentError("invalid_request", "loop 必须是布尔值")
                if cue_type == "note" and value:
                    raise AgentError("invalid_request", "备注不能循环")
            else:
                if cue_type == "note":
                    raise AgentError("invalid_request", "备注不支持媒体时间参数")
                value = self._number(value, key, 0, 864000)
            result[key] = value
        return result

    def _items(self, scope: str) -> list[Cue]:
        return self.window.project.cues if scope == "cue" else self.window.project.library

    def _find(self, scope: str, params: dict[str, Any], *, editable: bool = False) -> Cue:
        cue_id = self._str(params.get("id"), "id", nonempty=True)
        item = next((cue for cue in self._items(scope) if cue.id == cue_id), None)
        if item is None:
            raise AgentError("not_found", f"找不到条目：{cue_id}")
        if editable and scope == "library" and (item.source_id or item.category == SHOW_MIRROR_CATEGORY):
            raise AgentError("read_only_mirror", "节目单镜像由节目单维护，不能直接修改或删除")
        return item

    def _active(self, cue: Cue) -> bool:
        ctl = self.window.controller
        ids = {ctl.live_cue_state()[0], ctl.live_audio_state()[0], ctl.live_library_video_state()[0]}
        # Include media being loaded before mpv's idle-active observation catches up.
        for client, cue_id in ((ctl.audio, ctl.audio_cue_id), (ctl.lib_audio, ctl.lib_audio_cue_id),
                               (ctl.video, ctl.video_cue_id)):
            if client is not None and client.alive and cue_id and getattr(client, "is_loading", False):
                ids.add(cue_id)
        # A mirror refers to the same cue content even though it has its own ID.
        related = {cue.id}
        if cue.source_id:
            related.add(cue.source_id)
        for mirror in self.window.project.library:
            if mirror.source_id == cue.id:
                related.add(mirror.id)
        return bool(related & ids)

    def _refresh(self, selection_id: str | None, library_id: str | None) -> None:
        w = self.window
        row = next((i for i, cue in enumerate(w.project.cues) if cue.id == selection_id), -1)
        w.reload_table(row)
        w.reload_library("audio", keep_id=library_id)
        w.fill_inspector()
        w._refresh_status()

    def _mutate(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        scope, operation = method.split(".")
        w, project = self.window, self.window.project
        if scope == "cue" and w._cues_locked:
            raise AgentError("locked", "节目单已锁定")
        selected = w.current_cue().id if w.current_cue() else None
        selected_lib = w.current_library_cue().id if w.current_library_cue() else None
        items = self._items(scope)
        editable_items = items if scope == "cue" else [item for item in items if not item.source_id and item.category != SHOW_MIRROR_CATEGORY]
        if operation == "add":
            kind = self._str(params.get("type"), "type", nonempty=True).strip().lower()
            if kind not in (("audio", "video", "note") if scope == "cue" else ("audio", "video")):
                raise AgentError("invalid_request", "type 必须是 audio、video 或 note（素材库仅支持音视频）")
            allowed = self._FIELDS | {"type", "index", "expected_revision"} | ({"category"} if scope == "library" else set())
            unknown = set(params) - allowed
            if unknown:
                raise AgentError("invalid_request", "不支持字段：" + ", ".join(sorted(unknown)))
            fields = {key: value for key, value in params.items() if key in self._FIELDS or key == "category"}
            if "name" not in fields:
                raise AgentError("invalid_request", "必须提供名称 name")
            fields = self._validate_fields(fields, scope, kind)
            index = self._index(params.get("index", len(editable_items)), 0, len(editable_items))
            cue = Cue(id=new_id(), type=kind, name=fields.pop("name"), loop=(kind == "audio"))
            for key, value in fields.items():
                setattr(cue, key, value)
            self._validate_trim(cue)
            w._push_undo()
            if scope == "cue":
                project.cues.insert(index, cue)
            else:
                editable_items.insert(index, cue)
                project.library = editable_items + [item for item in items if item not in editable_items and (item.source_id or item.category == SHOW_MIRROR_CATEGORY)]
            project.sync_show_mirrors()
            project.mark_dirty()
            self._refresh(selected, selected_lib)
            return {"id": cue.id, "item": cue.to_dict(), "revision": self._revision()}
        cue = self._find(scope, params, editable=True)
        if operation == "update":
            changes = params.get("changes")
            if not isinstance(changes, dict) or not changes:
                raise AgentError("invalid_request", "changes 必须是非空对象")
            changes = self._validate_fields(changes, scope, cue.type)
            if self._active(cue) and set(changes) & {"path", "trim_in", "trim_out", "fade_in", "fade_out"}:
                raise AgentError("playback_active", "播放中的素材不能更改路径或裁剪参数，请先停止")
            candidate = Cue.from_dict({**cue.to_dict(), **changes})
            self._validate_trim(candidate)
            w._push_undo()
            for key, value in changes.items():
                setattr(cue, key, value)
            project.sync_show_mirrors()
            if "loop" in changes:
                w.controller.apply_loop(cue, w._library_loop_for(cue) if scope == "library" else None)
                if scope == "cue":
                    for mirror in project.library:
                        if mirror.source_id == cue.id:
                            w.controller.apply_loop(mirror, w._library_loop_for(mirror))
            project.mark_dirty()
            w._missing_cache.clear()
            self._refresh(selected, selected_lib)
            return {"id": cue.id, "item": cue.to_dict(), "revision": self._revision()}
        if operation == "delete":
            if self._active(cue):
                raise AgentError("playback_active", "该条目正在播放，请先停止")
            w._push_undo()
            if scope == "cue":
                project.cues.remove(cue)
                project.drop_show_mirrors(cue.id)
            else:
                project.library.remove(cue)
            project.sync_show_mirrors()
            project.mark_dirty()
            self._refresh(selected, selected_lib)
            return {"id": cue.id, "deleted": True, "revision": self._revision()}
        if operation == "move":
            index = self._index(params.get("index"), 0, len(editable_items) - 1)
            w._push_undo()
            if scope == "cue":
                project.cues.remove(cue)
                project.cues.insert(index, cue)
            else:
                editable_items.remove(cue)
                editable_items.insert(index, cue)
                mirrors = [item for item in items if item.source_id or item.category == SHOW_MIRROR_CATEGORY]
                project.library = editable_items + mirrors
            project.sync_show_mirrors()
            project.mark_dirty()
            self._refresh(selected, selected_lib)
            return {"id": cue.id, "index": index, "item": cue.to_dict(), "revision": self._revision()}
        raise AgentError("method_not_found", f"不支持的操作：{method}")

    @staticmethod
    def _validate_trim(cue: Cue) -> None:
        if cue.trim_out > 0 and cue.trim_out <= cue.trim_in:
            raise AgentError("invalid_request", "trim_out 必须大于 trim_in，或设为 0")

    def _playback(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        w, ctl = self.window, self.window.controller
        if method == "playback.panic":
            w.on_panic()
            return {"stopped": True, "state": self._state()}
        if method in ("playback.mute", "playback.duck", "playback.hold"):
            value = self._boolean(params.get("value"), "value")
            ctl.last_error = ""
            if method == "playback.mute":
                if ctl.master_muted != value:
                    ctl.set_master_mute(value)
            elif method == "playback.duck":
                if ctl.ducked != value and ctl.set_duck(value):
                    w._fade_timer.start(50)
            elif value and not ctl.hold_active:
                w.on_toggle_hold()
            elif not value and ctl.hold_active:
                # Stop only the cover player; do not affect either audio channel.
                if ctl.video is None or not ctl.video.alive:
                    raise AgentError("playback_error", "封面状态异常，无法收起")
                ctl.exit_video()
            self._playback_error()
            w._refresh_status()
            actual = {"playback.mute": ctl.master_muted,
                      "playback.duck": ctl.ducked, "playback.hold": ctl.hold_active}[method]
            if actual != value:
                raise AgentError("playback_error", "操作未能完成")
            return {"value": actual, "state": self._state()}
        channel = params.get("channel")
        if method == "playback.seek":
            if channel not in ("show", "library_audio", "library_video"):
                raise AgentError("invalid_request", "channel 必须为 show、library_audio 或 library_video")
            ratio = self._number(params.get("ratio"), "ratio", 0, 1)
            if channel == "show":
                client = ctl._active_client()
                callback = w._on_seek
            elif channel == "library_audio":
                client = ctl.lib_audio if ctl.audio_from_library else None
                callback = w._on_library_audio_seek
            else:
                client = ctl.video if ctl.video_from_library else None
                callback = w._on_library_video_seek
            _, duration = ctl._client_progress(client)
            if client is None or not client.alive or duration is None or duration <= 0:
                raise AgentError("not_playing", "通道没有可跳转的媒体")
            ctl.last_error = ""
            callback(ratio)
            self._playback_error()
            w._refresh_status()
            return {"channel": channel, "ratio": ratio, "state": self._state()}
        if channel not in ("show", "library"):
            raise AgentError("invalid_request", "channel 必须为 show 或 library")
        if method in ("playback.stage", "playback.unstage"):
            if method == "playback.unstage":
                if ctl.video is None or not ctl.video.alive or ctl.video_from_library != (channel == "library"):
                    raise AgentError("not_playing", "该通道没有可收起的视频")
                if ctl.video_on_stage:
                    ctl.last_error = ""
                    ctl.unstage_video()
                    self._playback_error()
                w._refresh_status()
                return {"channel": channel, "staged": bool(ctl.video_on_stage), "state": self._state()}
            cue_id = params.get("id")
            ctl.last_error = ""
            w._apply_player_config()
            if cue_id is None:
                if (ctl.video is None or not ctl.video.alive or not ctl._is_active(ctl.video)
                        or ctl.video_from_library != (channel == "library")):
                    raise AgentError("not_playing", "该通道没有可全屏的视频")
                ctl.stage_loaded_video()
            else:
                cue = self._find("cue" if channel == "show" else "library", params)
                if cue.type != "video":
                    raise AgentError("invalid_request", "只有视频可以全屏")
                media = w.media_for(cue)
                if media is None or not media.is_file():
                    raise AgentError("missing_media", f"找不到媒体文件：{cue.path or '（空路径）'}")
                ctl.stage_video(cue, media, from_library=(channel == "library"))
            self._playback_error()
            if not ctl.video_on_stage:
                raise AgentError("playback_error", "未能进入全屏")
            w._refresh_status()
            return {"channel": channel, "staged": True, "state": self._state()}
        if method == "playback.play":
            scope = "cue" if channel == "show" else "library"
            cue = self._find(scope, params)
            if cue.type not in ("audio", "video"):
                raise AgentError("invalid_request", "备注不能播放")
            media = w.media_for(cue)
            if media is None or not media.is_file():
                raise AgentError("missing_media", f"找不到媒体文件：{cue.path or '（空路径）'}")
            action = ctl.go_action(cue, from_library=(channel == "library"))
            w._apply_player_config()
            if channel == "show":
                ctl.go(cue, media)
            else:
                ctl.go(cue, media, under_video=(cue.type == "audio"), from_library=True,
                       loop=w._library_loop_for(cue))
            self._playback_error()
            w._kick_fade_in()
            w._mark_show_go()
            w._refresh_status()
            return {"channel": channel, "id": cue.id, "action": action, "state": self._state()}
        if method in ("playback.pause", "playback.resume"):
            targets = ctl.pause_targets() if channel == "show" else ctl.library_pause_targets()
            if not targets:
                raise AgentError("not_playing", "该通道没有可暂停或继续的媒体")
            paused = method == "playback.pause"
            ctl.last_error = ""
            try:
                for target in targets:
                    if bool(target.props.get("pause")) != paused:
                        target.set("pause", paused)
                        target.props["pause"] = paused
                if not paused and ctl.video in targets:
                    ctl.video_ever_played = True
            except Exception as exc:
                raise AgentError("playback_error", f"控制播放失败：{exc}") from exc
            w._refresh_status()
            return {"channel": channel, "paused": paused, "state": self._state()}
        if method == "playback.stop":
            ctl.last_error = ""
            # Stop a still-loading item immediately, so it cannot start while
            # a fade-out is waiting for asynchronous mpv events.
            audio = ctl.audio if channel == "show" else ctl.lib_audio
            audio_id = ctl.audio_cue_id if channel == "show" else ctl.lib_audio_cue_id
            pending_audio = bool(audio is not None and audio.alive and audio_id
                                 and getattr(audio, "is_loading", False))
            video = ctl.video
            pending_video = bool(video is not None and video.alive and ctl.video_cue_id
                                 and ctl.video_from_library == (channel == "library")
                                 and getattr(video, "is_loading", False))
            if channel == "show":
                w.on_stop()
                if pending_audio and ctl.audio is audio:
                    ctl._stop_show_audio()
            else:
                w.on_library_stop()
                if pending_audio and ctl.lib_audio is audio:
                    ctl._stop_lib_audio()
            if pending_video and ctl.video is video:
                ctl._stop_video_only()
            self._playback_error()
            w._refresh_status()
            return {"channel": channel, "state": self._state()}
        raise AgentError("method_not_found", f"不支持的操作：{method}")

    def _playback_error(self) -> None:
        error = self.window.controller.last_error
        if error:
            raise AgentError("playback_error", str(error))

    def _volume(self, params: dict[str, Any]) -> dict[str, Any]:
        channel = params.get("channel")
        if channel not in ("show", "library"):
            raise AgentError("invalid_request", "channel 必须为 show 或 library")
        value = self._number(params.get("value"), "value", 0, 100)
        ctl = self.window.controller
        ctl.last_error = ""
        if channel == "show":
            applied = ctl.set_volume(value)
            self.window._apply_volume(applied)
        else:
            applied = ctl.set_library_volume(value)
            self.window._apply_library_volume(applied)
        self._playback_error()
        self.window._layout_timer.start()
        return {"channel": channel, "value": applied}
