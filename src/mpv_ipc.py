from __future__ import annotations

import ctypes
import json
import msvcrt
import os
import subprocess
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Any, NamedTuple

_PeekNamedPipe = ctypes.windll.kernel32.PeekNamedPipe
_PeekNamedPipe.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
]
_PeekNamedPipe.restype = wintypes.BOOL


def _pipe_available(fh: Any) -> int:
    handle = msvcrt.get_osfhandle(fh.fileno())
    avail = wintypes.DWORD()
    ok = _PeekNamedPipe(handle, None, 0, None, ctypes.byref(avail), None)
    return int(avail.value) if ok else 0


def _mpv_path_arg(path: Path) -> str:
    return path.resolve().as_posix()


class MpvError(RuntimeError):
    pass


class MpvClient:
    def __init__(self, exe: Path, kind: str) -> None:
        self.exe = exe
        self.kind = kind
        self.pipe_name = f"kongchang-{kind}-{os.getpid()}-{id(self):x}"
        self.proc: subprocess.Popen[bytes] | None = None
        self._fh: Any = None
        self._reader: threading.Thread | None = None
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._pending: dict[int, tuple[threading.Event, dict[str, Any]]] = {}
        self._req = 0
        self._running = False
        self.props: dict[str, Any] = {}
        self.media_path: str | None = None
        self.on_client_message: Any = None

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None and self._fh is not None

    def start(self, extra_args: list[str]) -> None:
        if not self.exe.exists():
            raise MpvError(f"找不到 mpv：{self.exe}")
        args = [
            str(self.exe),
            f"--input-ipc-server=\\\\.\\pipe\\{self.pipe_name}",
            "--idle=yes",
            "--keep-open=yes",
            "--no-terminal",
            "--no-config",
            "--input-default-bindings=no",
            "--no-input-media-keys",
            "--osc=no",
            "--osd-level=1",
            *extra_args,
        ]
        creation = 0
        if os.name == "nt":
            creation = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.proc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation,
        )
        try:
            from src.winjob import attach_pid

            if self.proc.pid:
                attach_pid(self.proc.pid)
        except Exception:
            pass
        self._fh = self._connect_pipe(8.0)
        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        for i, name in enumerate(
            ("pause", "eof-reached", "fullscreen", "idle-active", "path", "volume", "time-pos", "duration"),
            start=1,
        ):
            self.command(["observe_property", i, name])

    def stop(self) -> None:
        self._running = False
        if self.alive:
            try:
                self.command(["quit"], timeout=0.4)
            except Exception:
                pass
        if self._fh is not None:
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.wait(timeout=1.5)
            except Exception:
                try:
                    self.proc.terminate()
                    self.proc.wait(timeout=1.0)
                except Exception:
                    self.proc.kill()
        self.proc = None
        self.media_path = None
        self.props = {}
        with self._lock:
            for event, box in self._pending.values():
                box["error"] = "closed"
                event.set()
            self._pending.clear()

    def command(self, args: list[Any], timeout: float = 3.0) -> Any:
        if self._fh is None:
            raise MpvError("mpv 未连接")
        with self._lock:
            self._req += 1
            req_id = self._req
            waiter = threading.Event()
            box: dict[str, Any] = {}
            self._pending[req_id] = (waiter, box)
        payload = json.dumps({"command": args, "request_id": req_id}, ensure_ascii=False) + "\n"
        with self._write_lock:
            self._fh.write(payload.encode("utf-8"))
        if not waiter.wait(timeout):
            with self._lock:
                self._pending.pop(req_id, None)
            raise MpvError(f"mpv 命令超时：{args[0]}")
        error = box.get("error", "success")
        if error not in (None, "success"):
            raise MpvError(f"mpv 错误 {error}: {args}")
        return box.get("data")

    def get(self, name: str) -> Any:
        return self.command(["get_property", name])

    def set(self, name: str, value: Any) -> Any:
        return self.command(["set_property", name, value])

    def loadfile(self, path: Path, paused: bool, loop: bool = False) -> None:
        self.command(["loadfile", _mpv_path_arg(path), "replace"])
        self.set("loop-file", "inf" if loop else "no")
        self.set("pause", paused)
        self.media_path = str(path.resolve())

    def _connect_pipe(self, timeout: float) -> Any:
        pipe = rf"\\.\pipe\{self.pipe_name}"
        deadline = time.monotonic() + timeout
        last: Exception | None = None
        while time.monotonic() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                raise MpvError("mpv 启动后立刻退出")
            try:
                return open(pipe, "r+b", buffering=0)
            except OSError as exc:
                last = exc
                time.sleep(0.05)
        raise MpvError(f"无法连接 mpv IPC：{last}")

    def _read_loop(self) -> None:
        buf = b""
        while self._running and self._fh is not None:
            try:
                ready = _pipe_available(self._fh)
                if ready <= 0:
                    time.sleep(0.02)
                    continue
                chunk = os.read(self._fh.fileno(), ready)
            except Exception:
                break
            if not chunk:
                time.sleep(0.02)
                continue
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                self._dispatch(msg)

    def _dispatch(self, msg: dict[str, Any]) -> None:
        if msg.get("event") == "client-message":
            args = [str(item) for item in (msg.get("args") or [])]
            callback = self.on_client_message
            if callback is not None:
                callback(args)
            return
        if msg.get("event") == "property-change":
            name = msg.get("name")
            if name:
                self.props[name] = msg.get("data")
        req_id = msg.get("request_id")
        if req_id is None:
            return
        with self._lock:
            pending = self._pending.pop(req_id, None)
        if pending is None:
            return
        waiter, box = pending
        box["error"] = msg.get("error", "success")
        box["data"] = msg.get("data")
        waiter.set()


