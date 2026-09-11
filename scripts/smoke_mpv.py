from __future__ import annotations

import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.controller import ShowController
from src.models import Cue
from src.mpv_ipc import list_mpv_displays
from src.paths import vendor_mpv_exe


def write_wav(path: Path) -> None:
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 8000)


def main() -> None:
    exe = vendor_mpv_exe()
    assert exe.exists(), exe
    print("mpv", exe)
    displays = list_mpv_displays(exe)
    print("displays", displays)
    wav = ROOT / "data" / "_smoke.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    write_wav(wav)
    ctl = ShowController()
    ctl.configure(exe, 0, 0)
    cue = Cue(id="a1", name="smoke", type="audio", path=str(wav))
    ctl.activate(cue, wav)
    time.sleep(0.6)
    st = ctl.status()
    print("audio", st.audio_state, st.message)
    assert st.audio_state in ("播放中", "已暂停"), st
    ctl.toggle_pause(cue)
    time.sleep(0.2)
    print("paused", ctl.status().audio_state)
    ctl.stop_all()
    print("stopped", ctl.status().audio_state)
    print("ok")


if __name__ == "__main__":
    main()
