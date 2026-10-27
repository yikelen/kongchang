"""Exercise the native launcher against a harmless fake bundled runtime."""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
CSC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"


@unittest.skipUnless(os.name == "nt" and CSC.is_file(), "Windows .NET Framework compiler required")
class LauncherTests(unittest.TestCase):
    def test_launcher_passes_script_and_working_directory_with_unicode_and_spaces(self) -> None:
        with tempfile.TemporaryDirectory(prefix="kongchang-launcher-") as temp:
            root = Path(temp) / "测试 app"
            runtime = root / "vendor" / "python"
            scripts = root / "scripts"
            runtime.mkdir(parents=True)
            scripts.mkdir()
            (scripts / "run_app.py").write_text("# fixture", encoding="utf-8")
            spy = root / "spy.cs"
            spy.write_text(
                'using System; using System.IO; class Spy { static void Main(string[] args) '
                '{ File.WriteAllText(Path.Combine(Directory.GetCurrentDirectory(), "capture.txt"), '
                'args[0] + "|" + Directory.GetCurrentDirectory() + "|" + '
                'Environment.GetEnvironmentVariable("KONGCHANG_PORTABLE")); } }', encoding="utf-8"
            )
            subprocess.run([str(CSC), "/nologo", "/target:winexe", f"/out:{runtime / 'pythonw.exe'}", str(spy)],
                           check=True, capture_output=True)
            subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(ROOT / "scripts" / "build_launcher.ps1"), "-OutputDirectory", str(root)],
                           check=True, capture_output=True)
            subprocess.run([str(root / "简易控场.exe")], check=True, timeout=10)
            result = root / "capture.txt"
            deadline = time.monotonic() + 10
            while not result.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(result.exists(), "the bundled executable was not started")
            self.assertEqual(result.read_text(encoding="utf-8-sig"), f"{scripts / 'run_app.py'}|{root}|1")

    def test_portable_mode_skips_automatic_desktop_shortcut(self) -> None:
        from src.ui.main_window import MainWindow

        settings = SimpleNamespace(desktop_shortcut_created=False, save=Mock())
        window = SimpleNamespace(settings=settings)
        with patch("src.shortcut.create_shortcuts") as create, patch.dict(os.environ, {"KONGCHANG_PORTABLE": "1"}):
            MainWindow._maybe_create_desktop_shortcut(window)
            create.assert_not_called()
            settings.save.assert_not_called()
        with patch("src.shortcut.create_shortcuts") as create, patch.dict(os.environ, {"KONGCHANG_PORTABLE": "0"}):
            MainWindow._maybe_create_desktop_shortcut(window)
            create.assert_called_once_with()
            settings.save.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
