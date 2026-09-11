from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path

from src.models import Cue
from src.mpv_ipc import MpvClient, MpvError

FADE_SECONDS = 1.6


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
        self.audio: MpvClient | None = None
        self.video: MpvClient | None = None
        self.audio_cue_id: str | None = None
        self.video_cue_id: str | None = None
        self.audio_name = ""
        self.video_name = ""
        self.audio_from_library = False  # True=右侧临时配乐，与底栏节目单独立
        self.video_from_library = False  # True=右侧临时视频（与节目单视频互斥，同用一个播放器）
        self.video_ever_played = False
        self.video_on_stage = False
        self.stopped_audio_id: str | None = None
        self.last_error = ""
        self._fading = False
        self._fade_lock = threading.Lock()
        self.on_client_message = None
        self.on_fade_done = None
        self.output_volume = 100.0
        self.library_volume = 100.0

    def configure(self, mpv_exe: Path, projection_screen: int, preview_screen: int) -> None:
        self.mpv_exe = mpv_exe
        self.projection_screen = max(0, projection_screen)
        self.preview_screen = max(0, preview_screen)

    def shutdown(self) -> None:
        self.stop_all()

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
    ) -> str:
        """播放条目。
        under_video：临时音频叠在视频上。
        from_library：来自右侧临时列表（视频与节目单互斥，同用一个播放器）。
        """
        self.last_error = ""
        if self._fading:
            # 渐停线程还握着同一个 mpv，不先关掉会把新节目音量压没。
            if under_video and cue.type == "audio":
                self._fading = False
                self._stop_audio_only()
            else:
                self.stop_all()
        action = self.go_action(cue)
        if cue.type == "note" or action == "disabled":
            return ""
        if cue.type == "audio":
            if action == "replay":
                self._restart_audio(cue, media, stop_video=not under_video)
                return ""
            if action == "playing":
                return ""
            self._activate_audio(cue, media, stop_video=not under_video)
            return ""
        if cue.type == "video":
            if action == "playing":
                return ""
            if action == "replay":
                self._restart_video(cue, media, from_library=from_library)
                return ""
            if action == "play":
                self.play_video(cue)
                return ""
            self._activate_video(cue, media, from_library=from_library)
            return ""
        return ""

    def go_action(self, cue: Cue | None) -> str:
        if cue is None:
            return "disabled"
        if cue.type == "note":
            return "disabled"
        if self._fading:
            return "play"
        if cue.type == "audio":
            if self._same_audio(cue):
                if self._client_paused(self.audio):
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
            return "preview"
        return "play"

    def _restart_audio(self, cue: Cue, media: Path | None, *, stop_video: bool = True) -> None:
        if self._same_audio(cue) and self.audio is not None:
            try:
                self.audio.command(["seek", 0, "absolute"])
                self.audio.set("pause", False)
                return
            except MpvError:
                pass
        if self._same_audio(cue):
            self._stop_audio_only()
        self._activate_audio(cue, media, stop_video=stop_video)

    def _restart_video(self, cue: Cue, media: Path | None, *, from_library: bool = False) -> None:
        if self._same_video(cue) and self.video is not None:
            try:
                self.video.command(["seek", 0, "absolute"])
                self.video.set("pause", False)
                self.video_ever_played = True
                self.video_from_library = from_library
                return
            except MpvError:
                pass
        if self._same_video(cue):
            self._stop_video_only()
        self._activate_video(cue, media, from_library=from_library)
        if self._same_video(cue):
            self.play_video(cue)

    def stop_all(self) -> None:
        self._fading = False
        if self.audio_cue_id:
            self.stopped_audio_id = self.audio_cue_id
        if self.audio is not None:
            self.audio.stop()
            self.audio = None
        if self.video is not None:
            self.video.stop()
            self.video = None
        self.audio_cue_id = None
        self.video_cue_id = None
        self.audio_name = ""
        self.video_name = ""
        self.audio_from_library = False
        self.video_from_library = False
        self.video_ever_played = False
        self.video_on_stage = False

    def fade_stop(self, seconds: float = FADE_SECONDS) -> None:
        """底栏停止：只停节目单音视频，不动右侧临时配乐。"""
        main_audio = (
            self.audio is not None
            and self.audio.alive
            and self._is_active(self.audio)
            and not self.audio_from_library
        )
        video_live = (
            self.video is not None and self.video.alive and self._is_active(self.video)
        )
        if main_audio:
            self.fade_stop_audio(seconds)
            return
        if video_live:
            self._stop_video_only()
            return

    def fade_stop_audio(self, seconds: float = FADE_SECONDS) -> None:
        """只停音频配乐，不动视频。"""
        audio_live = (
            self.audio is not None and self.audio.alive and self._is_active(self.audio)
        )
        if not audio_live:
            self._stop_audio_only()
            return
        if self.audio is not None and bool(self.audio.props.get("pause")):
            self._stop_audio_only()
            return
        with self._fade_lock:
            if self._fading:
                self._fading = False
                self._stop_audio_only()
                return
            self._fading = True
        threading.Thread(target=self._fade_audio_then_stop, args=(seconds,), daemon=True).start()

    def _fade_audio_then_stop(self, seconds: float) -> None:
        client = self.audio
        steps = 16
        try:
            if client is None or not client.alive:
                return
            try:
                raw = client.get("volume")
                vol = float(raw) if raw is not None else 100.0
            except MpvError:
                vol = 100.0
            for i in range(steps):
                if not self._fading:
                    return
                if client is not self.audio or not client.alive:
                    return
                factor = 1.0 - (i + 1) / steps
                try:
                    client.set("volume", max(0.0, vol * factor))
                except MpvError:
                    pass
                time.sleep(seconds / steps)
        finally:
            if self._fading:
                self._stop_audio_only()
                self._fading = False
            done = self.on_fade_done
            if done is not None:
                done()

    def toggle_audio_pause(self) -> None:
        """只暂停/继续音频配乐。"""
        if self.audio is None or not self.audio.alive or not self._is_active(self.audio):
            return
        try:
            paused = bool(self.audio.props.get("pause"))
            self.audio.set("pause", not paused)
        except MpvError as exc:
            self.last_error = str(exc)

    def library_pause_targets(self) -> list[MpvClient]:
        """临时区暂停对象：临时配乐 + 临时视频（不含节目单）。"""
        targets: list[MpvClient] = []
        if (
            self.audio_from_library
            and self.audio is not None
            and self.audio.alive
            and self._is_active(self.audio)
        ):
            targets.append(self.audio)
        if (
            self.video_from_library
            and self.video is not None
            and self.video.alive
            and self._is_active(self.video)
        ):
            # 预监未开播的不进暂停组（与节目单一致）
            if self.video_ever_played or not bool(self.video.props.get("pause")):
                targets.append(self.video)
            elif self.video_on_stage:
                targets.append(self.video)
        return targets

    def is_library_paused(self) -> bool:
        targets = self.library_pause_targets()
        if not targets:
            return False
        return all(bool(client.props.get("pause")) for client in targets)

    def toggle_library_pause(self) -> None:
        targets = self.library_pause_targets()
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
        """底栏暂停：只动节目单，不含临时配乐。"""
        del cue
        targets: list[MpvClient] = []
        if (
            self.audio is not None
            and self.audio.alive
            and self._is_active(self.audio)
            and not self.audio_from_library
        ):
            targets.append(self.audio)
        if self.video is not None and self.video.alive and self._is_active(self.video):
            targets.append(self.video)
        return targets

    def is_paused(self, cue: Cue | None) -> bool:
        targets = self.pause_targets(cue)
        if not targets or not all(bool(client.props.get("pause")) for client in targets):
            return False
        if self.video in targets and not self.video_ever_played and self.audio not in targets:
            return False
        return True

    def _same_audio(self, cue: Cue) -> bool:
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
        """底栏进度只跟节目单（视频优先）；临时配乐不进底栏。"""
        video_on = self.video is not None and self.video.alive and self._is_active(self.video)
        audio_on = (
            self.audio is not None
            and self.audio.alive
            and self._is_active(self.audio)
            and not self.audio_from_library
        )
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
        try:
            client.set("volume", next_vol)
            client.props["volume"] = next_vol
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
        # 保留临时配乐；有声视频请先停配乐
        try:
            if self.video_on_stage:
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
            self._stop_audio_only()
        if self.video is not None and not self.video.alive:
            self._forget_video()

    def exit_video(self) -> None:
        self._stop_video_only()

    def live_cue_state(self) -> tuple[str | None, str]:
        """底栏/节目单高亮：不含临时配乐。"""
        if self._fading and not self.audio_from_library:
            if self.audio_cue_id:
                return self.audio_cue_id, "paused"
            if self.video_cue_id:
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
        if (
            self.audio is not None
            and self.audio.alive
            and self._is_active(self.audio)
            and self.audio_cue_id
            and not self.audio_from_library
        ):
            paused = bool(self.audio.props.get("pause"))
            return self.audio_cue_id, "paused" if paused else "playing"
        return None, ""

    def live_audio_state(self) -> tuple[str | None, str]:
        """右侧临时配乐高亮（仅 library 通道）。"""
        if (
            not self.audio_from_library
            or self.audio is None
            or not self.audio.alive
            or not self._is_active(self.audio)
            or not self.audio_cue_id
        ):
            return None, ""
        if self._fading:
            return self.audio_cue_id, "paused"
        paused = bool(self.audio.props.get("pause"))
        return self.audio_cue_id, "paused" if paused else "playing"

    def audio_progress(self) -> tuple[float | None, float | None]:
        if (
            not self.audio_from_library
            or self.audio is None
            or not self.audio.alive
            or not self._is_active(self.audio)
        ):
            return None, None
        return self._client_progress(self.audio)

    def library_progress(self) -> tuple[float | None, float | None]:
        """右侧临时区进度：优先配乐，否则临时视频。"""
        pos, dur = self.audio_progress()
        if pos is not None or dur is not None:
            return pos, dur
        if (
            self.video_from_library
            and self.video is not None
            and self.video.alive
            and self._is_active(self.video)
        ):
            return self._client_progress(self.video)
        return None, None

    def live_library_state(self) -> tuple[str | None, str]:
        """右侧列表高亮：临时配乐或临时视频。"""
        aid, astate = self.live_audio_state()
        if aid:
            return aid, astate
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

    def video_needs_hotkeys(self) -> bool:
        if self.video is None or not self.video.alive or not self._is_active(self.video):
            return False
        return bool(self.video.props.get("fullscreen") or self.video_on_stage)

    def status(self) -> RuntimeStatus:
        self.reap()
        if self._fading:
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
        volume = None
        client = self._active_client()
        if client is not None:
            raw = client.props.get("volume")
            if raw is not None:
                try:
                    volume = int(round(float(raw)))
                except (TypeError, ValueError):
                    volume = None
        if volume is None:
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

    def _activate_audio(self, cue: Cue, media: Path | None, *, stop_video: bool = True) -> None:
        self._fading = False
        if media is None or not media.exists():
            self.last_error = "音频文件不存在"
            return
        if (
            self.audio is not None
            and self.audio.alive
            and self.audio_cue_id == cue.id
            and self._is_active(self.audio)
        ):
            return
        if stop_video:
            self._stop_video_only()
        try:
            client = self._ensure_audio()
            client.loadfile(media, paused=False, loop=cue.loop)
            self.audio_from_library = not stop_video
            try:
                vol = self.library_volume if self.audio_from_library else self.output_volume
                client.set("volume", vol)
            except MpvError:
                pass
            self.audio_cue_id = cue.id
            self.audio_name = cue.name or media.name
            self.stopped_audio_id = None
            # 临时配乐叠视频时静音视频轨，避免双声
            if self.audio_from_library:
                self._set_video_muted(True)
        except MpvError as exc:
            self.last_error = str(exc)

    def _activate_video(self, cue: Cue, media: Path | None, *, from_library: bool = False) -> None:
        self._fading = False
        if media is None or not media.exists():
            self.last_error = "视频文件不存在"
            return
        if (
            self.video is not None
            and self.video.alive
            and self.video_cue_id == cue.id
            and self._is_active(self.video)
        ):
            self.video_from_library = from_library
            return
        # 全局只播一个视频：加载新片会关掉当前片（节目单↔临时互斥）
        # 不关临时配乐；有声片请先停配乐
        try:
            if self.video is not None:
                self.video.stop()
                self.video = None
            client = self._ensure_video()
            client.loadfile(media, paused=True, loop=cue.loop)
            self.video_from_library = from_library
            try:
                vol = self.library_volume if from_library else self.output_volume
                client.set("volume", vol)
            except MpvError:
                pass
            if self.audio is not None and self.audio.alive and self._is_active(self.audio):
                self._set_video_muted(True)
            else:
                self._set_video_muted(False)
            self.video_cue_id = cue.id
            self.video_name = cue.name or media.name
            self.video_ever_played = False
            self.video_on_stage = False
        except MpvError as exc:
            self.last_error = str(exc)

    def set_library_volume(self, value: float) -> int:
        """临时通道音量（只作用于临时配乐/临时视频）。"""
        next_vol = max(0.0, min(100.0, float(value)))
        self.library_volume = next_vol
        clients: list[MpvClient] = []
        if (
            self.audio_from_library
            and self.audio is not None
            and self.audio.alive
            and self._is_active(self.audio)
        ):
            clients.append(self.audio)
        if (
            self.video_from_library
            and self.video is not None
            and self.video.alive
            and self._is_active(self.video)
        ):
            clients.append(self.video)
        for client in clients:
            try:
                # 若视频因叠配乐被 mute，仍记下音量，取消 mute 后生效
                client.set("volume", next_vol)
                client.props["volume"] = next_vol
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

    def apply_loop(self, cue: Cue) -> None:
        client = None
        if cue.type == "audio" and self.audio_cue_id == cue.id:
            client = self.audio
        elif cue.type == "video" and self.video_cue_id == cue.id:
            client = self.video
        if client is None or not client.alive:
            return
        try:
            client.set("loop-file", "inf" if cue.loop else "no")
        except MpvError as exc:
            self.last_error = str(exc)

    def _stop_audio_only(self) -> None:
        if self.audio is None:
            return
        was_bed = self.audio_from_library
        if self.audio_cue_id:
            self.stopped_audio_id = self.audio_cue_id
        self.audio.stop()
        self.audio = None
        self.audio_cue_id = None
        self.audio_name = ""
        self.audio_from_library = False
        self._fading = False
        if was_bed:
            self._set_video_muted(False)

    def _forget_video(self) -> None:
        self.video = None
        self.video_cue_id = None
        self.video_name = ""
        self.video_from_library = False
        self.video_ever_played = False
        self.video_on_stage = False

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
            ]
        )
        self.audio = client
        return client

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
