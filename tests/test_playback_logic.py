from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.controller import ShowController
from src.models import (
    LIB_PLAY_ALL,
    LIB_PLAY_DEFAULT,
    LIB_PLAY_ONE,
    LIB_PLAY_SEQ,
    SHOW_MIRROR_CATEGORY,
    Cue,
    Project,
    next_library_in_category,
    next_library_play_mode,
    rebuild_library_from_visual,
)


def _cue(cid: str, *, kind: str = "audio", category: str = "", loop: bool = False) -> Cue:
    return Cue(id=cid, name=cid, type=kind, category=category, loop=loop)


class FakeClient:
    def __init__(self, **props) -> None:
        self.alive = True
        self.media_path = "x"
        self.stopped = False
        self.props = {"idle-active": False, "path": "x", "pause": False, "eof-reached": False}
        self.props.update(props)

    def stop(self) -> None:
        self.stopped = True
        self.alive = False

    def loadfile(self, path, paused: bool, loop: bool = False) -> None:
        self.media_path = str(path)
        self.props["path"] = str(path)
        self.props["pause"] = paused
        self.props["loop-file"] = "inf" if loop else "no"
        self.props["eof-reached"] = False
        self.props["idle-active"] = False

    def set(self, name: str, value) -> None:
        self.props[name] = value

    def command(self, args, timeout: float = 1.0) -> None:
        del timeout
        self.last_command = list(args)


class NextInCategoryTests(unittest.TestCase):
    def test_stays_inside_category_and_type(self) -> None:
        a1 = _cue("a1", category="茶歇")
        a2 = _cue("a2", category="茶歇")
        a3 = _cue("a3", category="颁奖")
        v1 = _cue("v1", kind="video", category="茶歇")
        library = [a1, v1, a2, a3]
        nxt = next_library_in_category(library, a1)
        self.assertEqual(nxt.id if nxt else None, "a2")
        nxt = next_library_in_category(library, a2)
        self.assertEqual(nxt.id if nxt else None, "a1")

    def test_does_not_cross_whole_library(self) -> None:
        a1 = _cue("a1", category="茶歇")
        a2 = _cue("a2", category="颁奖")
        nxt = next_library_in_category([a1, a2], a1)
        self.assertEqual(nxt.id if nxt else None, "a1")

    def test_skips_unplayable_and_wraps(self) -> None:
        a1 = _cue("a1", category="过场")
        a2 = _cue("a2", category="过场")
        a3 = _cue("a3", category="过场")
        nxt = next_library_in_category(
            [a1, a2, a3],
            a1,
            playable=lambda cue: cue.id != "a2",
        )
        self.assertEqual(nxt.id if nxt else None, "a3")

    def test_no_wrap_at_end(self) -> None:
        a1 = _cue("a1", category="过场")
        a2 = _cue("a2", category="过场")
        nxt = next_library_in_category([a1, a2], a2, wrap=False)
        self.assertIsNone(nxt)

    def test_empty_category_groups_together(self) -> None:
        a1 = _cue("a1", category="")
        a2 = _cue("a2", category="")
        nxt = next_library_in_category([a1, a2], a1)
        self.assertEqual(nxt.id if nxt else None, "a2")


class PlayModeTests(unittest.TestCase):
    def test_cycle_order(self) -> None:
        self.assertEqual(next_library_play_mode(LIB_PLAY_DEFAULT), LIB_PLAY_ONE)
        self.assertEqual(next_library_play_mode(LIB_PLAY_ONE), LIB_PLAY_SEQ)
        self.assertEqual(next_library_play_mode(LIB_PLAY_SEQ), LIB_PLAY_ALL)
        self.assertEqual(next_library_play_mode(LIB_PLAY_ALL), LIB_PLAY_DEFAULT)

    def test_show_cues_mirror_into_uncategorized_library(self) -> None:
        show_audio = _cue("s1", kind="audio", category="")
        show_audio.path = "audio/a.mp3"
        show_audio.name = "高潮"
        show_note = Cue(id="n1", name="备注", type="note")
        project = Project(cues=[show_audio, show_note], library=[])
        self.assertTrue(project.sync_show_mirrors())
        copies = [item for item in project.library if item.source_id == "s1"]
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].name, "高潮")
        self.assertEqual(copies[0].category, SHOW_MIRROR_CATEGORY)
        self.assertFalse(any(item.source_id == "n1" for item in project.library))
        show_audio.name = "高潮改"
        project.mirror_show_cue(show_audio)
        self.assertEqual(copies[0].name, "高潮改")
        project.drop_show_mirrors("s1")
        self.assertFalse(any(item.source_id == "s1" for item in project.library))

    def test_show_mirrors_follow_show_order(self) -> None:
        a = _cue("s1", kind="audio")
        a.name = "暖场"
        v = _cue("s2", kind="video")
        v.name = "国歌"
        b = _cue("s3", kind="audio")
        b.name = "散场"
        project = Project(cues=[a, v, b], library=[])
        project.sync_show_mirrors()
        names = [item.name for item in project.library if item.source_id]
        self.assertEqual(names, ["暖场", "国歌", "散场"])
        project.cues = [b, a, v]
        project.sync_show_mirrors()
        names = [item.name for item in project.library if item.source_id]
        self.assertEqual(names, ["散场", "暖场", "国歌"])

    def test_hold_cover_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "show.json"
            project = Project(path=path, cues=[], hold_cover="covers/logo.png")
            project.save(path)
            loaded = Project.load(path)
            self.assertEqual(loaded.hold_cover, "covers/logo.png")

    def test_load_defaults_to_default_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "show.json"
            path.write_text(
                json.dumps({"version": 1, "cues": [], "library": []}, ensure_ascii=False),
                encoding="utf-8",
            )
            project = Project.load(path)
            self.assertEqual(project.library_play_mode("茶歇"), LIB_PLAY_DEFAULT)
            self.assertEqual(project.library_play_mode(""), LIB_PLAY_DEFAULT)

    def test_save_omits_default_keeps_named_modes(self) -> None:
        project = Project()
        a1 = _cue("a1", category="茶歇")
        project.library = [a1]
        project.set_library_play_mode("茶歇", LIB_PLAY_ALL)
        project.set_library_play_mode("颁奖", LIB_PLAY_SEQ)
        data = project.to_dict()
        self.assertEqual(data["library_play_modes"], {"茶歇": LIB_PLAY_ALL})

    def test_rebuild_moves_item_into_drop_category(self) -> None:
        a1 = _cue("a1", category="茶歇")
        a2 = _cue("a2", category="颁奖")
        visual = [
            ("header", "茶歇"),
            ("header", "颁奖"),
            ("cue", "a1"),
            ("cue", "a2"),
        ]
        rebuilt = rebuild_library_from_visual({"a1": a1, "a2": a2}, visual)
        self.assertEqual([cue.id for cue in rebuilt], ["a1", "a2"])
        self.assertEqual(a1.category, "颁奖")
        self.assertEqual(a2.category, "颁奖")

    def test_sequence_does_not_wrap(self) -> None:
        a1 = _cue("a1", category="过场")
        a2 = _cue("a2", category="过场")
        nxt = next_library_in_category([a1, a2], a2, wrap=False)
        self.assertIsNone(nxt)


