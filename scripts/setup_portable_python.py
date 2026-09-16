"""把便携 CPython + 依赖装进 vendor/python，不依赖本机 Python / Miniconda / .venv。

拷贝整个「控场」文件夹到别的 Windows 电脑后，双击 启动.bat 即可。
本脚本只需在「还没有 vendor/python」时跑一次（开发机或首次打包）。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "vendor" / "python"
REQ = ROOT / "requirements.txt"

# python-build-standalone：可整体挪路径，不写死盘符。
# 升级时改这两个常量即可。
RELEASE = "20260901"
ASSET = "cpython-3.12.14+20260901-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
URL = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/"
    f"{RELEASE}/{ASSET}"
)

_UA = {"User-Agent": "kongchang-portable-python"}


def _stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def _say(*parts: object) -> None:
    text = " ".join(str(p) for p in parts)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        print(text.encode("ascii", "backslashreplace").decode("ascii"), flush=True)


def _download(url: str, dest: Path) -> None:
    _say("download", url)
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=120) as resp, dest.open("wb") as out:
        total = resp.headers.get("Content-Length")
        total_n = int(total) if total and total.isdigit() else None
        got = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            got += len(chunk)
            if total_n:
                msg = f"  {got / 1e6:.1f} / {total_n / 1e6:.1f} MB"
            else:
                msg = f"  {got / 1e6:.1f} MB"
            try:
                print(f"\r{msg}", end="", flush=True)
            except UnicodeEncodeError:
                pass
        _say()


def _python_ok() -> bool:
    py = DEST / "python.exe"
    if not py.exists():
        return False
    try:
        subprocess.check_call(
            [str(py), "-c", "import PySide6"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _extractall(tf: tarfile.TarFile, dest: Path) -> None:
    # 3.12+ 解压必须声明 filter，否则 3.13 会打 DeprecationWarning，
    # 看起来像启动失败；这是官方构建包，用 fully_trusted。
    if sys.version_info >= (3, 12):
        tf.extractall(dest, filter="fully_trusted")
    else:
        tf.extractall(dest)


def _extract_python(archive: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _say("extracting portable Python ...")
        with tarfile.open(archive, "r:gz") as tf:
            _extractall(tf, tmp_path)
        found = list(tmp_path.rglob("python.exe"))
        if not found:
            raise SystemExit(f"压缩包里没有 python.exe：{archive}")
        folder = found[0].parent
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        _say("moving into", dest)
        shutil.move(str(folder), str(dest))


def main() -> None:
    if _python_ok():
        _say("vendor/python already ok, skip")
        return

    DEST.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / ASSET
        _download(URL, archive)
        _say("extract to", DEST)
        _extract_python(archive, DEST)

    py = DEST / "python.exe"
    if not py.exists():
        raise SystemExit(f"解压后没有 {py}")

    _say("pip install dependencies ...")
    subprocess.check_call([str(py), "-m", "pip", "install", "-U", "pip"])
    subprocess.check_call([str(py), "-m", "pip", "install", "-r", str(REQ)])

    (DEST / "SOURCE.txt").write_text(
        f"source={URL}\nnote=bundled relocatable CPython + PySide6, do not use system Python\n",
        encoding="utf-8",
    )
    if not _python_ok():
        raise SystemExit("安装完成但无法 import PySide6")
    _say("done. run 启动.bat next time.")


if __name__ == "__main__":
    _stdio()
    if sys.version_info < (3, 11):
        raise SystemExit("need Python 3.11+ to bootstrap (runtime uses vendor/python)")
    main()
