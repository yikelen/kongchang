"""Portable packages must carry the Agent Skill and its usable dependencies."""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.check_portable_archive import REQUIRED_FILES, check_archive


class PortableArchiveTests(unittest.TestCase):
    def test_complete_archive_passes_and_missing_skill_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "portable.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                for name in REQUIRED_FILES:
                    zf.writestr(name, "fixture")
            self.assertEqual(check_archive(archive), [])
            omitted = "kongchang/skills/kongchang-control/scripts/agent_ctl.py"
            with zipfile.ZipFile(archive, "w") as zf:
                for name in REQUIRED_FILES:
                    if name != omitted:
                        zf.writestr(name, "fixture")
            self.assertEqual(check_archive(archive), [omitted])


if __name__ == "__main__":
    unittest.main()
