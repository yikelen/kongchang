"""单实例：新开一份就关掉上一份，并清掉残留 mpv。"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from src.paths import app_root, vendor_mpv_exe

SOCKET_NAME = "KongchangSingleton"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _wmi_processes(name: str) -> list[tuple[int, str]]:
    script = (
        f"Get-CimInstance Win32_Process -Filter \"Name='{name}'\" | "
        "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        raw = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            text=True,
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
        ).strip()
    except Exception:
        return []
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    result: list[tuple[int, str]] = []
    for item in data:
        try:
            result.append((int(item["ProcessId"]), str(item.get("CommandLine") or "")))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def _is_our_app(name: str, command: str) -> bool:
    cmd = command.lower()
    if name.lower() == "控场.exe":
        return True
    if "src.main" in cmd or "src\\main.py" in cmd or "src/main.py" in cmd or "简易控场" in command:
        return True
    exe = vendor_mpv_exe()
    if name.lower() == "mpv.exe" and "kongchang-" in cmd:
        return True
    if name.lower() == "mpv.exe" and str(exe).lower() in cmd:
        return True
    return False


def _terminate(pid: int) -> None:
    if pid in (0, os.getpid(), os.getppid()):
        return
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW,
    )


def kill_leftovers(keep_pid: int | None = None) -> None:
    keep = {os.getpid(), os.getppid()}
    if keep_pid:
        keep.add(keep_pid)
    names = ("mpv.exe", "控场.exe", "python.exe", "pythonw.exe")
    for name in names:
        for pid, command in _wmi_processes(name):
            if pid in keep:
                continue
            if not _is_our_app(name, command):
                continue
            _terminate(pid)


def _send_existing(payload: bytes) -> bool:
    from PySide6.QtNetwork import QLocalSocket

    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if not sock.waitForConnected(250):
        sock.deleteLater()
        return False
    sock.write(payload)
    sock.flush()
    sock.waitForBytesWritten(400)
    sock.disconnectFromServer()
    sock.deleteLater()
    return True


def start_singleton_server(on_raise, on_replace) -> object:
    from PySide6.QtNetwork import QLocalServer

    QLocalServer.removeServer(SOCKET_NAME)
    server = QLocalServer()
    server.listen(SOCKET_NAME)

    def _incoming() -> None:
        conn = server.nextPendingConnection()
        if conn is None:
            return

        def _read() -> None:
            payload = bytes(conn.readAll()).decode("utf-8", errors="ignore")
            if "raise" in payload:
                on_raise()
            elif "quit" in payload:
                on_replace()

        conn.readyRead.connect(_read)

    server.newConnection.connect(_incoming)
    return server


def pid_file() -> Path:
    folder = app_root() / "data"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "instance.pid"


def write_pid() -> None:
    pid_file().write_text(str(os.getpid()), encoding="utf-8")


def _read_old_pid() -> int | None:
    path = pid_file()
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def take_over() -> bool:
    """已有实例则把它唤到前台，返回 False 表示本进程应退出。"""
    if _send_existing(b"raise\n"):
        return False
    # 只清本软件残留的 mpv，不要扫杀其它 pythonw
    keep = {os.getpid(), os.getppid()}
    for pid, command in _wmi_processes("mpv.exe"):
        if pid in keep:
            continue
        if _is_our_app("mpv.exe", command):
            _terminate(pid)
    write_pid()
    return True