class IsolationTests(unittest.TestCase):
    def test_show_video_stops_show_audio(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "clip.mp4"
            media.write_bytes(b"x")
            ctl = ShowController()
            audio = FakeClient()
            ctl.audio = audio
            ctl.audio_cue_id = "show-a"
            cue = _cue("show-v", kind="video")
            ctl._activate_video(cue, media, from_library=False, autoplay=False)
            self.assertTrue(audio.stopped)

    def test_show_and_library_audio_are_mutex(self) -> None:
        ctl = ShowController()
        show = FakeClient()
        ctl.audio = show
        ctl.audio_cue_id = "show-a"
        lib = FakeClient()
        ctl.lib_audio = lib
        ctl.lib_audio_cue_id = "lib-a"
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "bed.mp3"
            media.write_bytes(b"x")
            cue = _cue("lib-b", kind="audio")
            ctl._activate_audio(cue, media, from_library=True, stop_video=False)
            self.assertTrue(show.stopped)
            self.assertFalse(lib.stopped)

    def test_library_other_video_is_cut_not_preview(self) -> None:
        ctl = ShowController()
        ctl.video = FakeClient()
        ctl.video_cue_id = "playing"
        ctl.video_from_library = True
        ctl.video_ever_played = True
        other = _cue("other", kind="video")
        self.assertEqual(ctl.go_action(other, from_library=True), "play")
        self.assertEqual(ctl.go_action(other, from_library=False), "preview")
        playing = _cue("playing", kind="video")
        self.assertEqual(ctl.go_action(playing, from_library=True), "playing")

    def test_replace_video_keeps_player_and_fullscreen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            media = Path(tmp) / "next.mp4"
            media.write_bytes(b"x")
            ctl = ShowController()
            video = FakeClient(fullscreen=True)
            ctl.video = video
            ctl.video_cue_id = "old"
            ctl.video_on_stage = True
            ctl.video_from_library = True
            ctl.video_ever_played = True
            nxt = _cue("new", kind="video", category="采访")
            ctl._activate_video(nxt, media, from_library=True, autoplay=True)
            self.assertFalse(video.stopped)
            self.assertIs(ctl.video, video)
            self.assertTrue(ctl.video_on_stage)
            self.assertEqual(ctl.video_cue_id, "new")
            self.assertEqual(video.props.get("pause"), False)
            self.assertNotEqual(video.props.get("fullscreen"), False)

    def test_show_pause_ignores_library_audio(self) -> None:
        ctl = ShowController()
        ctl.lib_audio = FakeClient()
        ctl.lib_audio_cue_id = "lib-a"
        self.assertEqual(ctl.pause_targets(), [])
        self.assertTrue(ctl.audio_from_library)

    def test_main_pause_ignores_library_video(self) -> None:
        ctl = ShowController()
        ctl.video = FakeClient()
        ctl.video_from_library = True
        ctl.video_cue_id = "lib-v"
        self.assertEqual(ctl.pause_targets(), [])

    def test_main_progress_ignores_library_video(self) -> None:
        ctl = ShowController()
        ctl.video = FakeClient(pause=False)
        ctl.video_from_library = True
        self.assertIsNone(ctl._active_client())

    def test_fade_stop_does_not_kill_library_video(self) -> None:
        ctl = ShowController()
        video = FakeClient()
        ctl.video = video
        ctl.video_from_library = True
        ctl.video_cue_id = "lib-v"
        ctl.fade_stop()
        self.assertFalse(video.stopped)
        self.assertTrue(video.alive)

    def test_library_eof_prefers_audio_bed(self) -> None:
        ctl = ShowController()
        ctl.lib_audio = FakeClient(pause=True, **{"eof-reached": True})
        ctl.lib_audio_cue_id = "a"
        ctl.video = FakeClient(pause=False, **{"eof-reached": False})
        ctl.video_from_library = True
        self.assertTrue(ctl.library_reached_eof())


if __name__ == "__main__":
    unittest.main()
