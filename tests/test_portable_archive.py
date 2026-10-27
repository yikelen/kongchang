"""Portable packages must carry the Agent Skill and its usable dependencies."""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.check_portable_archive import REQUIRED_FILES, check_archive
from scripts.create_portable_archive import create_archive


class PortableArchiveTests(unittest.TestCase):
    def test_created_archive_preserves_chinese_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "kongchang"
            source.mkdir()
            (source / "启动.bat").write_text("test", encoding="utf-8")
            archive = Path(temp) / "portable.zip"
            create_archive(source, archive)
            with zipfile.ZipFile(archive) as zf:
                self.assertEqual(zf.read("kongchang/启动.bat"), b"test")

    def test_complete_archive_passes_and_missing_skill_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "portable.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                for name in REQUIRED_FILES:
                    zf.writestr(name, "fixture")
            self.assertEqual(check_archive(archive), [])
            for omitted in ("kongchang/简易控场.exe",
                            "kongchang/skills/kongchang-control/scripts/agent_ctl.py",
                            "kongchang/vendor/python/Lib/site-packages/PySide6/plugins/platforms/qwindows.dll"):
                with self.subTest(omitted=omitted):
                    with zipfile.ZipFile(archive, "w") as zf:
                        for name in REQUIRED_FILES:
                            if name != omitted:
                                zf.writestr(name, "fixture")
                    self.assertEqual(check_archive(archive), [omitted])


if __name__ == "__main__":
    unittest.main()
