"""Behavioral tests for the local agent interface, using an isolated Qt window."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.agent_api import AgentAPI, AgentError
from src.models import Cue
from src.settings import AppSettings
from src.ui.main_window import MainWindow
from test_playback_logic import FakeClient


class AgentAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="kongchang-agent-tests-")
        self.patches = [
            patch.object(AppSettings, "load", return_value=AppSettings()),
            patch.object(AppSettings, "save"),
            patch.object(MainWindow, "_warm_players"),
            patch.object(MainWindow, "_maybe_create_desktop_shortcut"),
            patch.object(MainWindow, "_rebuild_audio_menu"),
            patch("src.show_log.log"),
        ]
        for item in self.patches:
            item.start()
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()
        self.api = AgentAPI(self.window)

    def tearDown(self) -> None:
        self.window._force_closing = True
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        for item in reversed(self.patches):
            item.stop()
        self.temporary.cleanup()

    def call(self, method: str, params: dict | None = None):
        return self.api.dispatch(method, params or {})

    def test_read_methods_return_json_serializable_data(self) -> None:
        for method in ("system.info", "state.get", "project.get"):
            result = self.call(method)
            self.assertIsInstance(result, dict)
            json.dumps(result, ensure_ascii=False)

    def test_show_cue_create_update_move_delete_and_mirrors(self) -> None:
        self.call("cue.add", {"type": "audio", "name": "开场", "path": "music/open.wav"})
        self.call("cue.add", {"type": "video", "name": "短片", "path": "video/intro.mp4"})
        self.assertEqual([c.name for c in self.window.project.cues], ["开场", "短片"])
        first, second = self.window.project.cues
        first_id, second_id = first.id, second.id
        mirrors = {c.source_id: c for c in self.window.project.library if c.source_id}
        self.assertEqual(set(mirrors), {first_id, second_id})
        self.assertEqual(mirrors[first_id].name, "开场")
        self.assertTrue(self.window.project.dirty)
        self.assertEqual(self.window.table.rowCount(), 2)

        self.call("cue.update", {"id": first_id, "changes": {"name": "开场音乐", "notes": "主持人上台"}})
        mirror = next(c for c in self.window.project.library if c.source_id == first_id)
        self.assertEqual((mirror.name, mirror.notes), ("开场音乐", "主持人上台"))
        self.call("cue.move", {"id": second_id, "index": 0})
        self.assertEqual([c.id for c in self.window.project.cues], [second_id, first_id])
        self.assertEqual([c.source_id for c in self.window.project.library if c.source_id], [second_id, first_id])
        self.call("cue.delete", {"id": first_id})
        self.assertEqual([c.id for c in self.window.project.cues], [second_id])
        self.assertFalse(any(c.source_id == first_id for c in self.window.project.library))
        self.assertEqual(self.window.table.rowCount(), 1)

    def test_library_create_update_move_delete(self) -> None:
        self.call("library.add", {"type": "audio", "name": "茶歇一", "category": "茶歇"})
        self.call("library.add", {"type": "audio", "name": "茶歇二", "category": "茶歇"})
        first, second = (c for c in self.window.project.library if not c.source_id)
        first_id, second_id = first.id, second.id
        self.call("library.update", {"id": first_id, "changes": {"name": "茶歇改", "notes": "低音量"}})
        self.assertEqual(next(c.name for c in self.window.project.library if c.id == first_id), "茶歇改")
        self.call("library.move", {"id": second_id, "index": 0})
        self.assertEqual([c.id for c in self.window.project.library if not c.source_id], [second_id, first_id])
        self.call("library.delete", {"id": first_id})
        self.assertFalse(any(c.id == first_id for c in self.window.project.library))

    def test_mirrored_library_entries_cannot_be_mutated_directly(self) -> None:
        self.call("cue.add", {"type": "audio", "name": "开场"})
        mirror = next(c for c in self.window.project.library if c.source_id)
        for method, params in (
            ("library.update", {"id": mirror.id, "changes": {"name": "不能改"}}),
            ("library.delete", {"id": mirror.id}),
        ):
            with self.subTest(method=method), self.assertRaises(AgentError):
                self.call(method, params)
        self.assertEqual(self.window.project.cues[0].name, "开场")
        self.assertTrue(any(c.id == mirror.id for c in self.window.project.library))

    def test_invalid_requests_and_lock_do_not_modify_project(self) -> None:
        before = self.window._snapshot_project()
        for method, params in (
            ("unknown.action", {}),
            ("cue.add", {"type": "unknown", "name": "错误"}),
            ("library.add", {"type": "note", "name": "错误"}),
            ("cue.update", {"id": "missing", "changes": {"name": "不存在"}}),
            ("cue.delete", {"id": "missing"}),
            ("cue.move", {"id": "missing", "index": 0}),
        ):
            with self.subTest(method=method), self.assertRaises(AgentError):
                self.call(method, params)
        self.assertEqual(self.window._snapshot_project(), before)
        self.window._cues_locked = True
        with self.assertRaises(AgentError):
            self.call("cue.add", {"type": "note", "name": "锁定时新增"})
        self.assertEqual(self.window._snapshot_project(), before)

    def test_agent_mutation_participates_in_undo(self) -> None:
        self.call("cue.add", {"type": "note", "name": "撤销测试"})
        self.assertEqual(len(self.window.project.cues), 1)
        self.window.on_undo()
        self.assertEqual(len(self.window.project.cues), 0)
        self.window.on_redo()
        self.assertEqual([c.name for c in self.window.project.cues], ["撤销测试"])

    def test_save_as_preserves_media_paths_in_undo_and_redo(self) -> None:
        root = Path(self.temporary.name)
        source, target = root / "source", root / "target"
        source.mkdir()
        target.mkdir()
        self.call("project.create", {"path": str(source / "show.json")})
        item = self.call("cue.add", {"type": "audio", "name": "原名", "path": "media/track.wav"})
        self.call("cue.update", {"id": item["id"], "changes": {"name": "新名"}})
        self.call("project.save_as", {"path": str(target / "copy.json")})
        for action, name in ((self.window.on_undo, "原名"), (self.window.on_redo, "新名")):
            action()
            cue = self.window.project.cues[0]
            self.assertEqual(cue.name, name)
            self.assertEqual(self.window.project.resolve_media(cue).resolve(), (source / "media/track.wav").resolve())

    def test_save_rejects_unsaved_project_and_saves_existing_path(self) -> None:
        self.assertIsNone(self.window.project.path)
        with self.assertRaises(AgentError):
            self.call("project.save")
        self.call("cue.add", {"type": "note", "name": "保存测试"})
        path = Path(self.temporary.name) / "show.json"
        self.window.project.path = path
        self.call("project.save")
        self.assertTrue(path.is_file())
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["cues"][0]["name"], "保存测试")
        self.assertFalse(self.window.project.dirty)

    def test_revision_conflict_does_not_overwrite_newer_changes(self) -> None:
        original = self.call("project.get")["revision"]
        self.call("cue.add", {"type": "note", "name": "新内容", "expected_revision": original})
        before = self.window._snapshot_project()
        with self.assertRaises(AgentError) as error:
            self.call("cue.add", {"type": "note", "name": "旧请求", "expected_revision": original})
        self.assertEqual(error.exception.code, "revision_conflict")
        self.assertEqual(self.window._snapshot_project(), before)

    def test_uncommitted_editor_name_is_not_overwritten_by_agent(self) -> None:
        self.call("cue.add", {"type": "note", "name": "原名称"})
        self.window.side_tabs.setCurrentIndex(1)
        self.window.name_edit.setFocus()
        self.window.name_edit.setText("正在输入")
        self.app.processEvents()
        with self.assertRaises(AgentError) as error:
            self.call("cue.add", {"type": "note", "name": "另一个"})
        self.assertEqual(error.exception.code, "editor_busy")
        self.assertEqual(self.window.name_edit.text(), "正在输入")
        self.assertEqual(len(self.window.project.cues), 1)

    def test_missing_media_and_invalid_volume_fail_without_playback(self) -> None:
        self.call("cue.add", {"type": "audio", "name": "缺失", "path": "missing.wav"})
        cue_id = self.window.project.cues[0].id
        with self.assertRaises(AgentError) as error:
            self.call("playback.play", {"channel": "show", "id": cue_id})
        self.assertEqual(error.exception.code, "missing_media")
        self.assertIsNone(self.window.controller.audio)
        for value in (-1, 101, True, "50"):
            with self.subTest(value=value), self.assertRaises(AgentError):
                self.call("volume.set", {"channel": "show", "value": value})

    def test_play_command_does_not_require_gui_keyboard_focus(self) -> None:
        media = Path(self.temporary.name) / "example.wav"
        media.write_bytes(b"test placeholder")
        self.call("cue.add", {"type": "audio", "name": "播放目标", "path": str(media)})
        cue = self.window.project.cues[0]
        self.window.side_tabs.setCurrentIndex(1)
        self.window.name_edit.setFocus()
        self.app.processEvents()
        with patch.object(self.window.controller, "go") as play, \
             patch.object(self.window, "_apply_player_config"), \
             patch.object(self.window, "_kick_fade_in"), \
             patch.object(self.window, "_mark_show_go"):
            result = self.call("playback.play", {"channel": "show", "id": cue.id})
        play.assert_called_once()
        self.assertEqual(result["id"], cue.id)
        self.assertTrue(self.window.name_edit.hasFocus())

    def test_create_and_open_project_preserve_existing_files(self) -> None:
        path = Path(self.temporary.name) / "new-show.json"
        created = self.call("project.create", {"path": str(path)})
        self.assertEqual(Path(created["path"]), path)
        self.assertTrue(path.is_file())
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["cues"], [])
        existing = path.read_bytes()
        with self.assertRaises(AgentError) as error:
            self.call("project.create", {"path": str(path)})
        self.assertEqual(error.exception.code, "already_exists")
        self.assertEqual(path.read_bytes(), existing)
        second = Path(self.temporary.name) / "second-show.json"
        second.write_text(json.dumps({"version": 1, "cues": [{"id": "note", "type": "note", "name": "现有条目"}]}), encoding="utf-8")
        opened = self.call("project.open", {"path": str(second)})
        self.assertEqual(Path(opened["path"]), second)
        self.assertEqual([cue.name for cue in self.window.project.cues], ["现有条目"])

    def test_switching_projects_does_not_reuse_previous_project_undo(self) -> None:
        first = Path(self.temporary.name) / "first.json"
        second = Path(self.temporary.name) / "second.json"
        self.call("project.create", {"path": str(first)})
        self.call("cue.add", {"type": "note", "name": "工程一的内容"})
        self.call("project.save")
        second.write_text(json.dumps({"version": 1, "cues": [{"id": "b", "type": "note", "name": "工程二的内容"}]}), encoding="utf-8")
        self.call("project.open", {"path": str(second)})
        self.window.on_undo()
        self.assertEqual([c.name for c in self.window.project.cues], ["工程二的内容"])
        self.assertFalse(self.window.project.dirty)

    def test_project_switch_rejects_dirty_or_playing_without_losing_state(self) -> None:
        target = Path(self.temporary.name) / "target.json"
        target.write_text(json.dumps({"version": 1, "cues": []}), encoding="utf-8")
        self.call("cue.add", {"type": "note", "name": "未保存"})
        with self.assertRaises(AgentError) as error:
            self.call("project.open", {"path": str(target)})
        self.assertEqual(error.exception.code, "project_dirty")
        self.assertEqual(self.window.project.cues[0].name, "未保存")
        self.window.project.dirty = False
        active = FakeClient()
        self.window.controller.audio = active
        self.window.controller.audio_cue_id = "active"
        with self.assertRaises(AgentError) as error:
            self.call("project.open", {"path": str(target)})
        self.assertEqual(error.exception.code, "playback_active")
        self.assertTrue(active.alive)
        self.assertEqual(self.window.project.cues[0].name, "未保存")

    def test_stop_during_loading_stops_the_requested_channel(self) -> None:
        for channel, attribute, id_attribute in (("show", "audio", "audio_cue_id"),
                                                  ("library", "lib_audio", "lib_audio_cue_id")):
            with self.subTest(channel=channel):
                client = FakeClient(**{"idle-active": True})
                client.media_path = "loading.wav"
                client.is_loading = True
                setattr(self.window.controller, attribute, client)
                setattr(self.window.controller, id_attribute, "loading")
                self.call("playback.stop", {"channel": channel})
                self.assertTrue(client.stopped)
                self.assertIsNone(getattr(self.window.controller, attribute))

    def test_loading_media_blocks_project_switch_and_delete(self) -> None:
        source = Path(self.temporary.name) / "source.json"
        other = Path(self.temporary.name) / "other.json"
        self.call("project.create", {"path": str(source)})
        item_id = self.call("cue.add", {"type": "audio", "name": "加载中"})["id"]
        self.call("project.save")
        other.write_text(json.dumps({"version": 1, "cues": []}), encoding="utf-8")
        client = FakeClient(**{"idle-active": True})
        client.media_path = "loading.wav"
        client.is_loading = True
        self.window.controller.audio = client
        self.window.controller.audio_cue_id = item_id
        with self.assertRaises(AgentError) as error:
            self.call("project.open", {"path": str(other)})
        self.assertEqual(error.exception.code, "playback_active")
        with self.assertRaises(AgentError) as error:
            self.call("cue.delete", {"id": item_id})
        self.assertEqual(error.exception.code, "playback_active")
        self.assertEqual(self.window.project.path, source)
        self.assertTrue(client.alive)

    def test_finished_idle_media_does_not_block_project_switch(self) -> None:
        source = Path(self.temporary.name) / "source.json"
        other = Path(self.temporary.name) / "other.json"
        self.call("project.create", {"path": str(source)})
        item_id = self.call("cue.add", {"type": "audio", "name": "已结束"})["id"]
        self.call("project.save")
        other.write_text(json.dumps({"version": 1, "cues": []}), encoding="utf-8")
        client = FakeClient(**{"idle-active": True, "eof-reached": True})
        client.media_path = "finished.wav"
        client.is_loading = False
        self.window.controller.audio = client
        self.window.controller.audio_cue_id = item_id
        self.call("project.open", {"path": str(other)})
        self.assertEqual(self.window.project.path, other)

    def test_save_as_rebases_media_and_cover_and_refuses_overwrite(self) -> None:
        root = Path(self.temporary.name)
        source = root / "source"
        target = root / "target"
        source.mkdir()
        target.mkdir()
        (source / "media").mkdir()
        audio = source / "media" / "track.wav"
        audio.write_bytes(b"sample")
        cover = source / "cover.png"
        cover.write_bytes(b"sample")
        original = source / "original.json"
        self.call("project.create", {"path": str(original)})
        self.call("cue.add", {"type": "audio", "name": "开场", "path": "media/track.wav"})
        cue = self.window.project.cues[0]
        cue_id = cue.id
        self.window.project.hold_cover = "cover.png"
        self.window.project.mark_dirty()
        destination = target / "copy.json"
        result = self.call("project.save_as", {"path": str(destination)})
        self.assertEqual(Path(result["path"]), destination)
        self.assertIs(self.window.project.cues[0], cue)
        self.assertEqual(self.window.project.cues[0].id, cue_id)
        self.assertEqual(self.window.project.resolve_media(cue).resolve(), audio.resolve())
        self.assertEqual(self.window.project.resolve_hold_cover().resolve(), cover.resolve())
        mirror = next(item for item in self.window.project.library if item.source_id == cue_id)
        self.assertEqual(self.window.project.resolve_media(mirror).resolve(), audio.resolve())
        self.assertFalse(self.window.project.dirty)
        previous = destination.read_bytes()
        with self.assertRaises(AgentError) as error:
            self.call("project.save_as", {"path": str(destination)})
        self.assertEqual(error.exception.code, "already_exists")
        self.assertEqual(destination.read_bytes(), previous)
        self.assertIs(self.window.project.cues[0], cue)
        self.assertEqual(self.window.project.resolve_media(cue).resolve(), audio.resolve())

    def test_fullscreen_requires_correct_video_channel_and_unstage_is_idempotent(self) -> None:
        with self.assertRaises(AgentError) as error:
            self.call("playback.stage", {"channel": "show"})
        self.assertEqual(error.exception.code, "not_playing")
        controller = self.window.controller
        controller.video = FakeClient()
        controller.video_cue_id = "lib-video"
        controller.video_from_library = True
        with self.assertRaises(AgentError) as error:
            self.call("playback.stage", {"channel": "show"})
        self.assertEqual(error.exception.code, "not_playing")
        with patch.object(self.window, "_apply_player_config"), \
             patch.object(controller, "stage_loaded_video", side_effect=lambda: setattr(controller, "video_on_stage", True)) as stage, \
             patch.object(controller, "unstage_video", side_effect=lambda: setattr(controller, "video_on_stage", False)) as unstage:
            staged = self.call("playback.stage", {"channel": "library"})
            self.assertTrue(staged["staged"])
            stage.assert_called_once()
            with self.assertRaises(AgentError) as error:
                self.call("playback.unstage", {"channel": "show"})
            self.assertEqual(error.exception.code, "not_playing")
            unstaged = self.call("playback.unstage", {"channel": "library"})
            self.assertFalse(unstaged["staged"])
            self.assertFalse(self.call("playback.unstage", {"channel": "library"})["staged"])
            unstage.assert_called_once()

    def test_fullscreen_selected_video_requires_valid_media_and_type(self) -> None:
        self.call("cue.add", {"type": "note", "name": "备注"})
        cue_id = self.window.project.cues[0].id
        with patch.object(self.window, "_apply_player_config"):
            with self.assertRaises(AgentError) as error:
                self.call("playback.stage", {"channel": "show", "id": cue_id})
            self.assertEqual(error.exception.code, "invalid_request")
            self.call("library.add", {"type": "video", "name": "丢失视频", "path": "missing.mp4"})
            video_id = next(c.id for c in self.window.project.library if not c.source_id)
            with self.assertRaises(AgentError) as error:
                self.call("playback.stage", {"channel": "library", "id": video_id})
            self.assertEqual(error.exception.code, "missing_media")

    def test_panic_stops_all_actual_controller_channels(self) -> None:
        controller = self.window.controller
        clients = [FakeClient() for _ in range(3)]
        controller.audio, controller.lib_audio, controller.video = clients
        controller.audio_cue_id, controller.lib_audio_cue_id, controller.video_cue_id = "a", "b", "v"
        controller.video_on_stage = True
        controller.master_muted = True
        self.call("playback.panic")
        self.assertTrue(all(client.stopped for client in clients))
        self.assertIsNone(controller.audio)
        self.assertIsNone(controller.lib_audio)
        self.assertIsNone(controller.video)
        self.assertFalse(controller.video_on_stage)
        self.assertTrue(controller.master_muted)


if __name__ == "__main__":
    unittest.main()
