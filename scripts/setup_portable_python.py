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


def _download(url: str, dest: Path) -> None:
    print("下载", url)
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
                print(f"\r  {got / 1e6:.1f} / {total_n / 1e6:.1f} MB", end="", flush=True)
            else:
                print(f"\r  {got / 1e6:.1f} MB", end="", flush=True)
        print()


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


def _extract_python(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(tmp_path)
        exe = next(tmp_path.rglob("python.exe"))
        folder = exe.parent
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(folder), str(dest))


def main() -> None:
    if _python_ok():
        print("已有可用的 vendor/python，跳过。")
        return

    DEST.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / ASSET
        _download(URL, archive)
        print("解压到", DEST, flush=True)
        _extract_python(archive, DEST)

    py = DEST / "python.exe"
    if not py.exists():
        raise SystemExit(f"解压后没有 {py}")

    print("安装 pip 依赖 …", flush=True)
    subprocess.check_call([str(py), "-m", "pip", "install", "-U", "pip"])
    subprocess.check_call([str(py), "-m", "pip", "install", "-r", str(REQ)])

    (DEST / "SOURCE.txt").write_text(
        f"source={URL}\nnote=bundled relocatable CPython + PySide6, do not use system Python\n",
        encoding="utf-8",
    )
    if not _python_ok():
        raise SystemExit("安装完成但无法 import PySide6")
    print("完成。之后双击 启动.bat 即可，整夹拷到别的电脑也能用。")


if __name__ == "__main__":
    if sys.version_info < (3, 11):
        raise SystemExit("引导本脚本需要 Python 3.11+（只在打包时用，运行软件不需要）")
    main()
