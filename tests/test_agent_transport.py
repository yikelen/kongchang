"""Real local transport tests with an isolated discovery file and Qt loop."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from src.agent_api import AgentError
from src.agent_transport import AgentServer, MAX_REQUEST_BYTES, _restrict_file


class AgentTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="kongchang-transport-")
        self.path = Path(self.tmp.name) / "agent-control.json"
        self.seen = []

        def handler(method, params):
            self.seen.append((method, params))
            if method == "fail":
                raise AgentError("conflict", "状态已变化")
            if method == "crash":
                raise RuntimeError("private diagnostic detail")
            return {"method": method, "params": params, "thread": threading.get_ident()}

        self.server = AgentServer(handler, self.path)
        self.server.start()
        self.record = json.loads(self.path.read_text(encoding="utf-8"))

    def tearDown(self) -> None:
        self.server.close()
        self.app.processEvents()
        self.tmp.cleanup()

    def run_client(self, fn):
        output, failures = [], []

        def work():
            try:
                output.append(fn())
            except Exception as exc:
                failures.append(exc)

        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        deadline = time.monotonic() + 12
        while thread.is_alive() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertFalse(thread.is_alive(), "client timed out")
        if failures:
            raise failures[0]
        return output[0]

    def exchange(self, payload):
        def client():
            with socket.create_connection(("127.0.0.1", self.record["port"]), timeout=5) as conn:
                conn.settimeout(5)
                conn.sendall(payload)
                result = bytearray()
                while b"\n" not in result:
                    block = conn.recv(65536)
                    if not block:
                        raise RuntimeError("response closed before newline")
                    result.extend(block)
                return json.loads(bytes(result).split(b"\n", 1)[0].decode("utf-8"))
        return self.run_client(client)

    def request(self, *, method="system.info", token=None, params=None, request_id="r1"):
        return (json.dumps({"id": request_id, "method": method,
                            "params": {} if params is None else params,
                            "token": self.record["token"] if token is None else token},
                           ensure_ascii=False) + "\n").encode("utf-8")

    def test_authenticated_dispatch_runs_in_qt_thread(self):
        response = self.exchange(self.request(params={"name": "测试"}))
        self.assertTrue(response["ok"])
        self.assertEqual(response["id"], "r1")
        self.assertEqual(response["result"]["params"], {"name": "测试"})
        self.assertEqual(response["result"]["thread"], threading.get_ident())

    def test_unauthorized_and_malformed_requests_never_dispatch(self):
        self.assertEqual(self.exchange(self.request(token="wrong"))["error"]["code"], "unauthorized")
        for data in (b'{"id":1,"id":2}\n', b'{"id":NaN}\n', b'POST / HTTP/1.1\r\n',
                     self.request() + self.request(), b'\xff\n',
                     b'{"id":1,"token":"\\ud800","method":"x","params":{}}\n'):
            self.assertEqual(self.exchange(data)["error"]["code"], "invalid_request")
        self.assertEqual(self.seen, [])

    def test_large_request_and_structured_handler_error(self):
        reply = self.exchange(b"x" * (MAX_REQUEST_BYTES + 2))
        self.assertEqual(reply["error"]["code"], "request_too_large")
        reply = self.exchange(self.request(method="fail"))
        self.assertEqual(reply["error"], {"code": "conflict", "message": "状态已变化"})
        self.assertEqual(reply["id"], "r1")

    def test_unexpected_handler_error_is_sanitized_and_service_stays_live(self):
        with patch("src.agent_transport._LOG.exception"):
            reply = self.exchange(self.request(method="crash"))
        self.assertEqual(reply["error"]["code"], "internal_error")
        self.assertNotIn("private diagnostic detail", json.dumps(reply))
        self.assertTrue(self.exchange(self.request())["ok"])

    def test_idle_connection_times_out(self):
        def client():
            with socket.create_connection(("127.0.0.1", self.record["port"]), timeout=5) as conn:
                conn.settimeout(5)
                return json.loads(conn.recv(4096))
        with patch("src.agent_transport.REQUEST_TIMEOUT_MS", 80):
            reply = self.run_client(client)
        self.assertEqual(reply["error"]["code"], "timeout")

    def test_cli_from_another_directory(self):
        script = Path(__file__).resolve().parents[1] / "scripts" / "agent_ctl.py"

        def client():
            return subprocess.run(
                [sys.executable, str(script), "call", "system.info", "--params", '{"value":3}',
                 "--discovery", str(self.path)], cwd=self.tmp.name, capture_output=True,
                text=True, encoding="utf-8", timeout=10,
            )
        process = self.run_client(client)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["result"]["params"], {"value": 3})
        self.assertNotIn(self.record["token"], process.stdout + process.stderr)

    def test_other_live_instance_and_owned_cleanup(self):
        before = self.path.read_bytes()
        other = AgentServer(lambda *_: None, self.path)
        with self.assertRaises(OSError):
            other.start()
        other.close()
        self.assertEqual(self.path.read_bytes(), before)
        third = AgentServer(lambda *_: None, self.path)
        with self.assertRaises(OSError):
            third.start()
        third.close()
        self.path.write_text('{"token":"replacement"}', encoding="utf-8")
        self.server.close()
        self.server.close()
        self.assertTrue(self.path.exists())
        self.path.unlink()
        other.start()
        other.close()
        self.assertFalse(self.path.exists())

    def test_stale_discovery_and_lock_recover_after_process_crash(self):
        crash_path = Path(self.tmp.name) / "crashed.json"
        code = (
            "import os,sys; from pathlib import Path; "
            "from PySide6.QtCore import QCoreApplication; "
            "from src.agent_transport import AgentServer; "
            "app=QCoreApplication([]); "
            "server=AgentServer(lambda method,params: {}, Path(sys.argv[1])); "
            "server.start(); os._exit(0)"
        )
        process = subprocess.run(
            [sys.executable, "-c", code, str(crash_path)],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=10,
        )
        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", "replace"))
        self.assertTrue(crash_path.exists())
        recovered = AgentServer(lambda *_: None, crash_path)
        recovered.start()
        recovered.close()
        self.assertFalse(crash_path.exists())

    def test_acl_is_set_before_token_is_written_and_failure_cleans_up(self):
        other_path = Path(self.tmp.name) / "failure.json"
        observed = []

        def fail_empty(path):
            observed.append(path.read_bytes())
            raise OSError("no ACL")

        other = AgentServer(lambda *_: None, other_path)
        with patch("src.agent_transport._restrict_file", side_effect=fail_empty):
            with self.assertRaises(OSError):
                other.start()
        self.assertEqual(observed, [b""])
        self.assertFalse(other_path.exists())
        self.assertFalse(list(Path(self.tmp.name).glob(".agent-control-*.tmp")))
        other.start()
        other.close()
        self.assertFalse(other_path.exists())


if __name__ == "__main__":
    unittest.main()
