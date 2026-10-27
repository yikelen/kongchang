"""Regression checks for the v0.2.4 controls in the redesigned window."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.settings import AppSettings
from src.ui.main_window import MainWindow
from test_playback_logic import FakeClient


class MigratedWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
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

    def tearDown(self) -> None:
        self.window._force_closing = True
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        for item in reversed(self.patches):
            item.stop()

    def test_panic_button_stops_all_channels_and_retains_mute(self) -> None:
        controller = self.window.controller
        clients = [FakeClient() for _ in range(3)]
        controller.audio, controller.lib_audio, controller.video = clients
        controller.audio_cue_id, controller.lib_audio_cue_id, controller.video_cue_id = "a", "b", "v"
        controller.video_on_stage = True
        controller.master_muted = True
        self.window.panic_btn.click()
        self.assertTrue(all(client.stopped for client in clients))
        self.assertIsNone(controller.audio)
        self.assertIsNone(controller.lib_audio)
        self.assertIsNone(controller.video)
        self.assertFalse(controller.video_on_stage)
        self.assertTrue(controller.master_muted)

    def test_panic_shortcut_and_show_mode_keep_library_controls(self) -> None:
        fired = []
        self.window.panic_shortcut.activated.connect(lambda: fired.append(True))
        self.window.side_tabs.setCurrentIndex(1)
        self.window.name_edit.setFocus()
        QTest.keyClick(self.window.name_edit, Qt.Key.Key_Escape, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(fired, [True])
        self.window.side_tabs.setCurrentIndex(1)
        self.window._set_show_mode(True, persist=False)
        self.assertEqual(self.window.side_tabs.currentIndex(), 0)
        self.assertFalse(self.window.side_tabs.isTabVisible(1))
        self.assertTrue(self.window.library_bed.isVisible())
        self.window._set_show_mode(False, persist=False)
        self.assertTrue(self.window.side_tabs.isTabVisible(1))

    def test_new_media_opens_its_editor(self) -> None:
        self.window.add_media("audio")
        self.app.processEvents()
        self.assertEqual(self.window.side_tabs.currentIndex(), 1)
        self.assertTrue(self.window.name_edit.isVisible())
        self.window.side_tabs.setCurrentIndex(0)
        self.window.add_library_media("video")
        self.app.processEvents()
        self.assertEqual(self.window.side_tabs.currentIndex(), 1)
        self.assertTrue(self.window.name_edit.isVisible())
        self.assertEqual(self.window.active_cue().type, "video")

    def test_library_audio_and_video_show_independent_progress(self) -> None:
        controller = self.window.controller
        controller.lib_audio = FakeClient(**{"time-pos": 10, "duration": 100})
        controller.lib_audio_cue_id = "audio"
        controller.video = FakeClient(**{"time-pos": 30, "duration": 60})
        controller.video_cue_id = "video"
        controller.video_from_library = True
        self.window._refresh_library_audio_transport()
        self.app.processEvents()
        self.assertTrue(self.window.library_audio_row.isVisible())
        self.assertTrue(self.window.library_video_row.isVisible())
        self.assertEqual(self.window.library_audio_bar.value(), 100)
        self.assertEqual(self.window.library_video_bar.value(), 500)
        self.assertTrue(self.window.library_stop_bed_btn.isEnabled())
        self.assertTrue(self.window.library_stop_video_btn.isEnabled())

    def test_independent_seek_controls_have_clickable_tracks(self) -> None:
        for bar in (self.window.progress_bar, self.window.library_audio_bar, self.window.library_video_bar):
            bar.setEnabled(True)
            bar.resize(200, 20)
            values = []
            bar.seeked.connect(values.append)
            QTest.mouseClick(bar, Qt.MouseButton.LeftButton, pos=QPoint(100, 1))
            self.assertAlmostEqual(values[-1], 0.5, places=2)
        self.assertIsNot(self.window.library_audio_bar, self.window.library_video_bar)


if __name__ == "__main__":
    unittest.main()