class WinDisplay(NamedTuple):
    index: int
    device: str
    width: int
    height: int
    primary: bool
    left: int = 0
    top: int = 0
    connected: bool = True

    @property
    def short_device(self) -> str:
        if self.device.startswith("\\\\.\\"):
            return self.device[4:]
        return self.device

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    @property
    def label(self) -> str:
        extra = "（主屏）" if self.primary else ""
        miss = "（未连接）" if not self.connected else ""
        return (
            f"屏幕{self.index + 1}  ·  {self.short_device}  "
            f"{self.width}x{self.height} @{self.left},{self.top}{extra}{miss}"
        )


def list_windows_displays() -> list[WinDisplay]:
    """用 EnumDisplayMonitors 列出显示器。下标与 mpv --fs-screen / --screen 一致。

    不能信 mpv 的 display-names：Windows + d3d11 上它只返回当前窗口所在的那一块。
    也不能用 Qt screens() 的下标：顺序常和 EnumDisplayMonitors / mpv 不一致。
    """
    if os.name != "nt":
        return []

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", ctypes.c_wchar * 32),
        ]

    monitors: list[WinDisplay] = []
    user32 = ctypes.windll.user32
    MonitorEnumProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(RECT),
        wintypes.LPARAM,
    )

    def _callback(hmonitor, hdc, lprect, lparam) -> int:
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            return 1
        rect = info.rcMonitor
        monitors.append(
            WinDisplay(
                index=len(monitors),
                device=info.szDevice,
                width=rect.right - rect.left,
                height=rect.bottom - rect.top,
                primary=bool(info.dwFlags & 1),
                left=rect.left,
                top=rect.top,
            )
        )
        return 1

    callback = MonitorEnumProc(_callback)
    user32.EnumDisplayMonitors(None, None, callback, 0)
    return monitors


def display_index_for_point(x: int, y: int, displays: list[WinDisplay] | None = None) -> int | None:
    """点落在哪块屏（EnumDisplayMonitors / mpv 下标）。"""
    items = displays if displays is not None else list_windows_displays()
    for item in items:
        if item.contains(int(x), int(y)):
            return item.index
    return None


def display_index_for_hwnd(hwnd: int, displays: list[WinDisplay] | None = None) -> int | None:
    """窗口所在屏。优先 MonitorFromWindow，避免 Qt 屏幕下标和 mpv 不一致。"""
    if os.name != "nt" or not hwnd:
        return None
    items = displays if displays is not None else list_windows_displays()
    if not items:
        return None
    user32 = ctypes.windll.user32
    MONITOR_DEFAULTTONEAREST = 2
    hmon = user32.MonitorFromWindow(wintypes.HWND(hwnd), MONITOR_DEFAULTTONEAREST)
    if not hmon:
        return None

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", ctypes.c_wchar * 32),
        ]

    info = MONITORINFOEXW()
    info.cbSize = ctypes.sizeof(MONITORINFOEXW)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
        return None
    device = info.szDevice
    for item in items:
        if item.device == device:
            return item.index
    # 设备名偶发对不上时，用几何中心兜底
    cx = (info.rcMonitor.left + info.rcMonitor.right) // 2
    cy = (info.rcMonitor.top + info.rcMonitor.bottom) // 2
    return display_index_for_point(cx, cy, items)


def list_mpv_displays(exe: Path) -> list[tuple[int, str]]:
    displays = list_windows_displays()
    if displays:
        return [(item.index, item.label) for item in displays]
    client = MpvClient(exe, "probe")
    try:
        client.start(
            [
                "--force-window=yes",
                "--geometry=1x1+-4000+-4000",
                "--title=控场-检测显示器",
                "--ao=null",
                "--pause",
            ]
        )
        names = client.get("display-names")
    except Exception:
        names = None
    finally:
        client.stop()
    result: list[tuple[int, str]] = []
    if isinstance(names, list) and names:
        for i, name in enumerate(names):
            result.append((i, str(name)))
        return result
    return []
