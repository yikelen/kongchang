from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

from src.models import Cue
from src.mpv_ipc import MpvClient, MpvError

FADE_SECONDS = 1.6
DUCK_RATIO = 0.6
DUCK_STEPS = 18


@dataclass
class RuntimeStatus:
    audio_state: str = "空闲"
    audio_name: str = ""
    video_state: str = "未加载"
    video_name: str = ""
    position: float | None = None
    duration: float | None = None
    volume: int | None = None
    message: str = ""


class ShowController:
    def __init__(self) -> None:
        self.mpv_exe: Path | None = None
        self.projection_screen = 0
        self.preview_screen = 1
        self.audio: MpvClient | None = None  # 节目单音频
        self.lib_audio: MpvClient | None = None  # 临时垫乐，独立进程
        self.video: MpvClient | None = None
        self.audio_cue_id: str | None = None
        self.lib_audio_cue_id: str | None = None
        self.video_cue_id: str | None = None
        self.audio_name = ""
        self.lib_audio_name = ""
        self.video_name = ""
        self.video_from_library = False  # True=右侧临时视频（与节目单视频互斥，同用一个播放器）
        self.video_ever_played = False
        self.video_on_stage = False
        self.stopped_audio_id: str | None = None
        self.last_error = ""
        self._fading_show = False
        self._fading_lib = False
        self._fade_lock = threading.Lock()
        self._fade_client: MpvClient | None = None
        self._fade_origin = 100.0
        self._fade_i = 0
        self._fade_steps = 16
        self._fade_library = False
        self.on_client_message = None
        self.on_fade_done = None
        self.output_volume = 100.0
        self.library_volume = 100.0
        self.master_muted = False
        self.ducked = False
        self.hold_active = False
        self._fade_in = False
        self._fade_target = 100.0
        self.pending_fade_in: str | None = None
        self.audio_device = ""
        self.show_audio_trim_out = 0.0
        self.lib_audio_trim_out = 0.0
        self.video_trim_out = 0.0
        self.show_audio_fade_out = 0.0
        self.lib_audio_fade_out = 0.0
        self._fade_in_seconds = FADE_SECONDS
        self._duck_ramping = False
        self._duck_client: MpvClient | None = None
        self._duck_library = False
        self._duck_from = 100.0
        self._duck_to = 100.0
        self._duck_i = 0
        self._duck_steps = DUCK_STEPS

    @property
    def audio_from_library(self) -> bool:
        return self._lib_audio_on()

    @property
    def _fading(self) -> bool:
        return self._fading_show or self._fading_lib

    def _lib_audio_on(self) -> bool:
        return (
            self.lib_audio is not None
            and self.lib_audio.alive
            and self._is_active(self.lib_audio)
        )

    def _show_audio_on(self) -> bool:
        return self.audio is not None and self.audio.alive and self._is_active(self.audio)

    def _any_audio_on(self) -> bool:
        return self._show_audio_on() or self._lib_audio_on()

    def configure(
        self,
        mpv_exe: Path,
        projection_screen: int,
        preview_screen: int,
        audio_device: str = "",
    ) -> None:
        self.mpv_exe = mpv_exe
        self.projection_screen = max(0, projection_screen)
        self.preview_screen = max(0, preview_screen)
        self.audio_device = (audio_device or "").strip()

    def shutdown(self) -> None:
        self.stop_all()

    def panic_stop(self) -> None:
        """所有通道立刻停，收起全屏。保留静音开关。"""
        muted = self.master_muted
        self._duck_ramping = False
        self.ducked = False
        self.stop_all()
        self.master_muted = muted

    def list_audio_devices(self) -> list[tuple[str, str]]:
        try:
            client = self._ensure_audio()
        except MpvError:
            return []
        raw = client.get("audio-device-list")
        out: list[tuple[str, str]] = []
        if isinstance(raw, list):
            for item in raw:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name") or "")
                desc = str(item.get("description") or name)
                if name:
                    out.append((name, desc))
        return out

    def _audio_device_args(self) -> list[str]:
        if self.audio_device:
            return [f"--audio-device={self.audio_device}"]
        return []

    def _apply_trim_in(self, client: MpvClient, cue: Cue) -> None:
        if cue.trim_in <= 0:
            return
        try:
            client.command(["seek", cue.trim_in, "absolute"])
            client.props["time-pos"] = cue.trim_in
        except MpvError as exc:
            self.last_error = str(exc)

    def _past_trim_out(self, client: MpvClient | None, trim_out: float) -> bool:
        if client is None:
            return False
        if trim_out > 0:
            raw = client.props.get("time-pos")
            try:
                if float(raw) >= trim_out - 0.04:
                    return True
            except (TypeError, ValueError):
                pass
        return bool(client.props.get("eof-reached"))

    def activate(self, cue: Cue, media: Path | None, *, under_video: bool = False) -> None:
        self.last_error = ""
        if cue.type == "audio":
            self._activate_audio(cue, media, stop_video=not under_video)
        elif cue.type == "video":
            self._activate_video(cue, media)
        # note: select only

    def go(
        self,
        cue: Cue,
        media: Path | None,
        *,
        under_video: bool = False,
        from_library: bool = False,
        autoplay: bool = False,
        loop: bool | None = None,
    ) -> str:
        """播放条目。
        under_video：临时音频叠在视频上。
        from_library：来自右侧临时列表（视频与节目单互斥，同用一个播放器）。
        autoplay：视频加载后直接开播（分类切歌），不停留在预监暂停。
        loop：覆盖条目自身的 loop（分类单曲/顺序/列表模式用）。
        """
        self.last_error = ""
        library_audio = bool(from_library or under_video) if cue.type == "audio" else False
        if cue.type == "audio":
            if library_audio and self._fading_lib:
                self._cancel_fade(library=True)
                self._stop_lib_audio()
            elif not library_audio and self._fading_show:
                self._cancel_fade(library=False)
                self._stop_show_audio()
        action = self.go_action(cue, from_library=from_library or library_audio)
        if cue.type == "note" or action == "disabled":
            return ""
        if cue.type == "audio":
            if action == "replay":
                self._restart_audio(
                    cue, media, stop_video=not library_audio, loop=loop, from_library=library_audio
                )
                return ""
            if action == "playing":
                if loop is not None:
                    self.apply_loop(cue, loop)
                return ""
            self._activate_audio(
                cue, media, stop_video=not library_audio, loop=loop, from_library=library_audio
            )
            return ""
        if cue.type == "video":
            if action == "playing":
                if loop is not None:
                    self.apply_loop(cue, loop)
                return ""
            if action == "replay":
                self._restart_video(cue, media, from_library=from_library, loop=loop)
                return ""
            if action == "play":
                if self._same_video(cue):
                    self.play_video(cue)
                else:
                    # 临时切播 / 直接开播：同一窗口换片，保持全屏或小窗
                    self._activate_video(
                        cue,
                        media,
                        from_library=from_library,
                        loop=loop,
                        autoplay=True,
                    )
                if loop is not None:
                    self.apply_loop(cue, loop)
                return ""
            self._activate_video(
                cue, media, from_library=from_library, loop=loop, autoplay=autoplay
            )
            return ""
        return ""

    def go_action(self, cue: Cue | None, *, from_library: bool = False) -> str:
        if cue is None:
            return "disabled"
        if cue.type == "note":
            return "disabled"
        fading = self._fading_lib if from_library else self._fading_show
        if fading and not self._fade_in:
            return "play"
        if cue.type == "audio":
            if self._same_audio(cue, library=from_library):
                client = self.lib_audio if from_library else self.audio
                if self._client_paused(client):
                    return "replay"
                return "playing"
            return "play"
        if cue.type == "video":
            if self._same_video(cue):
                if not self._client_paused(self.video):
                    return "playing"
                if self.video_ever_played:
                    return "replay"
                return "play"
            # 临时列表：正在播时点另一条 = 切播，不走预览
            if from_library:
                return "play"
            return "preview"
        return "play"

    def _restart_audio(
        self,
        cue: Cue,
        media: Path | None,
        *,
        stop_video: bool = True,
        loop: bool | None = None,
        from_library: bool = False,
    ) -> None:
        client = self.lib_audio if from_library else self.audio
        if self._same_audio(cue, library=from_library) and client is not None:
            try:
                client.command(["seek", 0, "absolute"])
                client.set("pause", False)
                self.apply_loop(cue, loop)
                return
            except MpvError:
                pass
        if self._same_audio(cue, library=from_library):
            if from_library:
                self._stop_lib_audio()
            else:
                self._stop_show_audio()
        self._activate_audio(
            cue, media, stop_video=stop_video, loop=loop, from_library=from_library
        )

    def _restart_video(
        self,
        cue: Cue,
        media: Path | None,
        *,
        from_library: bool = False,
        loop: bool | None = None,
    ) -> None:
        if self._same_video(cue) and self.video is not None:
            try:
                self.video.command(["seek", 0, "absolute"])
                self.video.set("pause", False)
                self.video_ever_played = True
                self.video_from_library = from_library
                self.apply_loop(cue, loop)
                return
            except MpvError:
                pass
        if self._same_video(cue):
            self._stop_video_only()
        self._activate_video(
            cue, media, from_library=from_library, loop=loop, autoplay=True
        )

    def stop_all(self) -> None:
        self._cancel_fade(library=False)
        self._cancel_fade(library=True)
        if self.audio_cue_id:
            self.stopped_audio_id = self.audio_cue_id
        if self.audio is not None:
            self.audio.stop()
            self.audio = None
        if self.lib_audio is not None:
            self.lib_audio.stop()
            self.lib_audio = None
        if self.video is not None:
            self.video.stop()
            self.video = None
        self.audio_cue_id = None
        self.lib_audio_cue_id = None
        self.video_cue_id = None
        self.audio_name = ""
        self.lib_audio_name = ""
        self.video_name = ""
        self.video_from_library = False
        self.video_ever_played = False
        self.video_on_stage = False

    def fade_stop(self, seconds: float = FADE_SECONDS) -> bool:
        """底栏停止：节目单音频和节目单视频一次停干净。"""
        show_video = (
            self.video is not None
            and self.video.alive
            and self._is_active(self.video)
            and not self.video_from_library
        )
        fading = False
        if self._show_audio_on() or self._fading_show:
            fade_s = self.show_audio_fade_out or seconds
            fading = self.begin_fade(fade_s, library=False)
        if show_video:
            self._stop_video_only()
        return fading

    def fade_stop_audio(self, seconds: float = FADE_SECONDS, *, library: bool = True) -> bool:
        """停一路音频。默认临时垫乐。返回 True 表示需要界面定时器做渐停。"""
        if library and self.lib_audio_fade_out > 0:
            seconds = self.lib_audio_fade_out
        elif not library and self.show_audio_fade_out > 0:
            seconds = self.show_audio_fade_out
        return self.begin_fade(seconds, library=library)

    def _cancel_fade(self, *, library: bool) -> None:
        if library:
            self._fading_lib = False
        else:
            self._fading_show = False
        if self._fade_library == library:
            self._fade_client = None

    def begin_fade(self, seconds: float = FADE_SECONDS, *, library: bool = False) -> bool:
        """开始渐停。True = 调用方应用 QTimer 调 fade_tick。"""
        client = self.lib_audio if library else self.audio
        live = (
            client is not None and client.alive and self._is_active(client)
        )
        if not live:
            if library:
                self._stop_lib_audio()
            else:
                self._stop_show_audio()
            return False
        if bool(client.props.get("pause")):
            if library:
                self._stop_lib_audio()
            else:
                self._stop_show_audio()
            return False
        with self._fade_lock:
            already = self._fading_lib if library else self._fading_show
            if already:
                self._cancel_fade(library=library)
                if library:
                    self._stop_lib_audio()
                else:
                    self._stop_show_audio()
                return False
            if library:
                self._fading_lib = True
            else:
                self._fading_show = True
        try:
            raw = client.props.get("volume")
            vol = float(raw) if raw is not None else (
                self.library_volume if library else self.output_volume
            )
        except (TypeError, ValueError):
            vol = self.library_volume if library else self.output_volume
        self._fade_client = client
        self._fade_origin = vol
        self._fade_i = 0
        self._fade_steps = 16
        self._fade_library = library
        self._fade_interval_s = max(0.04, seconds / self._fade_steps)
        self._fade_in = False
        self._duck_ramping = False
        return True

    def _audio_target_volume(self, *, library: bool) -> float:
        if self.master_muted:
            return 0.0
        vol = float(self.library_volume if library else self.output_volume)
        if self.ducked:
            vol *= DUCK_RATIO
        return vol

    def begin_fade_in(self) -> bool:
        """音频开播后从 0 淡入。True = 需要定时器。"""
        kind = self.pending_fade_in
        self.pending_fade_in = None
        if kind not in ("show", "lib") or self.master_muted:
            return False
        self._duck_ramping = False
        library = kind == "lib"
        client = self.lib_audio if library else self.audio
        if client is None or not client.alive or not self._is_active(client):
            return False
        target = self._audio_target_volume(library=library)
        if target <= 0:
            return False
        if library:
            self._fading_lib = True
        else:
            self._fading_show = True
        self._fade_in = True
        self._fade_library = library
        self._fade_client = client
        self._fade_origin = 0.0
        self._fade_target = target
        self._fade_i = 0
        seconds = self._fade_in_seconds or FADE_SECONDS
        self._fade_steps = max(8, int(seconds / 0.05))
        try:
            client.set("volume", 0)
            client.set("mute", False)
        except MpvError:
            pass
        return True

    def fade_tick(self) -> bool:
        """走一步淡入或渐停。True = 还要继续。"""
        library = self._fade_library
        fading = self._fading_lib if library else self._fading_show
        client = self._fade_client
        expected = self.lib_audio if library else self.audio
        if not fading or client is None or client is not expected or not client.alive:
            if fading and not self._fade_in:
                if library:
                    self._stop_lib_audio()
                else:
                    self._stop_show_audio()
            self._fade_in = False
            self._cancel_fade(library=library)
            done = self.on_fade_done
            if done is not None:
                done()
            return False
        self._fade_i += 1
        if self._fade_in:
            factor = min(1.0, self._fade_i / self._fade_steps)
            vol = self._fade_target * factor
        else:
            factor = max(0.0, 1.0 - self._fade_i / self._fade_steps)
            vol = self._fade_origin * factor
        try:
            client.set("volume", vol)
        except MpvError:
            pass
        if self._fade_i >= self._fade_steps:
            if self._fade_in:
                try:
                    client.set("volume", self._fade_target)
                except MpvError:
                    pass
                self._fade_in = False
                self._cancel_fade(library=library)
            else:
                if library:
                    self._stop_lib_audio()
                else:
                    self._stop_show_audio()
                self._cancel_fade(library=library)
            done = self.on_fade_done
            if done is not None:
                done()
            return False
        return True

    def toggle_audio_pause(self) -> None:
        """只暂停/继续音频配乐。"""
        if self.audio is None or not self.audio.alive or not self._is_active(self.audio):
            return
        try:
            paused = bool(self.audio.props.get("pause"))
            self.audio.set("pause", not paused)
        except MpvError as exc:
            self.last_error = str(exc)

    def library_pause_targets(self, only: str | None = None) -> list[MpvClient]:
        """临时区暂停对象。only='audio'/'video' 时只取一路（叠播时跟选中走）。"""
        targets: list[MpvClient] = []
        want_audio = only in (None, "audio")
        want_video = only in (None, "video")
        if want_audio and self._lib_audio_on():
            targets.append(self.lib_audio)
        if (
            want_video
            and self.video_from_library
            and self.video is not None
            and self.video.alive
            and self._is_active(self.video)
        ):
            if self.video_ever_played or not bool(self.video.props.get("pause")):
                targets.append(self.video)
            elif self.video_on_stage:
                targets.append(self.video)
        return targets

    def is_library_paused(self, only: str | None = None) -> bool:
        targets = self.library_pause_targets(only)
        if not targets:
            return False
        return all(bool(client.props.get("pause")) for client in targets)

    def toggle_library_pause(self, only: str | None = None) -> None:
        targets = self.library_pause_targets(only)
        if not targets:
            return
        resume = all(bool(client.props.get("pause")) for client in targets)
        for client in targets:
            try:
                client.set("pause", not resume)
            except MpvError as exc:
                self.last_error = str(exc)
        if resume and self.video in targets:
            self.video_ever_played = True

    def pause_targets(self, cue: Cue | None = None) -> list[MpvClient]:
        """底栏暂停：只动节目单，不含临时配乐/临时视频。"""
        del cue
        targets: list[MpvClient] = []
        if self._show_audio_on():
            targets.append(self.audio)
        if (
            self.video is not None
            and self.video.alive
            and self._is_active(self.video)
            and not self.video_from_library
        ):
            targets.append(self.video)
        return targets

    def is_paused(self, cue: Cue | None) -> bool:
        targets = self.pause_targets(cue)
        if not targets or not all(bool(client.props.get("pause")) for client in targets):
            return False
        if self.video in targets and not self.video_ever_played and self.audio not in targets:
            return False
        return True

    def _same_audio(self, cue: Cue, *, library: bool = False) -> bool:
        if library:
            return (
                self.lib_audio is not None
                and self.lib_audio.alive
                and self.lib_audio_cue_id == cue.id
                and self._is_active(self.lib_audio)
            )
        return (
            self.audio is not None
            and self.audio.alive
            and self.audio_cue_id == cue.id
            and self._is_active(self.audio)
        )

    def _same_video(self, cue: Cue) -> bool:
        return (
            self.video is not None
            and self.video.alive
            and self.video_cue_id == cue.id
            and self._is_active(self.video)
        )

    @staticmethod
    def _client_paused(client: MpvClient | None) -> bool:
        return client is not None and bool(client.props.get("pause"))

    def toggle_pause(self, cue: Cue | None) -> None:
        targets = self.pause_targets(cue)
        if not targets:
            return
        resume = all(bool(client.props.get("pause")) for client in targets)
        for client in targets:
            try:
                client.set("pause", not resume)
            except MpvError as exc:
                self.last_error = str(exc)
        if resume and self.video in targets:
            self.video_ever_played = True

    def _active_client(self) -> MpvClient | None:
        """底栏进度只跟节目单（视频优先）；临时配乐/临时视频不进底栏。"""
        video_on = (
            self.video is not None
            and self.video.alive
            and self._is_active(self.video)
            and not self.video_from_library
        )
        audio_on = self._show_audio_on()
        video_playing = video_on and not bool(self.video.props.get("pause"))
        audio_playing = audio_on and not bool(self.audio.props.get("pause"))
        if video_playing:
            return self.video
        if audio_playing:
            return self.audio
        if video_on:
            return self.video
        if audio_on:
            return self.audio
        return None

    def seek_relative(self, seconds: float) -> None:
        client = self._active_client()
        if client is None:
            return
        try:
            client.command(["seek", seconds, "relative"])
        except MpvError as exc:
            self.last_error = str(exc)

    def _library_client(self) -> MpvClient | None:
        audio_on = self._lib_audio_on()
        video_on = (
            self.video_from_library
            and self.video is not None
            and self.video.alive
            and self._is_active(self.video)
        )
        audio_playing = audio_on and not bool(self.lib_audio.props.get("pause"))
        video_playing = video_on and not bool(self.video.props.get("pause"))
        if audio_playing:
            return self.lib_audio
        if video_playing:
            return self.video
        if audio_on:
            return self.lib_audio
        if video_on:
            return self.video
        return None

    def seek_library_relative(self, seconds: float) -> None:
        client = self._library_client()
        if client is None:
            return
        try:
            client.command(["seek", seconds, "relative"])
        except MpvError as exc:
            self.last_error = str(exc)

    def seek_library_fraction(self, ratio: float) -> None:
        self._seek_client_fraction(self._library_client(), ratio)

    def seek_library_audio_fraction(self, ratio: float) -> None:
        if not self._lib_audio_on():
            return
        self._seek_client_fraction(self.lib_audio, ratio)

    def seek_library_video_fraction(self, ratio: float) -> None:
        if (
            not self.video_from_library
            or self.video is None
            or not self.video.alive
            or not self._is_active(self.video)
        ):
            return
        self._seek_client_fraction(self.video, ratio)

    def _seek_client_fraction(self, client: MpvClient | None, ratio: float) -> None:
        if client is None:
            return
        _pos, duration = self._client_progress(client)
        if duration is None or duration <= 0:
            return
        target = max(0.0, min(duration, float(ratio) * duration))
        try:
            client.command(["seek", target, "absolute"])
            client.props["time-pos"] = target
        except MpvError as exc:
            self.last_error = str(exc)

    def library_audio_reached_eof(self) -> bool:
        if not self._lib_audio_on():
            return False
        return self._past_trim_out(self.lib_audio, self.lib_audio_trim_out)

    def library_video_reached_eof(self) -> bool:
        if self.hold_active or not self.video_from_library:
            return False
        if self.video is None or not self.video.alive or not self._is_active(self.video):
            return False
        if not self.video_ever_played:
            return False
        return self._past_trim_out(self.video, self.video_trim_out)

    def library_reached_eof(self) -> bool:
        """任一路到片尾。叠播时音频、视频要分别切歌，请用分路方法。"""
        return self.library_audio_reached_eof() or self.library_video_reached_eof()

    def nudge_library_volume(self, delta: float) -> int | None:
        return self.set_library_volume(self.library_volume + delta)

    def seek_video(self, seconds: float) -> None:
        self.seek_relative(seconds)

    def seek_fraction(self, ratio: float) -> None:
        client = self._active_client()
        if client is None:
            return
        _pos, duration = self._client_progress(client)
        if duration is None or duration <= 0:
            return
        target = max(0.0, min(duration, float(ratio) * duration))
        try:
            client.command(["seek", target, "absolute"])
            client.props["time-pos"] = target
        except MpvError as exc:
            self.last_error = str(exc)

    def set_volume(self, value: float, show_osd: bool = False) -> int:
        next_vol = max(0.0, min(100.0, float(value)))
        self.output_volume = next_vol
        client = self._active_client()
        if client is None:
            return int(round(next_vol))
        applied = self._audio_target_volume(library=False) if client is self.audio else next_vol
        try:
            client.set("volume", applied)
            client.props["volume"] = applied
            if show_osd:
                try:
                    client.command(["show-text", f"音量 {int(round(next_vol))}", 800])
                except MpvError:
                    pass
        except MpvError as exc:
            self.last_error = str(exc)
        return int(round(next_vol))

    def nudge_volume(self, delta: float) -> int | None:
        client = self._active_client()
        current = self.output_volume
        if client is not None:
            raw = client.props.get("volume")
            if raw is not None:
                try:
                    current = float(raw)
                except (TypeError, ValueError):
                    pass
        return self.set_volume(current + delta, show_osd=True)

    def nudge_video_volume(self, delta: float) -> int | None:
        return self.nudge_volume(delta)

    def stage_video(self, cue: Cue, media: Path | None, *, from_library: bool = False) -> None:
        self.last_error = ""
        if cue.type != "video":
            self.last_error = "全屏只对视频有效"
            return
        # 不关临时配乐：无声视频可叠播
        already = (
            self.video is not None
            and self.video.alive
            and self.video_cue_id == cue.id
            and self._is_active(self.video)
        )
        self._activate_video(cue, media, from_library=from_library)
        if self.video is None or not self.video.alive:
            return
        try:
            self._go_fullscreen()
            if not already:
                self.video.set("pause", True)
        except MpvError as exc:
            self.last_error = str(exc)

    def stage_loaded_video(self) -> None:
        self.last_error = ""
        if self.video is None or not self.video.alive or not self._is_active(self.video):
            self.last_error = "当前没有预监视频"
            return
        try:
            self._go_fullscreen()
        except MpvError as exc:
            self.last_error = str(exc)

    def play_video(self, cue: Cue) -> None:
        self.last_error = ""
        if cue.type != "video" or self.video is None or not self.video.alive:
            self.last_error = "当前没有已加载的视频"
            return
        # 保留临时配乐；有声视频请先停配乐。已全屏则不要关了再开。
        try:
            if self.video_on_stage and self.video.props.get("fullscreen") is not True:
                self._go_fullscreen()
            self.video.set("pause", False)
            self.video_ever_played = True
        except MpvError as exc:
            self.last_error = str(exc)

    def _go_fullscreen(self) -> None:
        """预监窗已在操作屏上时，必须先指定 fs-screen/screen，再全屏，否则 Windows 会全屏到当前屏。"""
        video = self.video
        if video is None or not video.alive:
            return
        target = self.projection_screen
        try:
            video.set("fullscreen", False)
        except MpvError:
            pass
        video.set("fs-screen", target)
        try:
            video.set("screen", target)
        except MpvError:
            pass
        video.set("fullscreen", True)
        video.set("cursor-autohide", "always")
        self.video_on_stage = True

    def unstage_video(self) -> None:
        self.last_error = ""
        if self.video is None or not self.video.alive:
            return
        try:
            self.video.set("fullscreen", False)
            self.video.set("screen", self.preview_screen)
            self.video.set("window-maximized", False)
            self.video.set("ontop", True)
            self.video_on_stage = False
        except MpvError as exc:
            self.last_error = str(exc)

    def reap(self) -> None:
        if self.audio is not None and not self.audio.alive:
            self._stop_show_audio()
        if self.lib_audio is not None and not self.lib_audio.alive:
            self._stop_lib_audio()
        if self.video is not None and not self.video.alive:
            self._forget_video()

    def exit_video(self) -> None:
        self._stop_video_only()

    def live_cue_state(self) -> tuple[str | None, str]:
        """底栏/节目单高亮：不含临时配乐。"""
        if self.hold_active and self.video_cue_id:
            return self.video_cue_id, "cover"
        if self._fading_show:
            if self.audio_cue_id:
                return self.audio_cue_id, "paused"
            if self.video_cue_id and not self.video_from_library:
                return self.video_cue_id, "paused"
            return None, ""
        if (
            self.video is not None
            and self.video.alive
            and self._is_active(self.video)
            and self.video_cue_id
            and not self.video_from_library
        ):
            if not bool(self.video.props.get("pause")):
                return self.video_cue_id, "playing"
            if self.video_ever_played or self.video_on_stage:
                return self.video_cue_id, "paused"
            return self.video_cue_id, "preview"
        if self._show_audio_on() and self.audio_cue_id:
            paused = bool(self.audio.props.get("pause"))
            return self.audio_cue_id, "paused" if paused else "playing"
        return None, ""

    def live_audio_state(self) -> tuple[str | None, str]:
        """右侧临时配乐高亮（仅 library 通道）。"""
        if not self._lib_audio_on() or not self.lib_audio_cue_id:
            return None, ""
        if self._fading_lib:
            return self.lib_audio_cue_id, "paused"
        paused = bool(self.lib_audio.props.get("pause"))
        return self.lib_audio_cue_id, "paused" if paused else "playing"

    def audio_progress(self) -> tuple[float | None, float | None]:
        if not self._lib_audio_on():
            return None, None
        return self._client_progress(self.lib_audio)

    def library_progress(self) -> tuple[float | None, float | None]:
        """右侧临时区进度：优先配乐，否则临时视频。"""
        pos, dur = self.audio_progress()
        if pos is not None or dur is not None:
            return pos, dur
        return self.library_video_progress()

    def library_video_progress(self) -> tuple[float | None, float | None]:
        if (
            self.video_from_library
            and self.video is not None
            and self.video.alive
            and self._is_active(self.video)
        ):
            return self._client_progress(self.video)
        return None, None

    def live_library_video_state(self) -> tuple[str | None, str]:
        if self.hold_active and self.video_from_library and self.video_cue_id:
            return self.video_cue_id, "cover"
        if (
            self.video_from_library
            and self.video is not None
            and self.video.alive
            and self._is_active(self.video)
            and self.video_cue_id
        ):
            if not bool(self.video.props.get("pause")):
                return self.video_cue_id, "playing"
            if self.video_ever_played or self.video_on_stage:
                return self.video_cue_id, "paused"
            return self.video_cue_id, "preview"
        return None, ""

    def live_library_state(self) -> tuple[str | None, str]:
        """兼容旧调用：优先音频，否则视频。"""
        aid, astate = self.live_audio_state()
        if aid:
            return aid, astate
        return self.live_library_video_state()

    def library_live_map(self) -> dict[str, str]:
        """临时列表可同时高亮音频和视频。"""
        out: dict[str, str] = {}
        aid, astate = self.live_audio_state()
        if aid:
            out[aid] = astate
        vid, vstate = self.live_library_video_state()
        if vid:
            out[vid] = vstate
        return out

    def video_needs_hotkeys(self) -> bool:
        if self.video is None or not self.video.alive or not self._is_active(self.video):
            return False
        return bool(self.video.props.get("fullscreen") or self.video_on_stage)

    def status(self) -> RuntimeStatus:
        self.reap()
        if self._fading_show:
            return RuntimeStatus(
                audio_state="渐停中" if self.audio is not None else "空闲",
                audio_name=self.audio_name,
                video_state="渐停中" if self.video is not None else "未加载",
                video_name=self.video_name,
                position=None,
                duration=None,
            )
        audio_state = "空闲"
        if self.audio is not None and self.audio.alive and self._is_active(self.audio):
            audio_state = "已暂停" if self.audio.props.get("pause") else "播放中"
        video_state = "未加载"
        if self.video is not None and self.video.alive and self._is_active(self.video):
            paused = bool(self.video.props.get("pause", True))
            fullscreen = bool(self.video.props.get("fullscreen") or self.video_on_stage)
            if not paused:
                video_state = "播放中"
            elif self.video_ever_played:
                video_state = "已全屏·已暂停" if fullscreen else "已暂停"
            elif fullscreen:
                video_state = "已全屏"
            else:
                video_state = "已加载"
        volume = int(round(self.output_volume))
        position, duration = self._active_progress()
        return RuntimeStatus(
            audio_state=audio_state,
            audio_name=self.audio_name,
            video_state=video_state,
            video_name=self.video_name,
            volume=volume,
            position=position,
            duration=duration,
            message=self.last_error,
        )

    def _active_progress(self) -> tuple[float | None, float | None]:
        return self._client_progress(self._active_client())

    @staticmethod
    def _client_progress(client: MpvClient | None) -> tuple[float | None, float | None]:
        if client is None:
            return None, None

        def as_float(raw: object) -> float | None:
            if raw is None:
                return None
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return None
            if value < 0:
                return None
            return value

        return as_float(client.props.get("time-pos")), as_float(client.props.get("duration"))

    def _activate_audio(
        self,
        cue: Cue,
        media: Path | None,
        *,
        stop_video: bool = True,
        loop: bool | None = None,
        from_library: bool = False,
    ) -> None:
        self._duck_ramping = False
        if from_library:
            self._cancel_fade(library=True)
            if self._show_audio_on() or self._fading_show:
                self._cancel_fade(library=False)
                self._stop_show_audio()
        else:
            self._cancel_fade(library=False)
            if self._lib_audio_on() or self._fading_lib:
                self._cancel_fade(library=True)
                self._stop_lib_audio()
        if media is None or not media.exists():
            self.last_error = "音频文件不存在"
            return
        if self._same_audio(cue, library=from_library):
            return
        if stop_video and not from_library and not self.video_from_library:
            self._stop_video_only()
        try:
            client = self._ensure_lib_audio() if from_library else self._ensure_audio()
            client.loadfile(media, paused=False, loop=cue.loop if loop is None else bool(loop))
            self._apply_trim_in(client, cue)
            if from_library:
                self.lib_audio_trim_out = cue.trim_out
                self.lib_audio_fade_out = cue.fade_out
            else:
                self.show_audio_trim_out = cue.trim_out
                self.show_audio_fade_out = cue.fade_out
            self._fade_in_seconds = cue.fade_in or FADE_SECONDS
            try:
                if self.master_muted:
                    client.set("mute", True)
                    client.set("volume", 0)
                    self.pending_fade_in = None
                else:
                    client.set("mute", False)
                    client.set("volume", 0)
                    self.pending_fade_in = "lib" if from_library else "show"
            except MpvError:
                self.pending_fade_in = None
            if from_library:
                self.lib_audio_cue_id = cue.id
                self.lib_audio_name = cue.name or media.name
            else:
                self.audio_cue_id = cue.id
                self.audio_name = cue.name or media.name
            self.stopped_audio_id = None
            if self._any_audio_on():
                self._set_video_muted(True)
        except MpvError as exc:
            self.last_error = str(exc)

    def _activate_video(
        self,
        cue: Cue,
        media: Path | None,
        *,
        from_library: bool = False,
        loop: bool | None = None,
        autoplay: bool = False,
    ) -> None:
        self.hold_active = False
        if media is None or not media.exists():
            self.last_error = "视频文件不存在"
            return
        # 节目单音视频互斥；临时视频仍可叠临时音频
        if not from_library and (self._show_audio_on() or self._fading_show):
            self._cancel_fade(library=False)
            self._stop_show_audio()
        if (
            self.video is not None
            and self.video.alive
            and self.video_cue_id == cue.id
            and self._is_active(self.video)
        ):
            self.video_from_library = from_library
            if autoplay:
                self.play_video(cue)
            return
        keep_stage = bool(self.video_on_stage)
        reuse = self.video is not None and self.video.alive
        try:
            client = self.video if reuse else self._ensure_video()
            try:
                client.set("keepaspect", True)
            except MpvError:
                pass
            client.loadfile(
                media,
                paused=not autoplay,
                loop=cue.loop if loop is None else bool(loop),
            )
            self._apply_trim_in(client, cue)
            self.video_trim_out = cue.trim_out
            self.video_from_library = from_library
            try:
                vol = self.library_volume if from_library else self.output_volume
                client.set("volume", vol)
            except MpvError:
                pass
            if self.master_muted:
                try:
                    client.set("mute", True)
                    client.set("volume", 0)
                except MpvError:
                    pass
            self._set_video_muted(self._any_audio_on())
            self.video_cue_id = cue.id
            self.video_name = cue.name or media.name
            self.video_ever_played = bool(autoplay)
            if reuse:
                self.video_on_stage = keep_stage
            else:
                self.video_on_stage = False
            if autoplay:
                try:
                    client.set("pause", False)
                    self.video_ever_played = True
                except MpvError:
                    pass
            # 已在全屏则保持，绝不先关全屏再打开；小窗也保持小窗
            if keep_stage and reuse and client.props.get("fullscreen") is not True:
                try:
                    client.set("fs-screen", self.projection_screen)
                    client.set("fullscreen", True)
                    self.video_on_stage = True
                except MpvError as exc:
                    self.last_error = str(exc)
        except MpvError as exc:
            self.last_error = str(exc)

    def set_library_volume(self, value: float) -> int:
        """临时通道音量（只作用于临时配乐/临时视频）。"""
        next_vol = max(0.0, min(100.0, float(value)))
        self.library_volume = next_vol
        clients: list[MpvClient] = []
        if self._lib_audio_on():
            clients.append(self.lib_audio)
        if (
            self.video_from_library
            and self.video is not None
            and self.video.alive
            and self._is_active(self.video)
        ):
            clients.append(self.video)
        for client in clients:
            try:
                applied = (
                    self._audio_target_volume(library=True)
                    if client is self.lib_audio
                    else next_vol
                )
                client.set("volume", applied)
                client.props["volume"] = applied
            except MpvError as exc:
                self.last_error = str(exc)
        return int(round(next_vol))

    def _set_video_muted(self, muted: bool) -> None:
        if self.video is None or not self.video.alive:
            return
        try:
            self.video.set("mute", muted)
        except MpvError:
            try:
                restore = self.library_volume if self.video_from_library else self.output_volume
                self.video.set("volume", 0 if muted else restore)
            except MpvError:
                pass

    def _live_players(self) -> list[MpvClient]:
        players: list[MpvClient] = []
        for client in (self.audio, self.lib_audio, self.video):
            if client is not None and client.alive:
                players.append(client)
        return players

    def set_master_mute(self, muted: bool) -> None:
        """一键静音：所有声道立刻无声；再按恢复。"""
        self.master_muted = bool(muted)
        if muted:
            self.pending_fade_in = None
        for client in self._live_players():
            try:
                client.set("mute", muted)
                if muted:
                    client.set("volume", 0)
                elif client is self.lib_audio:
                    client.set("volume", self._audio_target_volume(library=True))
                elif client is self.audio:
                    client.set("volume", self._audio_target_volume(library=False))
                elif client is self.video:
                    restore = self.library_volume if self.video_from_library else self.output_volume
                    if not self._any_audio_on():
                        client.set("volume", restore)
            except MpvError as exc:
                self.last_error = str(exc)

    def toggle_master_mute(self) -> bool:
        self.set_master_mute(not self.master_muted)
        return self.master_muted

    def _apply_bed_volume(self) -> None:
        """按当前目标音量写到正在播的垫乐（临时优先，否则节目单）。不停止。"""
        if self.master_muted:
            return
        try:
            if self._lib_audio_on():
                vol = self._audio_target_volume(library=True)
                self.lib_audio.set("volume", vol)
                if self._fade_in and self._fade_library:
                    self._fade_target = vol
            elif self._show_audio_on():
                vol = self._audio_target_volume(library=False)
                self.audio.set("volume", vol)
                if self._fade_in and not self._fade_library:
                    self._fade_target = vol
        except MpvError as exc:
            self.last_error = str(exc)

    def _live_bed(self) -> tuple[MpvClient | None, bool]:
        if self._lib_audio_on():
            return self.lib_audio, True
        if self._show_audio_on():
            return self.audio, False
        return None, False

    def begin_duck_ramp(self) -> bool:
        """把当前垫乐从现在音量渐变到目标。True = 需要定时器。不停止播放。"""
        if self.master_muted:
            return False
        client, library = self._live_bed()
        if client is None:
            return False
        stopping = (library and self._fading_lib and not self._fade_in) or (
            not library and self._fading_show and not self._fade_in
        )
        if stopping:
            return False
        if self._fade_in and self._fade_library == library:
            self._fade_in = False
            self._cancel_fade(library=library)
        try:
            raw = client.props.get("volume")
            current = float(raw) if raw is not None else self._audio_target_volume(library=library)
        except (TypeError, ValueError):
            current = self._audio_target_volume(library=library)
        target = self._audio_target_volume(library=library)
        if abs(current - target) < 0.8:
            try:
                client.set("volume", target)
            except MpvError:
                pass
            self._duck_ramping = False
            return False
        self._duck_ramping = True
        self._duck_client = client
        self._duck_library = library
        self._duck_from = current
        self._duck_to = target
        self._duck_i = 0
        self._duck_steps = DUCK_STEPS
        return True

    def duck_tick(self) -> bool:
        if not self._duck_ramping:
            return False
        client = self._duck_client
        expected = self.lib_audio if self._duck_library else self.audio
        if client is None or client is not expected or not client.alive:
            self._duck_ramping = False
            return False
        self._duck_i += 1
        t = min(1.0, self._duck_i / self._duck_steps)
        t = t * t * (3.0 - 2.0 * t)
        vol = self._duck_from + (self._duck_to - self._duck_from) * t
        try:
            client.set("volume", vol)
        except MpvError:
            pass
        if self._duck_i >= self._duck_steps:
            try:
                client.set("volume", self._duck_to)
            except MpvError:
                pass
            self._duck_ramping = False
            return False
        return True

    def set_duck(self, ducked: bool) -> bool:
        """压低到设定音量的 60%。True = 正在渐变。不暂停、不停止。"""
        self.ducked = bool(ducked)
        return self.begin_duck_ramp()

    def toggle_duck(self) -> bool:
        """切换压低。返回值表示是否需要开定时器做渐变。"""
        return self.set_duck(not self.ducked)

    def video_reached_eof(self) -> bool:
        if self.hold_active:
            return False
        if self.video is None or not self.video.alive or not self._is_active(self.video):
            return False
        if not self.video_ever_played:
            return False
        return self._past_trim_out(self.video, self.video_trim_out)

    def show_hold(self, image: Path, *, from_library: bool, stay_staged: bool) -> None:
        """视频播完或一键封面：投封面图（或黑图）。"""
        if not image.exists():
            self.last_error = "封面图不存在"
            return
        staged = bool(stay_staged or self.video_on_stage)
        try:
            client = self._ensure_video()
            try:
                client.set("keepaspect", image.name != "hold_black.png")
            except MpvError:
                pass
            client.loadfile(image, paused=False, loop=True)
            self.hold_active = True
            self.video_from_library = from_library
            self.video_name = "封面"
            self.video_ever_played = True
            if staged:
                self._go_fullscreen()
            if self.master_muted:
                try:
                    client.set("mute", True)
                    client.set("volume", 0)
                except MpvError:
                    pass
            if self._any_audio_on():
                self._set_video_muted(True)
        except MpvError as exc:
            self.last_error = str(exc)

    def apply_loop(self, cue: Cue, loop: bool | None = None) -> None:
        client = None
        if cue.type == "audio":
            if self.lib_audio_cue_id == cue.id:
                client = self.lib_audio
            elif self.audio_cue_id == cue.id:
                client = self.audio
        elif cue.type == "video" and self.video_cue_id == cue.id:
            client = self.video
        if client is None or not client.alive:
            return
        enabled = cue.loop if loop is None else bool(loop)
        try:
            client.set("loop-file", "inf" if enabled else "no")
        except MpvError as exc:
            self.last_error = str(exc)

    def _stop_show_audio(self) -> None:
        self._cancel_fade(library=False)
        if self.audio is None:
            return
        if self.audio_cue_id:
            self.stopped_audio_id = self.audio_cue_id
        self.audio.stop()
        self.audio = None
        self.audio_cue_id = None
        self.audio_name = ""
        if not self._lib_audio_on():
            self._set_video_muted(False)

    def _stop_lib_audio(self) -> None:
        self._cancel_fade(library=True)
        if self.lib_audio is None:
            return
        self.lib_audio.stop()
        self.lib_audio = None
        self.lib_audio_cue_id = None
        self.lib_audio_name = ""
        if not self._show_audio_on():
            self._set_video_muted(False)

    def _stop_audio_only(self) -> None:
        """兼容旧调用：停节目单音频。"""
        self._stop_show_audio()

    def _forget_video(self) -> None:
        self.video = None
        self.video_cue_id = None
        self.video_name = ""
        self.video_from_library = False
        self.video_ever_played = False
        self.video_on_stage = False
        self.hold_active = False

    def _stop_video_only(self) -> None:
        if self.video is None:
            return
        self.video.stop()
        self._forget_video()

    def _ensure_audio(self) -> MpvClient:
        if self.audio is not None and self.audio.alive:
            return self.audio
        if self.mpv_exe is None:
            raise MpvError("未配置 mpv")
        client = MpvClient(self.mpv_exe, "audio")
        client.start(
            [
                "--force-window=no",
                "--vid=no",
                "--input-vo-keyboard=no",
                "--title=控场-音频",
                *self._audio_device_args(),
            ]
        )
        self.audio = client
        return client

    def _ensure_lib_audio(self) -> MpvClient:
        if self.lib_audio is not None and self.lib_audio.alive:
            return self.lib_audio
        if self.mpv_exe is None:
            raise MpvError("未配置 mpv")
        client = MpvClient(self.mpv_exe, "lib-audio")
        client.start(
            [
                "--force-window=no",
                "--vid=no",
                "--input-vo-keyboard=no",
                "--title=控场-素材库音频",
                *self._audio_device_args(),
            ]
        )
        self.lib_audio = client
        return client

    def warm_audio_players(self) -> None:
        """启动后空闲拉起两路音频 mpv，避免第一次点播放卡一下。"""
        try:
            self._ensure_audio()
        except MpvError as exc:
            self.last_error = str(exc)
        try:
            self._ensure_lib_audio()
        except MpvError as exc:
            self.last_error = str(exc)

    def _forward_client_message(self, args: list[str]) -> None:
        callback = self.on_client_message
        if callback is not None:
            callback(args)

    def _ensure_video(self) -> MpvClient:
        if self.video is not None and self.video.alive:
            return self.video
        if self.mpv_exe is None:
            raise MpvError("未配置 mpv")
        from src.paths import video_input_conf

        client = MpvClient(self.mpv_exe, "video")
        client.on_client_message = self._forward_client_message
        client.start(
            [
                "--pause",
                "--force-window=yes",
                "--fs=no",
                f"--screen={self.preview_screen}",
                f"--fs-screen={self.projection_screen}",
                "--autofit=640x360",
                "--geometry=80:80",
                "--ontop=yes",
                "--title=控场-视频预监",
                "--cursor-autohide=always",
                "--input-vo-keyboard=yes",
                f"--input-conf={video_input_conf()}",
                "--input-default-bindings=no",
                *self._audio_device_args(),
            ]
        )
        self.video = client
        return client

    @staticmethod
    def _is_active(client: MpvClient) -> bool:
        if client.props.get("idle-active") is True:
            return False
        path = client.props.get("path") or client.media_path
        return bool(path)
