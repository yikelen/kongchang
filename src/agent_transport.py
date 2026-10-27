"""Authenticated, local-only transport for the running Qt application.

Requests are UTF-8 JSON objects terminated by a newline. All dispatch happens
on the Qt thread, so handlers may safely interact with the window and model.
"""
from __future__ import annotations

import hmac
import json
import logging
import math
import os
import re
import secrets
import socket
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, QLockFile
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QTcpServer, QTcpSocket

from src.agent_api import AgentError

HOST = "127.0.0.1"
PROTOCOL = 1
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_CONNECTIONS = 32
REQUEST_TIMEOUT_MS = 10000
_LOG = logging.getLogger(__name__)


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("重复的 JSON 字段")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("JSON 数字必须是有限值")
    return number


def _invalid_constant(_value: str) -> None:
    raise ValueError("JSON 不允许非有限数字")


def _restrict_file(path: Path) -> None:
    """Grant the discovery file only to this Windows user, or mode 0600 on POSIX."""
    if os.name != "nt":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
        return
    system = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        identity = subprocess.run(
            [str(system / "whoami.exe"), "/user", "/fo", "csv", "/nh"],
            check=True, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=5, creationflags=flags,
        ).stdout
        match = re.search(r"S-1-(?:\d+-)*\d+", identity)
        if match is None:
            raise OSError("无法确定当前用户 SID")
        subprocess.run(
            [str(system / "icacls.exe"), str(path), "/inheritance:r", "/grant:r", f"*{match.group(0)}:(F)"],
            check=True, capture_output=True, timeout=5, creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise OSError("无法设置 Agent 控制文件权限") from exc


def _endpoint_is_listening(path: Path) -> bool:
    """Avoid replacing another live instance's discovery record."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("host") != HOST:
            return False
        port = data.get("port")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            return False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.2)
            return probe.connect_ex((HOST, port)) == 0
    except (OSError, ValueError, TypeError):
        return False


class AgentServer(QObject):
    """Dispatch authenticated local requests in the owner Qt thread."""

    def __init__(
        self, handler: Callable[[str, dict[str, Any]], Any], discovery_path: Path | str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._handler = handler
        self.discovery_path = Path(discovery_path)
        # The lock is held for the lifetime of the endpoint, not just while writing
        # the discovery record, so two simultaneous launches cannot overwrite it.
        self._discovery_lock = QLockFile(str(self.discovery_path) + ".lock")
        self._discovery_lock.setStaleLockTime(0)
        self._server = QTcpServer(self)
        self._server.setMaxPendingConnections(MAX_CONNECTIONS)
        self._server.newConnection.connect(self._accept_connections)
        self._token: str | None = None
        self._connections: dict[QTcpSocket, tuple[bytearray, QTimer]] = {}

    def start(self) -> None:
        if self._server.isListening():
            return
        self.discovery_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._discovery_lock.tryLock(0):
            raise OSError("已有 Agent 控制服务正在运行或控制文件已锁定")
        temp_name: str | None = None
        try:
            if _endpoint_is_listening(self.discovery_path):
                raise OSError("已有 Agent 控制服务正在运行")
            if not self._server.listen(QHostAddress(HOST), 0):
                raise OSError(f"Agent 控制服务启动失败：{self._server.errorString()}")
            token = secrets.token_urlsafe(32)
            record = {"host": HOST, "port": self._server.serverPort(), "token": token,
                      "pid": os.getpid(), "protocol": PROTOCOL}
            descriptor, temp_name = tempfile.mkstemp(prefix=".agent-control-", suffix=".tmp", dir=self.discovery_path.parent)
            # Do not write the token until the empty file has a restrictive ACL.
            os.close(descriptor)
            _restrict_file(Path(temp_name))
            with open(temp_name, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(record, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            # Protect a live endpoint even if it was created by an older version
            # of the transport that did not use the lock file.
            if _endpoint_is_listening(self.discovery_path):
                raise OSError("已有 Agent 控制服务正在运行")
            os.replace(temp_name, self.discovery_path)
            temp_name = None
            self._token = token
        except Exception:
            self._server.close()
            self._discovery_lock.unlock()
            if temp_name is not None:
                try:
                    Path(temp_name).unlink()
                except FileNotFoundError:
                    pass
            raise

    def close(self) -> None:
        self._server.close()
        for connection, (_, timer) in list(self._connections.items()):
            timer.stop()
            connection.abort()
            connection.deleteLater()
        self._connections.clear()
        if self._token is not None:
            try:
                record = json.loads(self.discovery_path.read_text(encoding="utf-8"))
                if isinstance(record, dict) and hmac.compare_digest(
                    str(record.get("token", "")).encode("utf-8"), self._token.encode("ascii")
                ):
                    self.discovery_path.unlink()
            except (OSError, ValueError, TypeError):
                pass
            self._token = None
        self._discovery_lock.unlock()

    def _accept_connections(self) -> None:
        while self._server.hasPendingConnections():
            connection = self._server.nextPendingConnection()
            if connection is None:
                continue
            if len(self._connections) >= MAX_CONNECTIONS:
                connection.abort()
                connection.deleteLater()
                continue
            connection.setReadBufferSize(MAX_REQUEST_BYTES + 2)
            timer = QTimer(connection)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda sock=connection: self._finish(sock, None, error=("timeout", "请求超时")))
            self._connections[connection] = (bytearray(), timer)
            connection.readyRead.connect(lambda sock=connection: self._read(sock))
            connection.disconnected.connect(lambda sock=connection: self._discard(sock))
            timer.start(REQUEST_TIMEOUT_MS)
            if connection.bytesAvailable():
                self._read(connection)

    def _discard(self, connection: QTcpSocket) -> None:
        state = self._connections.pop(connection, None)
        if state:
            state[1].stop()
        connection.deleteLater()

    def _read(self, connection: QTcpSocket) -> None:
        state = self._connections.get(connection)
        if state is None:
            return
        buffer, _ = state
        if connection.bytesAvailable() > MAX_REQUEST_BYTES + 1 - len(buffer):
            self._finish(connection, None, error=("request_too_large", "请求超过大小限制"))
            return
        buffer.extend(bytes(connection.readAll()))
        newline = buffer.find(b"\n")
        if newline < 0:
            if len(buffer) > MAX_REQUEST_BYTES:
                self._finish(connection, None, error=("request_too_large", "请求超过大小限制"))
            return
        if newline > MAX_REQUEST_BYTES:
            self._finish(connection, None, error=("request_too_large", "请求超过大小限制"))
            return
        # The protocol is deliberately not HTTP and permits exactly one JSON line.
        if buffer[newline + 1:]:
            self._finish(connection, None, error=("invalid_request", "每个连接只接受一条请求"))
            return
        try:
            request = json.loads(
                buffer[:newline].decode("utf-8", errors="strict"),
                object_pairs_hook=_reject_duplicates, parse_constant=_invalid_constant,
                parse_float=_finite_float,
            )
            if not isinstance(request, dict):
                raise ValueError("请求必须是 JSON 对象")
            request_id = request.get("id")
            if isinstance(request_id, bool) or not isinstance(request_id, (str, int, float)):
                raise ValueError("id 必须是字符串或数字")
            token = request.get("token")
            method = request.get("method")
            params = request.get("params")
            if not isinstance(token, str) or not isinstance(method, str) or not method or len(method) > 128:
                raise ValueError("缺少有效的 token 或 method")
            if not isinstance(params, dict):
                raise ValueError("params 必须是 JSON 对象")
            if set(request) != {"token", "id", "method", "params"}:
                raise ValueError("请求字段不符合协议")
            # Reject escaped lone surrogates too; json.loads accepts them even
            # though they cannot be represented in a valid UTF-8 response.
            json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            self._finish(connection, None, error=("invalid_request", "无效的 JSON 请求"))
            return
        if self._token is None or not hmac.compare_digest(token.encode("utf-8"), self._token.encode("ascii")):
            self._finish(connection, request_id, error=("unauthorized", "认证失败"))
            return
        # Mark the request consumed before invoking the handler; reentrant readyRead
        # callbacks cannot dispatch a second command on the same socket.
        state[1].stop()
        self._connections.pop(connection, None)
        try:
            result = self._handler(method, params)
            self._write_response(connection, {"id": request_id, "ok": True, "result": result})
        except AgentError as exc:
            self._write_response(connection, {"id": request_id, "ok": False,
                                              "error": {"code": exc.code, "message": exc.message}})
        except Exception:
            _LOG.exception("Agent 控制请求执行失败")
            self._write_response(connection, {"id": request_id, "ok": False,
                                              "error": {"code": "internal_error", "message": "操作失败，请查看程序日志"}})

    def _finish(self, connection: QTcpSocket, request_id: Any,
                error: tuple[str, str]) -> None:
        state = self._connections.pop(connection, None)
        if state is None:
            return
        state[1].stop()
        code, message = error
        self._write_response(connection, {"id": request_id, "ok": False,
                                          "error": {"code": code, "message": message}})

    def _write_response(self, connection: QTcpSocket, response: dict[str, Any]) -> None:
        try:
            payload = (json.dumps(response, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
            if len(payload) > MAX_RESPONSE_BYTES:
                payload = (json.dumps({"id": response.get("id"), "ok": False,
                                       "error": {"code": "response_too_large", "message": "响应超过大小限制"}},
                                      ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        except (TypeError, ValueError, RecursionError):
            payload = b'{"id":null,"ok":false,"error":{"code":"internal_error","message":"invalid response"}}\n'
        if connection.state() != QAbstractSocket.SocketState.UnconnectedState:
            connection.write(payload)
            connection.disconnectFromHost()
        else:
            connection.deleteLater()
