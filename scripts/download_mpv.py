"""把便携 mpv 下载到 vendor/mpv，不依赖系统安装。"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "vendor" / "mpv"
API = "https://api.github.com/repos/mpv-player/mpv/releases/tags/git-release"


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


def main() -> None:
    _stdio()
    _say("query mpv git-release")
    with urllib.request.urlopen(API) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    asset = next(
        item
        for item in data["assets"]
        if item["name"].endswith("x86_64-pc-windows-msvc.zip")
        and "pdb" not in item["name"]
    )
    url = asset["browser_download_url"]
    _say("download", url)
    DEST.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "mpv.zip"
        urllib.request.urlretrieve(url, zip_path)
        extract = Path(tmp) / "out"
        extract.mkdir()
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract)
        exe = next(extract.rglob("mpv.exe"))
        folder = exe.parent
        for item in folder.iterdir():
            target = DEST / item.name
            if item.is_file():
                shutil.copy2(item, target)
        (DEST / "SOURCE.txt").write_text(f"source={url}\n", encoding="utf-8")
    _say("wrote", DEST / "mpv.exe")


if __name__ == "__main__":
    main()
