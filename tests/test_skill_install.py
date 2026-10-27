from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "scripts" / "install_kongchang_skill.py"


class SkillInstallTests(unittest.TestCase):
    def test_installs_to_selected_home_and_preserves_existing_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "codex"
            command = [sys.executable, str(INSTALLER), "--codex-home", str(home)]
            first = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(first.returncode, 0, first.stderr)
            installed = home / "skills" / "kongchang-control"
            self.assertTrue((installed / "SKILL.md").is_file())
            self.assertTrue((installed / "scripts" / "agent_ctl.py").is_file())
            self.assertEqual(json.loads((installed / "app-location.json").read_text(encoding="utf-8"))["app_dir"], str(ROOT))
            marker = installed / "local-work.txt"
            marker.write_text("keep", encoding="utf-8")
            denied = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
            self.assertNotEqual(denied.returncode, 0)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
            replaced = subprocess.run(command + ["--replace"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(replaced.returncode, 0, replaced.stderr)
            backups = list((home / "skill-backups").glob("kongchang-control-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "local-work.txt").read_text(encoding="utf-8"), "keep")

    def test_cli_uses_explicit_app_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, KONGCHANG_HOME="deliberately-wrong")
            cli = ROOT / "skills" / "kongchang-control" / "scripts" / "agent_ctl.py"
            data = Path(tmp) / "data"
            data.mkdir()
            server = socket.socket()
            self.addCleanup(server.close)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            server.settimeout(5)
            (data / "agent-control.json").write_text(json.dumps({"host": "127.0.0.1", "port": server.getsockname()[1], "token": "test", "protocol": 1}), encoding="utf-8")

            def reply() -> None:
                with server.accept()[0] as connection:
                    request = json.loads(connection.makefile("rb").readline())
                    response = {"id": request["id"], "ok": True, "result": {"method": request["method"]}}
                    connection.sendall((json.dumps(response) + "\n").encode())

            worker = threading.Thread(target=reply, daemon=True)
            worker.start()
            command = [sys.executable, str(cli), "call", "system.info", "--app-dir", tmp]
            result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env)
            worker.join(timeout=5)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(json.loads(result.stdout)["result"]["method"], "system.info")


if __name__ == "__main__":
    unittest.main()
