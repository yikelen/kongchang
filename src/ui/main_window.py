from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QByteArray, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QColor, QFont, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QSplitter,
)

from src import __version__
from src.controller import ShowController
from src.models import (
    LIB_PLAY_ALL,
    LIB_PLAY_DEFAULT,
    LIB_PLAY_ONE,
    LIB_PLAY_SEQ,
    SHOW_MIRROR_CATEGORY,
    TYPE_LABELS,
    Cue,
    Project,
    cue_category_key,
    library_play_label,
    library_play_tip,
    next_library_in_category,
    next_library_play_mode,
    new_id,
    rebuild_library_from_visual,
)
from src.mpv_ipc import display_index_for_hwnd, display_index_for_point, list_windows_displays
from src.settings import AppSettings
from src.ui.theme import stylesheet, theme_colors

AUDIO_FILTER = "音频 (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.wma);;所有 (*.*)"
VIDEO_FILTER = "视频 (*.mp4 *.mov *.mkv *.webm *.avi *.m4v);;所有 (*.*)"
IMAGE_FILTER = "图片 (*.jpg *.jpeg *.png *.webp *.bmp *.gif);;所有 (*.*)"
_MODE_BTN_TEXT = {
    LIB_PLAY_DEFAULT: "● 默认",
    LIB_PLAY_ONE: "🔂 单曲",
    LIB_PLAY_SEQ: "→ 顺序",
    LIB_PLAY_ALL: "🔁 列表",
}
# 临时音频列表里的分类标题行（非媒体）
LIB_HEADER = "__lib_category_header__"
LIB_UNCATEGORIZED = "未分类"


class CueTable(QTableWidget):
    row_dropped = Signal(int, int)
    arrow_pressed = Signal(int)
    _ROW_MIME = "application/x-kongchang-row"

    def __init__(self) -> None:
        super().__init__(0, 5)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropOverwriteMode(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.arrow_eaten = False

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.arrow_pressed.emit(key)
            if self.arrow_eaten or key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
                return
        super().keyPressEvent(event)

    def mimeData(self, items):
        mime = super().mimeData(items)
        rows = {item.row() for item in items}
        if len(rows) == 1:
            mime.setData(self._ROW_MIME, str(next(iter(rows))).encode("ascii"))
        return mime

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        if not mime.hasFormat(self._ROW_MIME):
            event.ignore()
            return
        source = int(bytes(mime.data(self._ROW_MIME)).decode("ascii"))
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        dest = self.indexAt(pos).row()
        indicator = self.dropIndicatorPosition()
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        if source < 0:
            return
        if dest < 0:
            dest = self.rowCount()
        elif indicator in (
            QAbstractItemView.DropIndicatorPosition.BelowItem,
            QAbstractItemView.DropIndicatorPosition.OnViewport,
        ):
            dest += 1
        if dest == source or dest == source + 1:
            return
        self.row_dropped.emit(source, dest)


class LibraryTable(QTableWidget):
    """临时列表：媒体行可拖拽排序；分类头不可拖。"""

    row_dropped = Signal(int, int)
    _ROW_MIME = "application/x-kongchang-lib-row"

    def __init__(self) -> None:
        super().__init__(0, 3)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropOverwriteMode(False)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def _payload(self, row: int):
        item = self.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def mimeData(self, items):
        mime = super().mimeData(items)
        rows = {item.row() for item in items}
        if len(rows) != 1:
            return mime
        row = next(iter(rows))
        if isinstance(self._payload(row), Cue):
            mime.setData(self._ROW_MIME, str(row).encode("ascii"))
        return mime

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        if not mime.hasFormat(self._ROW_MIME):
            return
        source = int(bytes(mime.data(self._ROW_MIME)).decode("ascii"))
        if not isinstance(self._payload(source), Cue):
            return
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        dest = self.indexAt(pos).row()
        indicator = self.dropIndicatorPosition()
        if dest < 0:
            dest = self.rowCount()
        else:
            payload = self._payload(dest)
            on_header = isinstance(payload, tuple) and payload and payload[0] == LIB_HEADER
            if on_header and indicator in (
                QAbstractItemView.DropIndicatorPosition.OnItem,
                QAbstractItemView.DropIndicatorPosition.BelowItem,
            ):
                dest += 1
            elif indicator in (
                QAbstractItemView.DropIndicatorPosition.BelowItem,
                QAbstractItemView.DropIndicatorPosition.OnViewport,
            ):
                dest += 1
        if dest == 0 and self.rowCount() and isinstance(self._payload(0), tuple):
            dest = 1
        if dest == source or dest == source + 1:
            return
        self.row_dropped.emit(source, dest)


class CueRowDelegate(QStyledItemDelegate):
    """节目单行：正在播黄色，选中绿色。"""

    _MARK = {"playing": "▶", "paused": "❚", "preview": "●", "cover": "▣"}

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        if index.column() == 0:
            size.setWidth(max(size.width(), 56))
        return size

    def paint(self, painter, option, index) -> None:
        window = self.parent()
        if not isinstance(window, MainWindow):
            super().paint(painter, option, index)
            return
        t = window.theme
        row = index.row()
        col = index.column()
        cue = window.cue_at_row(row)
        live = window.live_state_for_row(row)
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        if live == "playing":
            bg, fg = (QColor(t["playing_sel"]) if selected else QColor(t["playing"])), QColor(t["playing_fg"])
            accent = QColor(t["playing_accent"])
        elif live:
            bg, fg = (QColor(t["paused_sel"]) if selected else QColor(t["paused"])), QColor(t["paused_fg"])
            accent = QColor(t["paused_accent"])
        elif selected:
            bg, fg = QColor(t["select"]), QColor(t["select_fg"])
            accent = QColor(t["go_hover"])
        elif cue is not None and cue.type == "note":
            bg, fg = QColor(t["note_bg"]), QColor(t["note_fg"])
            accent = None
        else:
            bg = QColor(t["table_alt"]) if row % 2 else QColor(t["table"])
            fg = QColor(t["fg"])
            accent = None
        painter.save()
        painter.fillRect(opt.rect, bg)
        if col == 0 and accent is not None:
            painter.fillRect(QRect(opt.rect.left(), opt.rect.top(), 4, opt.rect.height()), accent)
        type_color = {
            "audio": t["type_audio"],
            "video": t["type_video"],
            "note": t["type_note"],
        }
        if col == 1 and cue is not None and not live:
            painter.setPen(QColor(type_color.get(cue.type, t["fg"])))
        else:
            painter.setPen(fg)
        font = QFont(opt.font)
        if live:
            font.setBold(True)
        painter.setFont(font)
        if col == 0:
            mark = self._MARK.get(live or "", "")
            if mark:
                painter.drawText(
                    QRect(opt.rect.left() + 6, opt.rect.top(), 16, opt.rect.height()),
                    int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                    mark,
                )
            painter.drawText(
                opt.rect.adjusted(24, 0, -4, 0),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                str(row + 1),
            )
        elif col == 2 and cue is not None and window.media_missing(cue):
            align = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            tag = "  缺文件"
            fm = painter.fontMetrics()
            tag_w = fm.horizontalAdvance(tag)
            avail = max(20, opt.rect.width() - 14 - tag_w)
            shown = fm.elidedText(opt.text, Qt.TextElideMode.ElideRight, avail)
            painter.drawText(opt.rect.adjusted(8, 0, -6, 0), align, shown)
            painter.setPen(QColor(t["missing_live"] if live else t["missing"]))
            painter.drawText(opt.rect.adjusted(8 + fm.horizontalAdvance(shown), 0, -6, 0), align, tag)
        else:
            painter.drawText(
                opt.rect.adjusted(8, 0, -6, 0),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                opt.text,
            )
        painter.restore()


class LibraryItemDelegate(QStyledItemDelegate):
    """临时列表：样式贴近节目单（类型着色 / 播放高亮），分类行作分组标题。"""

    _MARK = {"playing": "▶", "paused": "❚", "preview": "●", "cover": "▣"}

    def sizeHint(self, option, index) -> QSize:
        payload = index.sibling(index.row(), 0).data(Qt.ItemDataRole.UserRole)
        if isinstance(payload, tuple) and payload and payload[0] == LIB_HEADER:
            return QSize(option.rect.width() or 80, 28)
        return QSize(option.rect.width() or 80, 42)

    def paint(self, painter, option, index) -> None:
        payload = index.sibling(index.row(), 0).data(Qt.ItemDataRole.UserRole)
        window = self.parent()
        t = window.theme if isinstance(window, MainWindow) else theme_colors("dark")
        painter.save()
        if isinstance(payload, tuple) and payload and payload[0] == LIB_HEADER:
            title = str(payload[1] if len(payload) > 1 else LIB_UNCATEGORIZED)
            painter.fillRect(option.rect, QColor(t.get("lib_cat_bg", t["panel"])))
            if index.column() == 0:
                key = "" if title == LIB_UNCATEGORIZED else title
                collapsed = isinstance(window, MainWindow) and key in window._collapsed_cats
                mark = "▸" if collapsed else "▾"
                font = QFont(option.font)
                font.setBold(True)
                font.setPointSize(max(9, font.pointSize() - 1))
                painter.setFont(font)
                painter.setPen(QColor(t.get("lib_cat_fg", t["note_fg"])))
                text = f"{mark} {title}"
                elided = painter.fontMetrics().elidedText(
                    text, Qt.TextElideMode.ElideRight, max(20, option.rect.width() - 14)
                )
                painter.drawText(
                    option.rect.adjusted(8, 0, -6, 0),
                    int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                    elided,
                )
            painter.restore()
            return

        cue = payload if isinstance(payload, Cue) else None
        live = ""
        if isinstance(window, MainWindow) and cue is not None:
            live = window.controller.library_live_map().get(cue.id, "")
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        col = index.column()
        if live == "playing":
            bg, fg = (QColor(t["playing_sel"]) if selected else QColor(t["playing"])), QColor(t["playing_fg"])
            accent = QColor(t["playing_accent"])
        elif live:
            bg, fg = (QColor(t["paused_sel"]) if selected else QColor(t["paused"])), QColor(t["paused_fg"])
            accent = QColor(t["paused_accent"])
        elif selected:
            bg, fg = QColor(t["select"]), QColor(t["select_fg"])
            accent = QColor(t["go_hover"])
        else:
            row = index.row()
            bg = QColor(t["table_alt"]) if row % 2 else QColor(t["table"])
            fg = QColor(t["fg"])
            accent = None
        painter.fillRect(option.rect, bg)
        if col == 0 and accent is not None:
            painter.fillRect(QRect(option.rect.left(), option.rect.top(), 4, option.rect.height()), accent)
        type_color = {"audio": t["type_audio"], "video": t["type_video"], "note": t["type_note"]}
        font = QFont(option.font)
        if live:
            font.setBold(True)
        painter.setFont(font)
        align = int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        text = str(index.data() or "")
        if col == 0 and cue is not None and not live:
            painter.setPen(QColor(type_color.get(cue.type, t["fg"])))
        else:
            painter.setPen(fg)
        if col == 0:
            mark = self._MARK.get(live or "", "")
            left = 8
            if mark:
                painter.drawText(
                    QRect(option.rect.left() + 6, option.rect.top(), 16, option.rect.height()),
                    align,
                    mark,
                )
                left = 24
            painter.drawText(option.rect.adjusted(left, 0, -4, 0), align, text)
        elif col == 1 and cue is not None and isinstance(window, MainWindow) and window.media_missing(cue):
            tag = "  缺文件"
            fm = painter.fontMetrics()
            tag_w = fm.horizontalAdvance(tag)
            shown = fm.elidedText(text, Qt.TextElideMode.ElideRight, max(20, option.rect.width() - 14 - tag_w))
            painter.drawText(option.rect.adjusted(8, 0, -6, 0), align, shown)
            painter.setPen(QColor(t["missing_live"] if live else t["missing"]))
            painter.drawText(option.rect.adjusted(8 + fm.horizontalAdvance(shown), 0, -6, 0), align, tag)
        else:
            elided = painter.fontMetrics().elidedText(
                text, Qt.TextElideMode.ElideRight, max(20, option.rect.width() - 14)
            )
            painter.drawText(option.rect.adjusted(8, 0, -6, 0), align, elided)
        painter.restore()


class ScreenCombo(QComboBox):
    """现场下拉不能被滚轮误切投影屏。"""

    def wheelEvent(self, event) -> None:
        event.ignore()


class SeekBar(QProgressBar):
    seeked = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        self.mark_in = 0.0
        self.mark_out = 0.0
        self._dragging = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("拖动或点击跳转进度")

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.mark_in <= 0 and self.mark_out <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w = max(1, self.width())
        h = self.height()
        if self.mark_in > 0:
            painter.setPen(QPen(QColor("#f0b429"), 2))
            x = max(1, min(w - 2, int(self.mark_in * w)))
            painter.drawLine(x, 1, x, h - 2)
        if self.mark_out > 0:
            painter.setPen(QPen(QColor("#ef5555"), 2))
            x = max(1, min(w - 2, int(self.mark_out * w)))
            painter.drawLine(x, 1, x, h - 2)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._dragging = True
            self._emit_ratio(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            self._emit_ratio(event)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._emit_ratio(event)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _emit_ratio(self, event: QMouseEvent) -> None:
        width = max(1, self.width())
        x = event.position().x() if hasattr(event, "position") else event.x()
        self.seeked.emit(max(0.0, min(1.0, float(x) / width)))


class VolumeSlider(QSlider):
    def wheelEvent(self, event) -> None:
        if self.hasFocus():
            super().wheelEvent(event)
            return
        event.ignore()


class MainWindow(QMainWindow):
    mpv_script_message = Signal(object)
    fade_finished = Signal()

    def __init__(self, project_path: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"简易控场  v{__version__}")
        self.resize(1280, 800)
        assets = Path(__file__).resolve().parents[2] / "assets"
        icon_path = assets / "app_v3.ico"
        if not icon_path.exists():
            icon_path = assets / "app.ico"
        if not icon_path.exists():
            icon_path = assets / "app_v3.png"
        if not icon_path.exists():
            icon_path = assets / "app.png"
        if icon_path.exists():
            from PySide6.QtGui import QIcon

            self.setWindowIcon(QIcon(str(icon_path)))
        self.settings = AppSettings.load()
        self.project = Project()
        self._open_startup_project(project_path)
        self.controller = ShowController()
        self.mpv_script_message.connect(self._on_mpv_script_message)
        self.controller.on_client_message = self.mpv_script_message.emit
        self.fade_finished.connect(self._finish_fade)
        self.controller.on_fade_done = self.fade_finished.emit
        self._filling = False
        self._cues_locked = False
        self._missing_cache: dict[str, tuple[float, bool]] = {}
        self._collapsed_cats: set[str] = set()
        self._undo_stack: list[str] = []
        self._redo_stack: list[str] = []
        self._undoing = False
        self._force_closing = False
        self._seeking = False
        self._library_seeking = False
        self._library_seeking_audio = False
        self._library_seeking_video = False
        self._volume_user = False
        self._library_volume_user = False
        self._layout_ready = False
        self._focus = "cues"
        self._live_sig: tuple = (None, "", None, "", None, "")
        self._library_eof_handled: str | None = None
        self._library_eof_audio: str | None = None
        self._library_eof_video: str | None = None
        self._library_filter = ""
        self._show_mode = False
        self._show_t0: float | None = None
        self._edit_split_sizes: list[int] = []
        self.controller.output_volume = float(self.settings.output_volume)
        self.controller.library_volume = float(self.settings.library_volume)
        self._restore_window_geometry()
        self._apply_player_config()
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(1500)
        self._autosave_timer.timeout.connect(self._autosave_now)
        self.project.on_dirty = self._schedule_autosave
        if self.project.dirty:
            self._schedule_autosave()
        self._layout_timer = QTimer(self)
        self._layout_timer.setSingleShot(True)
        self._layout_timer.setInterval(400)
        self._layout_timer.timeout.connect(self._persist_layout)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)

        self._build_menu()
        app = QGuiApplication.instance()
        if app is not None:
            app.screenAdded.connect(self._reload_projection_combo)
            app.screenRemoved.connect(self._reload_projection_combo)
        # 窗口拖到另一块屏时，刷新「本软件」标记
        if hasattr(self, "screenChanged"):
            self.screenChanged.connect(lambda *_: self._reload_projection_combo())
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_add_bar())

        split = QSplitter(Qt.Orientation.Horizontal)
        self.main_split = split
        split.addWidget(self._build_table())
        self.inspector_panel = self._build_inspector()
        split.addWidget(self.inspector_panel)
        split.addWidget(self._build_library())
        split.setStretchFactor(0, 6)
        split.setStretchFactor(1, 3)
        split.setStretchFactor(2, 2)
        split.splitterMoved.connect(lambda *_: self._layout_timer.start())
        layout.addWidget(split, 1)
        layout.addWidget(self._build_now_next())
        layout.addWidget(self._build_transport())
        self.status_label = QLabel()
        self.status_label.setObjectName("status")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        self._apply_theme()

        self._fade_timer = QTimer(self)
        self._fade_timer.timeout.connect(self._on_fade_tick)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh_status)
        self.timer.start(400)
        self.reload_table()
        self._refresh_status()
        QTimer.singleShot(0, self._restore_splitters)
        QTimer.singleShot(400, self._warm_players)
        QTimer.singleShot(800, self._maybe_create_desktop_shortcut)
        QTimer.singleShot(0, self._rebuild_audio_menu)
        if self.settings.show_mode:
            QTimer.singleShot(0, lambda: self._set_show_mode(True, persist=False))

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._editing_text():
            super().keyPressEvent(event)
            return
        library = getattr(self, "_focus", "cues") == "library"
        if event.key() == Qt.Key.Key_Space:
            if library:
                self.on_library_play()
            else:
                self.on_go()
            return
        if event.key() in (Qt.Key.Key_P, Qt.Key.Key_Pause):
            if library:
                self.on_library_pause()
            else:
                self.on_pause()
            return
        if event.key() == Qt.Key.Key_M:
            self.on_toggle_mute()
            return
        if event.key() == Qt.Key.Key_B:
            self.on_toggle_hold()
            return
        if event.key() == Qt.Key.Key_D:
            self.on_toggle_duck()
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Z:
            self.on_undo()
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Y:
            self.on_redo()
            return
        if event.key() == Qt.Key.Key_Left:
            if library:
                self.controller.seek_library_relative(-5)
            else:
                self.controller.seek_relative(-5)
            return
        if event.key() == Qt.Key.Key_Right:
            if library:
                self.controller.seek_library_relative(5)
            else:
                self.controller.seek_relative(5)
            return
        if event.key() == Qt.Key.Key_Up:
            if library:
                self._apply_library_volume(self.controller.nudge_library_volume(5))
            else:
                self._apply_volume(self.controller.nudge_volume(5))
            return
        if event.key() == Qt.Key.Key_Down:
            if library:
                self._apply_library_volume(self.controller.nudge_library_volume(-5))
            else:
                self._apply_volume(self.controller.nudge_volume(-5))
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_Escape:
            self.on_panic()
            return
        if event.key() == Qt.Key.Key_F11:
            self._toggle_show_mode()
            return
        if self._show_mode and event.key() in (
            Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4, Qt.Key.Key_5,
            Qt.Key.Key_6, Qt.Key.Key_7, Qt.Key.Key_8, Qt.Key.Key_9,
        ):
            self._fire_library_hotkey(int(event.text() or "0"))
            return
        if event.key() == Qt.Key.Key_Escape:
            if library:
                self.on_library_stop()
                return
            self.on_panic()
            return
        super().keyPressEvent(event)

    @property
    def theme(self) -> dict[str, str]:
        return theme_colors(self.settings.theme)

    def _set_theme(self, name: str) -> None:
        next_theme = "light" if name == "light" else "dark"
        if self.settings.theme == next_theme:
            self._sync_theme_menu()
            return
        self.settings.theme = next_theme
        self.settings.save()
        self._apply_theme()

    def _apply_theme(self) -> None:
        self.setStyleSheet(stylesheet(self.settings.theme))
        self._sync_theme_menu()
        if hasattr(self, "table"):
            self._apply_list_palette(self.table)
            self.table.viewport().update()
        for widget in self._library_lists():
            self._apply_list_palette(widget)
            widget.viewport().update()
        combo = getattr(self, "screen_combo", None)
        if combo is not None:
            combo.style().unpolish(combo)
            combo.style().polish(combo)
        if hasattr(self, "now_title"):
            self._update_now_next(None)
        if hasattr(self, "go_btn"):
            self._refresh_transport_labels(self.active_cue())
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
        self._update_proj_warn()

    def _sync_theme_menu(self) -> None:
        light = self.settings.theme == "light"
        dark_act = getattr(self, "theme_dark_act", None)
        light_act = getattr(self, "theme_light_act", None)
        if dark_act is None or light_act is None:
            return
        dark_act.blockSignals(True)
        light_act.blockSignals(True)
        dark_act.setChecked(not light)
        light_act.setChecked(light)
        dark_act.blockSignals(False)
        light_act.blockSignals(False)

    def _apply_list_palette(self, widget: QTableWidget) -> None:
        t = self.theme
        palette = widget.palette()
        bg = QColor(t["table"])
        fg = QColor(t["fg"])
        hi = QColor(t["select"])
        hit = QColor(t["select_fg"])
        for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
            palette.setColor(group, widget.backgroundRole(), bg)
            palette.setColor(group, widget.foregroundRole(), fg)
            palette.setColor(group, QPalette.ColorRole.Base, bg)
            palette.setColor(group, QPalette.ColorRole.Text, fg)
            palette.setColor(group, QPalette.ColorRole.Highlight, hi)
            palette.setColor(group, QPalette.ColorRole.HighlightedText, hit)
        widget.setPalette(palette)

    def _build_menu(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("工程")
        new_act = file_menu.addAction("新建…", self.on_new_project)
        new_act.setShortcut("Ctrl+N")
        open_act = file_menu.addAction("打开 / 导入…", self.on_open_project)
        open_act.setShortcut("Ctrl+O")
        save_act = file_menu.addAction("保存", self.on_save_project)
        save_act.setShortcut("Ctrl+S")
        file_menu.addAction("另存为…", self.on_save_project_as)
        self.recent_menu = file_menu.addMenu("最近打开")
        file_menu.addSeparator()
        check_act = file_menu.addAction("检查媒体…", self.on_check_media)
        check_act.setShortcut("Ctrl+K")
        file_menu.addAction("设置封面图…", self.on_set_cover)
        undo_act = file_menu.addAction("撤销", self.on_undo)
        undo_act.setShortcut("Ctrl+Z")
        redo_act = file_menu.addAction("重做", self.on_redo)
        redo_act.setShortcut("Ctrl+Y")
        self.lock_act = file_menu.addAction("锁定节目单")
        self.lock_act.setCheckable(True)
        self.lock_act.setShortcut("Ctrl+L")
        self.lock_act.setToolTip("勾选后不能改节目单顺序和条目，仍可播放。")
        self.lock_act.triggered.connect(self._toggle_cues_lock)
        self.show_mode_act = file_menu.addAction("演出模式")
        self.show_mode_act.setCheckable(True)
        self.show_mode_act.setShortcut("F11")
        self.show_mode_act.triggered.connect(self._toggle_show_mode)
        file_menu.addAction("打开演出日志", self.on_open_show_log)
        file_menu.addAction("创建桌面快捷方式", self.on_create_shortcut)
        self.audio_menu = bar.addMenu("音频输出")
        file_menu.addSeparator()
        file_menu.addAction("退出", self.close)
        self._refresh_recent_menu()

        theme_menu = bar.addMenu("主题")
        group = QActionGroup(self)
        group.setExclusive(True)
        self.theme_dark_act = theme_menu.addAction("黑色")
        self.theme_light_act = theme_menu.addAction("白色")
        for act, name in ((self.theme_dark_act, "dark"), (self.theme_light_act, "light")):
            act.setCheckable(True)
            group.addAction(act)
            act.triggered.connect(lambda checked=False, n=name: self._set_theme(n))
        self._sync_theme_menu()

        help_menu = bar.addMenu("帮助")
        guide_act = help_menu.addAction("使用说明", self.on_help)
        guide_act.setShortcut("F1")
        help_menu.addAction("快捷键", lambda: self.on_help("keys"))
        help_menu.addAction("检查更新", self.on_check_update)
        help_menu.addSeparator()
        help_menu.addAction("关于", self.on_about)

        host = QWidget(bar)
        self._proj_host = host
        host.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        row = QHBoxLayout(host)
        row.setContentsMargins(8, 2, 10, 2)
        row.setSpacing(6)
        label = QLabel("全屏投影到")
        label.setObjectName("projLabel")
        self.screen_combo = ScreenCombo()
        self.screen_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.screen_combo.setMaximumWidth(200)
        self.screen_combo.activated.connect(self._on_projection_chosen)
        row.addWidget(label)
        row.addWidget(self.screen_combo)
        bar.setCornerWidget(host, Qt.Corner.TopRightCorner)
        host.show()
        self._reload_projection_combo()

    def _reload_projection_combo(self, *_args) -> None:
        combo = getattr(self, "screen_combo", None)
        if combo is None:
            return
        displays = list_windows_displays()
        preview = self._preview_screen_index()
        self._proj_preview_idx = preview
        multi = len(displays) > 1
        saved_device = (self.settings.projection_device or "").strip()
        saved_index = self.settings.projection_screen
        combo.blockSignals(True)
        combo.clear()
        pick = -1
        for item in displays:
            combo.addItem(self._projection_choice_label(item, preview, multi), (item.index, item.device))
            tip = f"{item.short_device}  {item.width}x{item.height}"
            if item.primary:
                tip += "  主屏"
            combo.setItemData(combo.count() - 1, tip, Qt.ItemDataRole.ToolTipRole)
            if saved_device and item.device == saved_device:
                pick = combo.count() - 1
            elif pick < 0 and not saved_device and item.index == saved_index:
                pick = combo.count() - 1
        if pick < 0 and saved_device:
            combo.addItem(
                f"屏幕{saved_index + 1}（未连接）",
                (saved_index, saved_device),
            )
            pick = combo.count() - 1
        if pick < 0 and combo.count():
            pick = 0
        if pick >= 0:
            combo.setCurrentIndex(pick)
        combo.blockSignals(False)
        data = combo.currentData()
        if data:
            index, device = data
            live = any(item.device == device for item in displays)
            if live:
                self.settings.set_projection(index, device)
        self._apply_player_config()
        self._update_proj_warn()

    def _on_projection_chosen(self, _index: int) -> None:
        data = self.screen_combo.currentData()
        if not data:
            return
        index, device = data
        self.settings.set_projection(index, device)
        self._apply_player_config()
        if self.controller.video_on_stage:
            try:
                self.controller._go_fullscreen()
            except Exception:
                pass
        self._update_proj_warn()
        self.table.setFocus()

    def _projection_choice_label(self, item, preview: int, multi: bool) -> str:
        # 带上 DISPLAY 名，方便核对「本软件」是否标对
        base = f"屏幕{item.index + 1}·{item.short_device}"
        if not item.connected:
            tag = "未连接"
        elif preview is not None and item.index == preview:
            tag = "本软件"
        elif multi:
            tag = "推荐"
        else:
            tag = "主屏" if item.primary else ""
        if tag:
            return f"{base}（{tag}）"
        return base

    def _update_proj_warn(self) -> None:
        combo = getattr(self, "screen_combo", None)
        if combo is None:
            return
        preview = self._preview_screen_index()
        if getattr(self, "_proj_preview_idx", None) != preview:
            self._reload_projection_combo()
            return
        covers = self.settings.projection_screen == preview
        combo.setProperty("covers", "true" if covers else "false")
        combo.style().unpolish(combo)
        combo.style().polish(combo)
        if covers:
            combo.setToolTip(
                "当前选的是控场窗口所在屏（本软件），全屏会盖住操作台。\n"
                "请改选标「推荐」的另一块屏。"
            )
        else:
            combo.setToolTip(
                "全屏视频投到所选屏幕。\n"
                "标「本软件」的是操作台所在屏，不要选；选「推荐」那块。"
            )

    def _build_add_bar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 8, 10, 8)
        self._cue_edit_btns: list[QPushButton] = []
        for text, handler in (
            ("+ 音频", lambda: self.add_media("audio")),
            ("+ 视频", lambda: self.add_media("video")),
            ("+ 备注", self.add_note),
        ):
            btn = QPushButton(text)
            btn.setObjectName("addBtn")
            btn.clicked.connect(handler)
            row.addWidget(btn)
            self._cue_edit_btns.append(btn)
        row.addSpacing(16)
        delete = QPushButton("删除")
        delete.clicked.connect(self.delete_cue)
        row.addWidget(delete)
        self._cue_edit_btns.append(delete)
        row.addStretch(1)
        self.project_label = QLabel("未打开工程")
        self.project_label.setObjectName("hint")
        row.addWidget(self.project_label)
        return bar

    def _build_now_next(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("nowNext")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 8, 10, 8)
        row.setSpacing(10)

        now = QFrame()
        now.setObjectName("nowCard")
        self.now_card = now
        now_box = QVBoxLayout(now)
        now_box.setContentsMargins(12, 8, 12, 8)
        now_box.setSpacing(2)
        self.now_kicker = QLabel("选中")
        self.now_kicker.setObjectName("nowKicker")
        self.now_title = QLabel("—")
        self.now_title.setObjectName("nowTitle")
        self.now_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.now_notes = QLabel("")
        self.now_notes.setObjectName("nowNotes")
        self.now_notes.setWordWrap(True)
        self.now_notes.setMinimumHeight(44)
        self.now_notes.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.now_remain = QLabel("")
        self.now_remain.setObjectName("nowRemain")
        now_box.addWidget(self.now_kicker)
        now_box.addWidget(self.now_title)
        now_box.addWidget(self.now_remain)
        now_box.addWidget(self.now_notes)

        nxt = QFrame()
        nxt.setObjectName("nextCard")
        self.next_card = nxt
        nxt_box = QVBoxLayout(nxt)
        nxt_box.setContentsMargins(12, 8, 12, 8)
        nxt_box.setSpacing(2)
        self.next_kicker = QLabel("下一条")
        self.next_kicker.setObjectName("nextKicker")
        self.next_title = QLabel("—")
        self.next_title.setObjectName("nextTitle")
        self.next_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.next_notes = QLabel("")
        self.next_notes.setObjectName("nowNotes")
        self.next_notes.setWordWrap(True)
        nxt_box.addWidget(self.next_kicker)
        nxt_box.addWidget(self.next_title)
        nxt_box.addWidget(self.next_notes)

        side = QVBoxLayout()
        side.setSpacing(4)
        self.show_clock = QPushButton("未开演")
        self.show_clock.setObjectName("showClock")
        self.show_clock.setFlat(True)
        self.show_clock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.show_clock.setToolTip("第一次播放后开始计时，点击复位")
        self.show_clock.clicked.connect(self._reset_show_clock)
        self.proj_status = QLabel("无画面")
        self.proj_status.setObjectName("projStatus")
        self.proj_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.show_vu = QProgressBar()
        self.show_vu.setObjectName("vuBar")
        self.show_vu.setRange(0, 100)
        self.show_vu.setValue(0)
        self.show_vu.setTextVisible(False)
        self.show_vu.setFixedWidth(88)
        self.show_vu.setFixedHeight(10)
        self.show_vu.setToolTip("节目单有声时的音量示意，不是精确分贝")
        self.lib_vu = QProgressBar()
        self.lib_vu.setObjectName("vuBar")
        self.lib_vu.setRange(0, 100)
        self.lib_vu.setValue(0)
        self.lib_vu.setTextVisible(False)
        self.lib_vu.setFixedWidth(88)
        self.lib_vu.setFixedHeight(10)
        self.lib_vu.setToolTip("素材库有声时的音量示意，不是精确分贝")
        vu_kicker = QLabel("电平")
        vu_kicker.setObjectName("vuKicker")
        show_vu_lab = QLabel("节目单")
        show_vu_lab.setObjectName("vuLabel")
        lib_vu_lab = QLabel("素材库")
        lib_vu_lab.setObjectName("vuLabel")
        side.addWidget(self.show_clock)
        side.addWidget(self.proj_status)
        side.addStretch(1)
        side.addWidget(vu_kicker)
        side.addWidget(show_vu_lab)
        side.addWidget(self.show_vu)
        side.addWidget(lib_vu_lab)
        side.addWidget(self.lib_vu)

        row.addWidget(now, 3)
        row.addWidget(nxt, 2)
        row.addLayout(side, 0)
        return bar

    def _build_table(self) -> QTableWidget:
        self.table = CueTable()
        self.table.setHorizontalHeaderLabels(["#", "类型", "名称", "备注", "路径"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 56)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(2, 220)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self.table.setColumnHidden(4, True)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setItemDelegate(CueRowDelegate(self))
        self.table.cellClicked.connect(self.on_row_clicked)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.row_dropped.connect(self.on_row_dropped)
        self.table.arrow_pressed.connect(self.on_table_arrow)
        return self.table

    def _build_inspector(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("inspector")
        box = QVBoxLayout(panel)
        title = QLabel("编辑选中")
        title.setObjectName("secTitle")
        box.addWidget(title)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("名称")
        # 分类：同一行「分类 | 下拉(只选) | 编辑 | +」，仅选中临时音频时显示
        self.category_row = QWidget()
        cat_row = QHBoxLayout(self.category_row)
        cat_row.setContentsMargins(0, 0, 0, 0)
        cat_row.setSpacing(6)
        self.category_label = QLabel("分类")
        self.category_label.setFixedWidth(36)
        self.category_edit = QComboBox()
        self.category_edit.setObjectName("categoryCombo")
        self.category_edit.setEditable(False)
        self.category_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.category_edit.setMaxVisibleItems(16)
        self.category_edit.setMinimumContentsLength(8)
        self.category_edit.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.category_edit_btn = QPushButton("编辑")
        self.category_edit_btn.setObjectName("addBtn")
        self.category_edit_btn.setFixedHeight(28)
        self.category_edit_btn.setToolTip("修改当前分类名称")
        self.category_edit_btn.clicked.connect(self.edit_library_category)
        self.category_add_btn = QPushButton("+")
        self.category_add_btn.setObjectName("addBtn")
        self.category_add_btn.setFixedSize(36, 28)
        self.category_add_btn.setToolTip("新建分类")
        self.category_add_btn.clicked.connect(self.add_library_category)
        cat_row.addWidget(self.category_label)
        cat_row.addWidget(self.category_edit, 1)
        cat_row.addWidget(self.category_edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        cat_row.addWidget(self.category_add_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("备注 / 现场口令")
        self.notes_edit.setFixedHeight(150)
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        browse = QPushButton("浏览媒体…")
        browse.clicked.connect(self.browse_media)
        self.loop_check = QCheckBox("音频循环")
        self.name_edit.editingFinished.connect(self.apply_inspector)
        self.notes_edit.textChanged.connect(self.apply_inspector)
        self.loop_check.toggled.connect(self.apply_inspector)
        # 下拉只负责选择，不和编辑混用
        self.category_edit.activated.connect(self._commit_library_category)
        box.addWidget(QLabel("名称"))
        box.addWidget(self.name_edit)
        box.addWidget(self.category_row)
        box.addWidget(QLabel("备注"))
        box.addWidget(self.notes_edit)
        box.addWidget(QLabel("媒体路径（相对工程目录）"))
        box.addWidget(self.path_edit)
        box.addWidget(browse)
        box.addWidget(self.loop_check)
        self.trim_toggle = QCheckBox("高级（一般不用）")
        self.trim_toggle.setToolTip("裁掉片头片尾、开头渐强、停止时渐弱。不勾选则整段播放。")
        self.trim_row = QWidget()
        trim = QVBoxLayout(self.trim_row)
        trim.setContentsMargins(0, 0, 0, 0)
        trim.setSpacing(4)
        explain = QLabel("从第几秒起播 / 播到第几秒停；渐强、渐弱是开头和停止时音量慢慢变化的秒数。填 0 表示不裁、用默认渐停。")
        explain.setObjectName("hint")
        explain.setWordWrap(True)
        trim.addWidget(explain)
        spin_row = QHBoxLayout()
        spin_row.setSpacing(6)
        self.trim_in_spin = QDoubleSpinBox()
        self.trim_out_spin = QDoubleSpinBox()
        self.fade_in_spin = QDoubleSpinBox()
        self.fade_out_spin = QDoubleSpinBox()
        for spin, label, tip in (
            (self.trim_in_spin, "从第几秒起", "0 = 从头播"),
            (self.trim_out_spin, "播到第几秒", "0 = 播到文件结束"),
            (self.fade_in_spin, "开头渐强", "0 = 用软件默认"),
            (self.fade_out_spin, "停止渐弱", "0 = 约 1.6 秒渐停"),
        ):
            spin.setRange(0, 36000)
            spin.setDecimals(1)
            spin.setSingleStep(0.5)
            spin.setSuffix(" 秒")
            spin.setSpecialValueText("不裁" if "第几秒" in label else "默认")
            spin.setToolTip(tip)
            spin.valueChanged.connect(self.apply_inspector)
            col = QVBoxLayout()
            tag = QLabel(label)
            tag.setObjectName("hint")
            col.addWidget(tag)
            col.addWidget(spin)
            spin_row.addLayout(col)
        trim.addLayout(spin_row)
        self.trim_row.setVisible(False)
        self.trim_toggle.toggled.connect(self.trim_row.setVisible)
        box.addWidget(self.trim_toggle)
        box.addWidget(self.trim_row)
        box.addStretch(1)
        # 默认隐藏：仅选中右侧临时媒体时再显示
        self.category_row.setVisible(False)
        return panel

    def _make_library_list(self) -> QTableWidget:
        widget = LibraryTable()
        widget.setObjectName("libraryList")
        widget.setHorizontalHeaderLabels(["类型", "名称", "备注"])
        widget.verticalHeader().setVisible(False)
        widget.setAlternatingRowColors(True)
        widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        widget.setShowGrid(False)
        widget.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        header = widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(1, 140)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setHighlightSections(False)
        widget.setItemDelegate(LibraryItemDelegate(self))
        widget.cellClicked.connect(lambda *_: self._on_library_selected("audio"))
        widget.itemSelectionChanged.connect(lambda: self._on_library_selected("audio"))
        widget.row_dropped.connect(self.on_library_row_dropped)
        widget.verticalHeader().setDefaultSectionSize(42)
        return widget

    def _build_library(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("library")
        box = QVBoxLayout(panel)
        box.setContentsMargins(10, 10, 10, 10)
        box.setSpacing(8)
        title = QLabel("素材库")
        title.setObjectName("secTitle")
        box.addWidget(title)
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("搜索名称 / 备注 / 分类")
        self.library_search.setClearButtonEnabled(True)
        self.library_search.textChanged.connect(self._on_library_filter)
        box.addWidget(self.library_search)
        self.library_audio_list = self._make_library_list()
        self._library_focus = "audio"
        self._library_default_category = ""
        add_row = QHBoxLayout()
        add_row.setSpacing(6)
        add_audio = QPushButton("+ 音频")
        add_audio.setObjectName("addBtn")
        add_audio.clicked.connect(lambda: self.add_library_media("audio"))
        add_video = QPushButton("+ 视频")
        add_video.setObjectName("addBtn")
        add_video.clicked.connect(lambda: self.add_library_media("video"))
        add_row.addWidget(add_audio)
        add_row.addWidget(add_video)
        add_row.addStretch(1)
        box.addLayout(add_row)
        box.addWidget(self.library_audio_list, 1)
        bed = QFrame()
        bed.setObjectName("libraryBed")
        bed_col = QVBoxLayout(bed)
        bed_col.setContentsMargins(0, 4, 0, 0)
        bed_col.setSpacing(4)
        self.library_audio_now = QLabel("素材库：未播放")
        self.library_audio_now.setObjectName("hint")
        self.library_audio_now.setWordWrap(True)
        bed_col.addWidget(self.library_audio_now)
        self.library_audio_bar, self.library_audio_time, audio_prog = self._make_lib_seek_row("音频")
        self.library_audio_bar.seeked.connect(self._on_library_audio_seek)
        self.library_audio_row = QWidget()
        audio_wrap = QVBoxLayout(self.library_audio_row)
        audio_wrap.setContentsMargins(0, 0, 0, 0)
        audio_wrap.setSpacing(0)
        audio_wrap.addLayout(audio_prog)
        self.library_audio_row.setVisible(False)
        self.library_video_bar, self.library_video_time, video_prog = self._make_lib_seek_row("视频")
        self.library_video_bar.seeked.connect(self._on_library_video_seek)
        self.library_video_row = QWidget()
        video_wrap = QVBoxLayout(self.library_video_row)
        video_wrap.setContentsMargins(0, 0, 0, 0)
        video_wrap.setSpacing(0)
        video_wrap.addLayout(video_prog)
        self.library_video_row.setVisible(False)
        seek_stack = QVBoxLayout()
        seek_stack.setContentsMargins(0, 0, 0, 0)
        seek_stack.setSpacing(4)
        seek_stack.addWidget(self.library_audio_row)
        seek_stack.addWidget(self.library_video_row)
        self.library_volume_label = QLabel(f"音量 {int(self.controller.library_volume)}")
        self.library_volume_label.setObjectName("volumeLabel")
        self.library_volume_slider = VolumeSlider(Qt.Orientation.Horizontal)
        self.library_volume_slider.setObjectName("volumeSlider")
        self.library_volume_slider.setRange(0, 100)
        self.library_volume_slider.blockSignals(True)
        self.library_volume_slider.setValue(int(self.controller.library_volume))
        self.library_volume_slider.blockSignals(False)
        self.library_volume_slider.setMinimumWidth(90)
        self.library_volume_slider.setMaximumWidth(120)
        self.library_volume_slider.setToolTip("素材库音量（与底栏独立）")
        self.library_volume_slider.valueChanged.connect(self._on_library_volume_changed)
        self.library_vol_row = QWidget()
        vol_wrap = QVBoxLayout(self.library_vol_row)
        vol_wrap.setContentsMargins(8, 0, 0, 0)
        vol_wrap.setSpacing(2)
        vol_wrap.addWidget(self.library_volume_label)
        vol_wrap.addWidget(self.library_volume_slider)
        vol_wrap.addStretch(1)
        self.library_vol_row.setFixedWidth(120)
        self.library_vol_row.setVisible(False)
        seek_pair = QHBoxLayout()
        seek_pair.setContentsMargins(0, 0, 0, 0)
        seek_pair.setSpacing(0)
        seek_pair.addLayout(seek_stack, 1)
        seek_pair.addWidget(self.library_vol_row, 0)
        bed_col.addLayout(seek_pair)
        # 与底栏一致：播放 → 停止 → 暂停 → 全屏 → 收起全屏
        bed_btns = QHBoxLayout()
        bed_btns.setSpacing(6)
        self.library_audio_play = QPushButton("播放")
        self.library_audio_play.setObjectName("libGoBtn")
        self.library_audio_stop = QPushButton("停止")
        self.library_audio_stop.setObjectName("libStopBtn")
        self.library_audio_pause = QPushButton("暂停")
        self.library_audio_pause.setObjectName("libPauseBtn")
        self.library_stage_btn = QPushButton("全屏")
        self.library_stage_btn.setObjectName("libStageBtn")
        self.library_unstage_btn = QPushButton("收起全屏")
        self.library_unstage_btn.setObjectName("libUnstageBtn")
        for btn in (
            self.library_audio_play,
            self.library_audio_stop,
            self.library_audio_pause,
            self.library_stage_btn,
            self.library_unstage_btn,
        ):
            btn.setFixedHeight(36)
            bed_btns.addWidget(btn, 1)
        self.library_audio_play.clicked.connect(self.on_library_play)
        self.library_audio_stop.clicked.connect(self.on_library_stop)
        self.library_audio_pause.clicked.connect(self.on_library_pause)
        self.library_stage_btn.clicked.connect(self.on_library_stage)
        self.library_unstage_btn.clicked.connect(self.on_library_unstage)
        bed_col.addLayout(bed_btns)
        split_row = QHBoxLayout()
        split_row.setSpacing(6)
        self.library_stop_bed_btn = QPushButton("停音频")
        self.library_stop_bed_btn.setObjectName("libStopSplitBtn")
        self.library_stop_bed_btn.setToolTip("只停素材库音频，视频继续（并恢复视频声）")
        self.library_stop_video_btn = QPushButton("停视频")
        self.library_stop_video_btn.setObjectName("libStopSplitBtn")
        self.library_stop_video_btn.setToolTip("只停素材库视频，音频继续")
        self.library_stop_bed_btn.setFixedHeight(28)
        self.library_stop_video_btn.setFixedHeight(28)
        self.library_stop_bed_btn.clicked.connect(self.on_library_stop_bed)
        self.library_stop_video_btn.clicked.connect(self.on_library_stop_video)
        split_row.addWidget(self.library_stop_bed_btn, 1)
        split_row.addWidget(self.library_stop_video_btn, 1)
        bed_col.addLayout(split_row)
        box.addWidget(bed)
        hint = QLabel("点另一条视频即切播。素材库音频与节目单音频互斥；可叠在无声视频上。分类：默认 / 单曲 / 顺序 / 列表。")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        box.addWidget(hint)
        return panel

    def _make_lib_seek_row(self, tag: str) -> tuple[SeekBar, QLabel, QHBoxLayout]:
        row = QHBoxLayout()
        row.setSpacing(6)
        name = QLabel(tag)
        name.setObjectName("libSeekTag")
        name.setFixedWidth(36)
        bar = SeekBar()
        bar.setObjectName("mediaProgress")
        bar.setRange(0, 1000)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setEnabled(False)
        bar.setFixedHeight(14)
        bar.setToolTip(f"拖动{tag}进度")
        clock = QLabel("--:-- / --:--")
        clock.setObjectName("libSeekTime")
        clock.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        clock.setFixedWidth(92)
        row.addWidget(name)
        row.addWidget(bar, 1)
        row.addWidget(clock)
        return bar, clock, row

    def _build_transport(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("transport")
        box = QVBoxLayout(bar)
        box.setContentsMargins(12, 10, 12, 12)
        box.setSpacing(8)
        prog = QHBoxLayout()
        prog.setSpacing(12)
        self.progress_bar = SeekBar()
        self.progress_bar.setObjectName("mediaProgress")
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setEnabled(False)
        self.progress_bar.seeked.connect(self._on_seek)
        self.progress_time = QLabel("--:-- / --:--")
        self.progress_time.setObjectName("progressTime")
        self.volume_label = QLabel("音量 100")
        self.volume_label.setObjectName("volumeLabel")
        self.volume_slider = VolumeSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.blockSignals(True)
        self.volume_slider.setValue(int(self.controller.output_volume))
        self.volume_slider.blockSignals(False)
        self.volume_slider.setMinimumWidth(120)
        self.volume_slider.setMaximumWidth(180)
        self.volume_slider.setToolTip("输出音量，本机记住")
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        prog.addWidget(self.progress_bar, 1)
        prog.addWidget(self.progress_time)
        prog.addWidget(self.volume_label)
        prog.addWidget(self.volume_slider)
        box.addLayout(prog)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.prev_btn = QPushButton("上一条")
        self.prev_btn.setObjectName("navBtn")
        self.next_btn = QPushButton("下一条")
        self.next_btn.setObjectName("navBtn")
        self.go_btn = QPushButton("播放")
        self.go_btn.setObjectName("goBtn")
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("stopBtn")
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.setObjectName("pauseBtn")
        self.stage_btn = QPushButton("全屏")
        self.stage_btn.setObjectName("stageBtn")
        self.unstage_btn = QPushButton("收起全屏")
        self.unstage_btn.setObjectName("unstageBtn")
        self.prev_btn.clicked.connect(lambda: self.step_cue(-1))
        self.next_btn.clicked.connect(lambda: self.step_cue(1))
        self.go_btn.clicked.connect(self.on_go)
        self.stop_btn.clicked.connect(self.on_stop)
        self.pause_btn.clicked.connect(self.on_pause)
        self.stage_btn.clicked.connect(self.on_stage)
        self.unstage_btn.clicked.connect(self.on_unstage)
        self.panic_btn = QPushButton("全停")
        self.panic_btn.setObjectName("panicBtn")
        self.panic_btn.setToolTip("所有声画立刻停（Ctrl+Esc）")
        self.panic_btn.clicked.connect(self.on_panic)
        self.mute_btn = QPushButton("静音")
        self.mute_btn.setObjectName("muteBtn")
        self.mute_btn.setToolTip("一键静音全部声道（M）")
        self.mute_btn.clicked.connect(self.on_toggle_mute)
        self.hold_btn = QPushButton("封面")
        self.hold_btn.setObjectName("holdBtn")
        self.hold_btn.setToolTip("视频播完落到封面；也可随时切到封面/黑场（B）")
        self.hold_btn.clicked.connect(self.on_toggle_hold)
        self.duck_btn = QPushButton("压低音频")
        self.duck_btn.setObjectName("duckBtn")
        self.duck_btn.setToolTip("讲话时约 0.9 秒把当前音频渐变到设定音量的 60%，再按渐变恢复（D）")
        self.duck_btn.clicked.connect(self.on_toggle_duck)
        for btn in (
            self.prev_btn,
            self.next_btn,
            self.go_btn,
            self.stop_btn,
            self.pause_btn,
            self.stage_btn,
            self.unstage_btn,
            self.panic_btn,
        ):
            row.addWidget(btn)
        row.addStretch(1)
        for btn in (self.mute_btn, self.hold_btn, self.duck_btn):
            row.addWidget(btn)
        box.addLayout(row)
        self.hotkey_bar = QLabel("空格 播放　P 暂停　M 静音　B 封面　D 压低　Esc 停　Ctrl+Esc 全停　F11 演出　1–9 点播")
        self.hotkey_bar.setObjectName("hotkeyBar")
        box.addWidget(self.hotkey_bar)
        return bar

    def current_row(self) -> int:
        items = self.table.selectedIndexes()
        if items:
            return items[0].row()
        return -1

    def cue_at_row(self, row: int) -> Cue | None:
        if 0 <= row < len(self.project.cues):
            return self.project.cues[row]
        return None

    def live_state_for_row(self, row: int) -> str | None:
        if not (0 <= row < len(self.project.cues)):
            return None
        cue_id, state = self.controller.live_cue_state()
        if cue_id and self.project.cues[row].id == cue_id:
            return state
        return None

    def _remain_text(self, st) -> str:
        if self.controller.hold_active:
            return "封面"
        pos, dur = st.position, st.duration
        if pos is None or dur is None or dur <= 0:
            return ""
        left = max(0.0, dur - pos)
        return f"剩余 {self._fmt_clock(left)}"

    @staticmethod
    def _elide(label: QLabel, text: str) -> None:
        raw = (text or "").replace("\n", " ").strip()
        width = max(60, label.width() - 8)
        label.setText(label.fontMetrics().elidedText(raw, Qt.TextElideMode.ElideRight, width))

    def _update_now_next(self, st) -> None:
        if not hasattr(self, "now_title"):
            return
        live_id, live_state = self.controller.live_cue_state()
        live_cue = self._find_cue(live_id)
        in_show = live_cue is not None and live_cue in self.project.cues
        if live_cue is not None:
            kicker = {
                "playing": "正在播",
                "paused": "已暂停",
                "preview": "预监",
                "cover": "封面",
            }.get(live_state, "正在播")
            if self.controller._fading and not self.controller._fade_in:
                kicker = "渐停中"
            # 临时配乐不进底栏「正在播」
            if not in_show:
                live_cue = None
        if live_cue is not None and in_show:
            self.now_card.setStyleSheet("")
            self.now_kicker.setStyleSheet("")
            self.now_title.setStyleSheet("")
            self.now_notes.setStyleSheet("")
            self.now_kicker.setText(kicker)
            idx = self.project.cues.index(live_cue) + 1
            self._elide(self.now_title, f"{idx}  {live_cue.name}")
            remain = self._remain_text(st)
            if hasattr(self, "now_remain"):
                self.now_remain.setText(remain)
                self.now_remain.setVisible(bool(remain))
            self.now_notes.setText((live_cue.notes or "").strip())
        else:
            t = self.theme
            self.now_card.setStyleSheet(
                f"QFrame#nowCard {{ background:{t['now_idle_bg']}; border-left: 4px solid {t['now_idle_accent']}; }}"
            )
            self.now_kicker.setStyleSheet(f"color:{t['now_idle_accent']};")
            self.now_title.setStyleSheet(f"color:{t['now_idle_title']};")
            self.now_notes.setStyleSheet(f"color:{t['now_notes']};")
            # 底栏只显示节目单选中，不显示临时配乐选中
            self.now_kicker.setText("选中")
            sel = self.current_cue()
            if hasattr(self, "now_remain"):
                self.now_remain.clear()
                self.now_remain.setVisible(False)
            if sel is not None:
                self._elide(self.now_title, f"{self.current_row() + 1}  {sel.name}")
                self.now_notes.setText((sel.notes or "").strip())
            else:
                self.now_title.setText("—")
                self.now_notes.setText("")
        self._update_next_card()
        self._update_proj_status()
        self._update_show_clock()
        self._update_vu()

    def _next_show_cue(self) -> Cue | None:
        row = self.current_row()
        start = row + 1 if row >= 0 else 0
        for i in range(start, len(self.project.cues)):
            cue = self.project.cues[i]
            if cue.type in ("audio", "video"):
                return cue
        return None

    def _update_next_card(self) -> None:
        if not hasattr(self, "next_title"):
            return
        nxt = self._next_show_cue()
        if nxt is None:
            self.next_title.setText("—")
            self.next_notes.setText("")
            return
        idx = self.project.cues.index(nxt) + 1
        self._elide(self.next_title, f"{idx}  {nxt.name}")
        self.next_notes.setText((nxt.notes or "").strip())

    def _update_proj_status(self) -> None:
        if not hasattr(self, "proj_status"):
            return
        if self.controller.hold_active:
            text = "封面"
        elif self.controller.video_on_stage:
            text = "观众全屏"
        elif self.controller.video is not None and self.controller.video.alive:
            text = "预监"
        else:
            text = "无画面"
        self.proj_status.setText(text)

    def _update_show_clock(self) -> None:
        if not hasattr(self, "show_clock"):
            return
        if self._show_t0 is None:
            self.show_clock.setText("未开演")
            return
        import time as _time

        elapsed = max(0, int(_time.monotonic() - self._show_t0))
        self.show_clock.setText(f"已开演 {elapsed // 60:02d}:{elapsed % 60:02d}")

    def _reset_show_clock(self) -> None:
        self._show_t0 = None
        self._update_show_clock()

    def _mark_show_go(self) -> None:
        import time as _time

        if self._show_t0 is None:
            self._show_t0 = _time.monotonic()

    def _update_vu(self) -> None:
        if not hasattr(self, "show_vu"):
            return
        def level(on: bool, vol: float) -> int:
            if not on:
                return 0
            return max(8, min(100, int(vol)))
        self.show_vu.setValue(level(self.controller._show_audio_on(), self.controller.output_volume))
        self.lib_vu.setValue(level(self.controller._lib_audio_on(), self.controller.library_volume))

    def _sync_live_row(self) -> None:
        cue_id, state = self.controller.live_cue_state()
        aid, astate = self.controller.live_audio_state()
        vid, vstate = self.controller.live_library_video_state()
        sig = (cue_id, state, aid, astate, vid, vstate)
        if sig == self._live_sig:
            return
        self._live_sig = sig
        for i, cue in enumerate(self.project.cues):
            item = self.table.item(i, 0)
            if item is None:
                continue
            if item.text() != str(i + 1):
                item.setText(str(i + 1))
        self.table.viewport().update()
        for widget in self._library_lists():
            widget.viewport().update()

    def current_cue(self) -> Cue | None:
        row = self.current_row()
        if 0 <= row < len(self.project.cues):
            return self.project.cues[row]
        return None

    def _find_cue(self, cue_id: str | None) -> Cue | None:
        if not cue_id:
            return None
        for cue in self.project.cues:
            if cue.id == cue_id:
                return cue
        for cue in self.project.library:
            if cue.id == cue_id:
                return cue
        return None

    def active_cue(self) -> Cue | None:
        if getattr(self, "_focus", "cues") == "library":
            lib = self.current_library_cue()
            if lib is not None:
                return lib
        return self.current_cue()

    def _focus_cues(self) -> None:
        self._focus = "cues"
        for widget in self._library_lists():
            widget.blockSignals(True)
            widget.clearSelection()
            widget.blockSignals(False)

    def media_for(self, cue: Cue) -> Path | None:
        return self.project.resolve_media(cue)

    def media_missing(self, cue: Cue | None) -> bool:
        if cue is None or cue.type not in ("audio", "video"):
            return False
        raw = (cue.path or "").strip()
        if not raw:
            return True
        import time as _time

        now = _time.monotonic()
        cached = self._missing_cache.get(raw)
        if cached is not None and now - cached[0] < 2.0:
            return cached[1]
        media = self.project.resolve_media(cue)
        missing = media is None or not media.exists()
        self._missing_cache[raw] = (now, missing)
        return missing

    def reload_table(self, keep_row: int | None = None) -> None:
        if keep_row is None:
            keep_row = self.current_row()
        self._filling = True
        self.table.setRowCount(len(self.project.cues))
        for i, cue in enumerate(self.project.cues):
            values = [str(i + 1), cue.label(), cue.name, cue.notes, cue.path]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsDragEnabled
                )
                if col == 0:
                    font = QFont("Consolas")
                    font.setBold(True)
                    item.setFont(font)
                if col == 2 and cue.type in ("audio", "video") and self.media_missing(cue):
                    item.setToolTip(f"找不到文件：{cue.path or '（空路径）'}")
                if col == 3 and cue.notes:
                    item.setToolTip(cue.notes)
                self.table.setItem(i, col, item)
        if self._focus == "library":
            self.table.clearSelection()
        elif 0 <= keep_row < len(self.project.cues):
            self.table.selectRow(keep_row)
        elif self.project.cues:
            self.table.selectRow(0)
        self._filling = False
        self._refresh_project_label()
        self.fill_inspector()
        self.reload_library()
        self._live_sig = (None, "", None, "", None, "")
        self._sync_live_row()

    def _library_category_names(self) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for cue in self.project.library:
            if cue.type not in ("audio", "video"):
                continue
            cat = (cue.category or "").strip()
            if not cat or cat in seen:
                continue
            seen.add(cat)
            names.append(cat)
        return names

    def _set_category_editor(self, cue: Cue | None) -> None:
        show = (
            cue is not None
            and getattr(self, "_focus", "cues") == "library"
            and cue.type in ("audio", "video")
        )
        self.category_row.setVisible(show)
        if not show:
            return
        current = (cue.category or "").strip()
        names = self._library_category_names()
        default = getattr(self, "_library_default_category", "") or ""
        if default and default not in names:
            names = list(names) + [default]
        if current and current not in names:
            names = list(names) + [current]
        self.category_edit.blockSignals(True)
        self.category_edit.clear()
        self.category_edit.addItem("未分类", "")
        for name in names:
            self.category_edit.addItem(name, name)
        idx = 0
        if current:
            found = self.category_edit.findData(current)
            if found < 0:
                found = self.category_edit.findText(current)
            if found >= 0:
                idx = found
        self.category_edit.setCurrentIndex(idx)
        self.category_edit.blockSignals(False)

    def fill_inspector(self) -> None:
        cue = self.active_cue()
        self._filling = True
        if cue is None:
            self.name_edit.clear()
            self.notes_edit.clear()
            self.path_edit.clear()
            self.loop_check.setChecked(False)
            self.loop_check.setEnabled(False)
            self.loop_check.setText("循环")
            self.loop_check.setToolTip("")
            self._set_category_editor(None)
            if hasattr(self, "trim_row"):
                self.trim_toggle.setEnabled(False)
                self.trim_row.setEnabled(False)
                for spin in (self.trim_in_spin, self.trim_out_spin, self.fade_in_spin, self.fade_out_spin):
                    spin.setValue(0)
        else:
            self.name_edit.setText(cue.name)
            self.notes_edit.setPlainText(cue.notes)
            self.path_edit.setText(cue.path)
            self.loop_check.setChecked(cue.loop)
            if cue.type == "audio":
                self.loop_check.setText("音频循环")
                self.loop_check.setEnabled(True)
            elif cue.type == "video":
                self.loop_check.setText("视频循环")
                self.loop_check.setEnabled(True)
            else:
                self.loop_check.setText("循环")
                self.loop_check.setEnabled(False)
            if getattr(self, "_focus", "cues") == "library" and cue.type in ("audio", "video"):
                mode = self.project.library_play_mode(cue_category_key(cue))
                if mode != LIB_PLAY_DEFAULT:
                    self.loop_check.setEnabled(False)
                    self.loop_check.setToolTip(
                        f"当前分类是「{library_play_label(mode)}」，由分类栏按钮控制。"
                        "切回默认后，本勾选才生效。"
                    )
                else:
                    self.loop_check.setToolTip("默认模式：勾选则本条循环；不勾选则播完即停，不自动下一首")
            else:
                self.loop_check.setToolTip("本条循环播放")
            self._set_category_editor(cue)
            if hasattr(self, "trim_row"):
                media = cue.type in ("audio", "video")
                self.trim_toggle.setEnabled(media)
                self.trim_row.setEnabled(media)
                self.trim_in_spin.setValue(cue.trim_in if media else 0)
                self.trim_out_spin.setValue(cue.trim_out if media else 0)
                self.fade_in_spin.setValue(cue.fade_in if media else 0)
                self.fade_out_spin.setValue(cue.fade_out if media else 0)
                used = media and (cue.trim_in or cue.trim_out or cue.fade_in or cue.fade_out)
                if used:
                    self.trim_toggle.setChecked(True)
                elif not self.trim_toggle.isChecked():
                    self.trim_row.setVisible(False)
        self._filling = False
        if hasattr(self, "lock_act"):
            self._apply_cues_lock()

    def apply_inspector(self) -> None:
        if self._filling:
            return
        if self._cues_locked and getattr(self, "_focus", "cues") == "cues":
            return
        cue = self.active_cue()
        if cue is None:
            return
        new_name = self.name_edit.text().strip()
        new_notes = self.notes_edit.toPlainText()
        new_loop = self.loop_check.isChecked()
        if (new_name, new_notes, new_loop) != (cue.name, cue.notes, cue.loop):
            self._push_undo()
        cue.name = new_name
        cue.notes = new_notes
        cue.loop = new_loop
        if cue.type in ("audio", "video") and hasattr(self, "trim_in_spin"):
            cue.trim_in = float(self.trim_in_spin.value())
            cue.trim_out = float(self.trim_out_spin.value())
            cue.fade_in = float(self.fade_in_spin.value())
            cue.fade_out = float(self.fade_out_spin.value())
        if self._focus == "library":
            self.controller.apply_loop(cue, self._library_loop_for(cue))
        else:
            self.controller.apply_loop(cue)
            self.project.mirror_show_cue(cue)
            if hasattr(self, "library_audio_list"):
                self.reload_library()
        self.project.mark_dirty()
        self._refresh_project_label()
        if self._focus == "library":
            widget = self.library_audio_list
            for r in range(widget.rowCount()):
                item = widget.item(r, 0)
                payload = item.data(Qt.ItemDataRole.UserRole) if item else None
                if isinstance(payload, Cue) and payload.id == cue.id:
                    type_item = widget.item(r, 0)
                    if type_item is not None:
                        type_item.setText(TYPE_LABELS.get(cue.type, cue.type))
                    name_item = widget.item(r, 1)
                    if name_item is not None:
                        name_item.setText(cue.name)
                    notes_item = widget.item(r, 2)
                    if notes_item is not None:
                        notes_item.setText((cue.notes or "").replace("\n", " "))
                    break
            widget.viewport().update()
            return
        row = self.current_row()
        if row >= 0:
            self.table.item(row, 2).setText(cue.name)
            self.table.item(row, 3).setText(cue.notes)

    def _category_from_combo(self) -> str:
        data = self.category_edit.currentData()
        if data is not None:
            return str(data).strip()
        text = self.category_edit.currentText().strip()
        return "" if (not text or text == "未分类") else text

    def _apply_category_to_cue(self, cue: Cue, new_cat: str) -> None:
        new_cat = (new_cat or "").strip()
        if new_cat == (cue.category or "").strip():
            return
        self._push_undo()
        cue.category = new_cat
        if new_cat:
            self._library_default_category = new_cat
        self.project.mark_dirty()
        self._focus = "library"
        self._library_focus = "audio"
        self.reload_library("audio", keep_id=cue.id)
        self._set_category_editor(cue)
        self._refresh_project_label()
        self._refresh_status()

    def _commit_library_category(self) -> None:
        """下拉选择：切换当前临时媒体的分类。"""
        if self._filling:
            return
        cue = self.active_cue()
        if cue is None or self._focus != "library" or cue.type not in ("audio", "video"):
            return
        self._apply_category_to_cue(cue, self._category_from_combo())

    def edit_library_category(self) -> None:
        """编辑按钮：弹窗改分类名（与下拉选择分开）。"""
        if getattr(self, "_focus", "cues") != "library":
            QMessageBox.information(self, "编辑分类", "请先在右侧素材库选中一条媒体。")
            return
        cue = self.current_library_cue()
        if cue is None or cue.type not in ("audio", "video"):
            QMessageBox.information(self, "编辑分类", "请先在右侧素材库选中一条媒体。")
            return
        old = (cue.category or "").strip()
        text, ok = QInputDialog.getText(
            self,
            "编辑分类",
            "分类名称（留空=未分类）：",
            text=old,
        )
        if not ok:
            return
        new_cat = text.strip()
        if new_cat == old:
            return
        siblings = [
            item
            for item in self.project.library
            if item.type in ("audio", "video")
            and (item.category or "").strip() == old
            and item.id != cue.id
        ]
        rename_all = False
        if old and siblings:
            box = QMessageBox(self)
            box.setWindowTitle("编辑分类")
            box.setIcon(QMessageBox.Icon.Question)
            box.setText(
                f"还有 {len(siblings)} 首也在「{old}」。\n"
                f"要全部改成「{new_cat or '未分类'}」，还是只改当前这首？"
            )
            all_btn = box.addButton("全部改名", QMessageBox.ButtonRole.AcceptRole)
            one_btn = box.addButton("只改这首", QMessageBox.ButtonRole.ActionRole)
            box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(all_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is None or clicked not in (all_btn, one_btn):
                return
            rename_all = clicked is all_btn
        if rename_all:
            for item in siblings:
                item.category = new_cat
            cue.category = new_cat
            self.project.rename_library_play_mode(old, new_cat)
            if new_cat:
                self._library_default_category = new_cat
            self.project.mark_dirty()
            self.reload_library("audio", keep_id=cue.id)
            self._set_category_editor(cue)
            self._refresh_project_label()
            self._refresh_status()
        else:
            self._apply_category_to_cue(cue, new_cat)

    def on_selection_changed(self) -> None:
        if self._filling:
            return
        self._focus_cues()
        self.fill_inspector()
        self._refresh_status()

    def on_row_clicked(self, row: int, _col: int) -> None:
        if not (0 <= row < len(self.project.cues)):
            return
        self._focus_cues()
        self.fill_inspector()
        self._refresh_status()

    def _toggle_cues_lock(self) -> None:
        self._cues_locked = bool(self.lock_act.isChecked())
        self._apply_cues_lock()

    def _apply_cues_lock(self) -> None:
        locked = self._cues_locked
        if hasattr(self, "table"):
            self.table.setDragEnabled(not locked)
        for btn in getattr(self, "_cue_edit_btns", []):
            btn.setEnabled(not locked)
        cue_focus = getattr(self, "_focus", "cues") == "cues"
        inspectable = not (locked and cue_focus)
        for widget in (
            getattr(self, "name_edit", None),
            getattr(self, "notes_edit", None),
            getattr(self, "loop_check", None),
        ):
            if widget is not None:
                widget.setEnabled(inspectable)
        if locked:
            self.lock_act.setText("已锁定节目单")
        else:
            self.lock_act.setText("锁定节目单")
        self._refresh_project_label()

    def on_check_media(self) -> None:
        self._missing_cache.clear()
        missing: list[str] = []
        for i, cue in enumerate(self.project.cues, 1):
            if cue.type in ("audio", "video") and self.media_missing(cue):
                missing.append(f"节目单 {i}. {cue.name or '（未命名）'}  {cue.path or '（空路径）'}")
        for cue in self.project.library:
            if cue.type in ("audio", "video") and self.media_missing(cue):
                cat = (cue.category or "").strip() or "未分类"
                missing.append(f"素材库/{cat}  {cue.name or '（未命名）'}  {cue.path or '（空路径）'}")
        if not missing:
            QMessageBox.information(self, "检查媒体", "节目单和素材库里的音视频文件都在。")
            return
        box = QMessageBox(self)
        box.setWindowTitle("检查媒体")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(f"有 {len(missing)} 条找不到文件。")
        box.setInformativeText("可在「编辑选中」里用「浏览媒体…」补路径，或把文件拷到工程目录。")
        box.setDetailedText("\n".join(missing))
        box.exec()

    def on_create_shortcut(self) -> None:
        from src.shortcut import create_shortcuts

        try:
            desktop, local = create_shortcuts()
        except OSError as exc:
            QMessageBox.warning(self, "创建快捷方式", str(exc))
            return
        self.settings.desktop_shortcut_created = True
        self.settings.save()
        QMessageBox.information(
            self,
            "创建快捷方式",
            f"已创建：\n• {desktop}\n• {local}\n\n之后可从桌面图标启动。",
        )

    def _maybe_create_desktop_shortcut(self) -> None:
        if getattr(self.settings, "desktop_shortcut_created", False):
            return
        from src.shortcut import create_shortcuts

        try:
            create_shortcuts()
            self.settings.desktop_shortcut_created = True
            self.settings.save()
        except OSError:
            pass

    def _warm_players(self) -> None:
        self.controller.warm_audio_players()
        self._rebuild_audio_menu()

    def on_panic(self) -> None:
        from src.show_log import log as show_log

        self.controller.panic_stop()
        show_log("全停")
        self._refresh_status()

    def _toggle_show_mode(self) -> None:
        self._set_show_mode(not self._show_mode)

    def _set_show_mode(self, on: bool, persist: bool = True) -> None:
        self._show_mode = bool(on)
        if hasattr(self, "show_mode_act"):
            self.show_mode_act.blockSignals(True)
            self.show_mode_act.setChecked(self._show_mode)
            self.show_mode_act.blockSignals(False)
        inspector = getattr(self, "inspector_panel", None)
        if inspector is not None:
            inspector.setVisible(not self._show_mode)
        add = getattr(self, "_cue_edit_btns", None)
        if add and self._show_mode:
            for btn in add:
                btn.setVisible(False)
        elif add:
            for btn in add:
                btn.setVisible(True)
        if hasattr(self, "now_card"):
            self.now_card.setMinimumHeight(120 if self._show_mode else 0)
        if persist:
            self.settings.show_mode = self._show_mode
            self.settings.save()
        if hasattr(self, "main_split"):
            if self._show_mode:
                self._edit_split_sizes = self.main_split.sizes()
                total = sum(self.main_split.sizes()) or 1000
                self.main_split.setSizes([int(total * 0.62), 0, int(total * 0.38)])
            elif self._edit_split_sizes:
                self.main_split.setSizes(self._edit_split_sizes)
        self._refresh_status()

    def _on_library_filter(self, text: str) -> None:
        self._library_filter = text or ""
        keep = self.current_library_cue().id if self.current_library_cue() else None
        self.reload_library("audio", keep_id=keep)

    def _library_matches(self, cue: Cue) -> bool:
        query = (self._library_filter or "").strip().casefold()
        if not query:
            return True
        blob = f"{cue.name} {cue.notes} {cue.category} {cue.path}".casefold()
        return query in blob

    def _visible_library_cues(self) -> list[Cue]:
        cues: list[Cue] = []
        for cat, items in self._grouped_library():
            key = "" if cat == LIB_UNCATEGORIZED else cat
            if key in self._collapsed_cats:
                continue
            for cue in items:
                if self._library_matches(cue):
                    cues.append(cue)
        return cues

    def _fire_library_hotkey(self, number: int) -> None:
        if number < 1:
            return
        cues = self._visible_library_cues()
        if number > len(cues):
            return
        cue = cues[number - 1]
        self._select_library_cue(cue.id)
        self._play_library_cue(cue, autoplay=cue.type == "audio")
        self.fill_inspector()
        self._refresh_status()

    def _rebuild_audio_menu(self) -> None:
        menu = getattr(self, "audio_menu", None)
        if menu is None:
            return
        menu.clear()
        current = (self.settings.audio_device or "").strip()
        auto = menu.addAction("系统默认")
        auto.setCheckable(True)
        auto.setChecked(not current)
        auto.triggered.connect(lambda: self._set_audio_device(""))
        devices = self.controller.list_audio_devices()
        if not devices:
            empty = menu.addAction("（启动播放后可列出设备）")
            empty.setEnabled(False)
            return
        for name, desc in devices:
            act = menu.addAction(desc or name)
            act.setCheckable(True)
            act.setChecked(name == current)
            act.triggered.connect(lambda checked=False, n=name: self._set_audio_device(n))

    def _set_audio_device(self, name: str) -> None:
        self.settings.audio_device = name
        self.settings.save()
        self._apply_player_config()
        self.controller.stop_all()
        self.controller.warm_audio_players()
        self._rebuild_audio_menu()

    def on_help(self, page: str = "guide") -> None:
        from src.ui.help_dialog import HelpDialog

        HelpDialog(self, page=page if isinstance(page, str) else "guide").exec()

    def on_about(self) -> None:
        from src.ui.help_dialog import show_about

        show_about(self)

    def on_check_update(self) -> None:
        root = Path(__file__).resolve().parents[2]
        git_dir = root / ".git"
        if git_dir.exists():
            try:
                subprocess.run(
                    ["git", "fetch", "origin"],
                    cwd=str(root),
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                local = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"], cwd=str(root), text=True
                ).strip()
                remote = subprocess.check_output(
                    ["git", "rev-parse", "--short", "origin/main"], cwd=str(root), text=True
                ).strip()
            except (OSError, subprocess.CalledProcessError) as exc:
                QMessageBox.warning(self, "检查更新", f"git 失败：{exc}")
                return
            if local == remote:
                QMessageBox.information(self, "检查更新", f"已是 GitHub 最新。\n当前 {local}")
                return
            go = QMessageBox.question(
                self,
                "检查更新",
                f"本地 {local}\nGitHub {remote}\n\n要现在 pull 吗？未提交的改动不会自动覆盖。",
            )
            if go != QMessageBox.StandardButton.Yes:
                return
            script = root / "scripts" / "update_from_github.ps1"
            r = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                cwd=str(root),
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            QMessageBox.information(self, "检查更新", (r.stdout or "")[-1500:] or r.stderr or "完成")
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl("https://github.com/yikelen/kongchang/releases/latest"))

    def on_open_show_log(self) -> None:
        from src.show_log import log_path

        path = log_path()
        if not path.exists():
            path.write_text("", encoding="utf-8")
        try:
            os.startfile(path)  # type: ignore[attr-defined]
        except OSError as exc:
            QMessageBox.information(self, "演出日志", f"{path}\n{exc}")

    def _start_fade(self, *, library: bool) -> None:
        running = (
            self.controller.fade_stop_audio(library=True)
            if library
            else self.controller.fade_stop()
        )
        if running:
            self._fade_timer.start(100)
        self._refresh_status()

    def _kick_fade_in(self) -> None:
        if self.controller.begin_fade_in():
            self._fade_timer.start(80)

    def _on_fade_tick(self) -> None:
        fade_more = False
        if self.controller._fading_show or self.controller._fading_lib:
            fade_more = self.controller.fade_tick()
        duck_more = self.controller.duck_tick()
        if not fade_more and not duck_more:
            self._fade_timer.stop()
            self._refresh_status()

    def _hold_image(self) -> Path:
        cover = self.project.resolve_hold_cover()
        if cover is not None:
            return cover
        from src.paths import hold_black_png

        return hold_black_png()

    def _maybe_hold_cover(self) -> None:
        if not self.controller.video_reached_eof():
            return
        cue = self._find_cue(self.controller.video_cue_id)
        if cue is None or cue.loop:
            return
        if cue in self.project.library:
            mode = self.project.library_play_mode(cue_category_key(cue))
            if mode in (LIB_PLAY_SEQ, LIB_PLAY_ALL):
                return
        self.controller.show_hold(
            self._hold_image(),
            from_library=self.controller.video_from_library,
            stay_staged=self.controller.video_on_stage,
        )

    def on_toggle_mute(self) -> None:
        self.controller.toggle_master_mute()
        self._refresh_status()

    def on_toggle_duck(self) -> None:
        if self.controller.toggle_duck():
            self._fade_timer.start(50)
        self._refresh_status()

    def on_toggle_hold(self) -> None:
        if self.controller.hold_active:
            self.controller.unstage_video()
            self._refresh_status()
            return
        self.controller.show_hold(
            self._hold_image(),
            from_library=self.controller.video_from_library,
            stay_staged=True,
        )
        self._refresh_status()

    def on_set_cover(self) -> None:
        current = self.project.resolve_hold_cover()
        start = str(current.parent) if current else str(self.project.directory or Path.home())
        path, _ok = QFileDialog.getOpenFileName(self, "选择封面图", start, IMAGE_FILTER)
        if not path:
            if self.project.hold_cover:
                if QMessageBox.question(self, "封面图", "清除已设置的封面？没有封面时，视频播完会落到黑场。") == QMessageBox.StandardButton.Yes:
                    self._push_undo()
                    self.project.hold_cover = ""
                    self.project.mark_dirty()
            return
        self._push_undo()
        self.project.hold_cover = self.project.store_path(Path(path))
        self.project.mark_dirty()
        QMessageBox.information(self, "封面图", f"已设置封面：{self.project.hold_cover}\n视频播完（不循环）后会自动切到这张图。")

    def _snapshot_project(self) -> str:
        return json.dumps(
            {
                "cues": [cue.to_dict() for cue in self.project.cues],
                "library": [cue.to_dict() for cue in self.project.library],
                "library_play_modes": dict(self.project.library_play_modes),
                "hold_cover": self.project.hold_cover,
            },
            ensure_ascii=False,
        )

    def _push_undo(self) -> None:
        if self._undoing:
            return
        self._undo_stack.append(self._snapshot_project())
        del self._undo_stack[:-40]
        self._redo_stack.clear()

    def _restore_snapshot(self, raw: str) -> None:
        data = json.loads(raw)
        self._undoing = True
        try:
            self.project.cues = [Cue.from_dict(item) for item in data.get("cues") or []]
            self.project.library = [Cue.from_dict(item) for item in data.get("library") or []]
            self.project.library_play_modes = dict(data.get("library_play_modes") or {})
            self.project.hold_cover = str(data.get("hold_cover") or "")
            self.project.mark_dirty()
            keep = self.current_library_cue().id if self.current_library_cue() else None
            self.reload_table(self.current_row())
            self.reload_library("audio", keep_id=keep)
            self.fill_inspector()
        finally:
            self._undoing = False

    def on_undo(self) -> None:
        if self._cues_locked or not self._undo_stack:
            return
        self._redo_stack.append(self._snapshot_project())
        self._restore_snapshot(self._undo_stack.pop())
        self._refresh_status()

    def on_redo(self) -> None:
        if self._cues_locked or not self._redo_stack:
            return
        self._undo_stack.append(self._snapshot_project())
        self._restore_snapshot(self._redo_stack.pop())
        self._refresh_status()

    def on_go(self) -> None:
        """底栏播放：只操作节目单，不碰临时配乐。"""
        if self._editing_text():
            return
        self._focus_cues()
        cue = self.current_cue()
        if cue is None:
            return
        if cue.type == "note":
            return
        if cue.type in ("audio", "video"):
            media = self.media_for(cue)
            if media is None or not media.exists():
                QMessageBox.warning(self, "没有文件", f"找不到媒体：\n{cue.path or '（空路径）'}")
                return
        self._apply_player_config()
        self.controller.go(cue, self.media_for(cue))
        self._kick_fade_in()
        self._mark_show_go()
        from src.show_log import log as show_log

        show_log("节目单播放", f"{cue.type}\t{cue.name}")
        self._refresh_status()

    def on_stop(self) -> None:
        """底栏停止：只停节目单。"""
        self._start_fade(library=False)

    def on_pause(self) -> None:
        """底栏暂停：只暂停节目单。"""
        self.controller.toggle_pause(self.current_cue())
        self._refresh_status()

    def step_cue(self, delta: int) -> None:
        if not self.project.cues:
            return
        row = self.current_row()
        if row < 0:
            row = 0
        dest = max(0, min(len(self.project.cues) - 1, row + delta))
        self._filling = True
        self.table.selectRow(dest)
        self._filling = False
        self._focus_cues()
        self.fill_inspector()
        self._refresh_status()

    def _refresh_project_label(self) -> None:
        label = getattr(self, "project_label", None)
        if label is None:
            return
        if self.project.path:
            mark = " *" if self.project.dirty else ""
            lock = "  已锁定" if self._cues_locked else ""
            label.setText(f"{self.project.path.name}{mark}{lock}")
        else:
            label.setText("已锁定节目单" if self._cues_locked else "未打开工程")

    def _schedule_autosave(self) -> None:
        self._refresh_project_label()
        if self.project.path is None:
            return
        self._autosave_timer.start()

    def _autosave_now(self) -> None:
        if not self.project.dirty or self.project.path is None:
            return
        try:
            self.project.save()
        except OSError as exc:
            self.status_label.setText(f"自动保存失败：{exc}")
            self.status_label.setVisible(True)
            return
        self._refresh_project_label()

    def _adopt_project(self, project: Project) -> None:
        self.project = project
        if self.project.sync_show_mirrors():
            self.project.mark_dirty()
        if hasattr(self, "_autosave_timer"):
            self.project.on_dirty = self._schedule_autosave

    def _remember_project(self, path: Path | None) -> None:
        if path is None:
            return
        self.settings.remember_project(path)
        self._refresh_recent_menu()

    def _startup_candidates(self, given: Path | None) -> list[Path]:
        raw: list[Path] = []
        if given is not None:
            raw.append(given)
        if self.settings.last_project:
            raw.append(Path(self.settings.last_project))
        raw.extend(Path(item) for item in self.settings.recent_projects)
        seen: set[str] = set()
        candidates: list[Path] = []
        for path in raw:
            key = str(path).casefold()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(path)
        return candidates

    def _open_startup_project(self, given: Path | None) -> None:
        for path in self._startup_candidates(given):
            if not path.exists():
                continue
            try:
                self._adopt_project(Project.load(path))
                self._drop_stop_cues()
                self._remember_project(path)
                return
            except Exception:
                continue

    def _refresh_recent_menu(self) -> None:
        menu = getattr(self, "recent_menu", None)
        if menu is None:
            return
        menu.clear()
        items = []
        for text in self.settings.recent_projects:
            path = Path(text)
            if path.exists():
                items.append(path)
        if not items:
            empty = menu.addAction("（空）")
            empty.setEnabled(False)
            return
        for path in items:
            action = QAction(f"{path.parent.name} / {path.name}", self)
            action.setToolTip(str(path))
            action.setData(str(path))
            action.triggered.connect(lambda checked=False, p=str(path): self.on_open_recent(p))
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction("清空最近记录", self.on_clear_recent)

    def on_open_recent(self, path_text: str) -> None:
        path = Path(path_text)
        if not path.exists():
            QMessageBox.warning(self, "打开失败", f"找不到工程：\n{path}")
            self.settings.recent_projects = [
                item for item in self.settings.recent_projects if item != path_text
            ]
            if self.settings.last_project == path_text:
                self.settings.last_project = self.settings.recent_projects[0] if self.settings.recent_projects else ""
            self.settings.save()
            self._refresh_recent_menu()
            return
        if not self._confirm_discard():
            return
        try:
            self._adopt_project(Project.load(path))
            self._drop_stop_cues()
            self._remember_project(path)
        except Exception as exc:
            QMessageBox.warning(self, "打开失败", str(exc))
            return
        self.reload_table()

    def on_clear_recent(self) -> None:
        current = str(self.project.path.resolve()) if self.project.path else ""
        self.settings.recent_projects = [current] if current else []
        if not current:
            self.settings.last_project = ""
        self.settings.save()
        self._refresh_recent_menu()

    def _drop_stop_cues(self) -> None:
        kept = [cue for cue in self.project.cues if cue.type != "stop"]
        if len(kept) != len(self.project.cues):
            self.project.cues = kept
            self.project.mark_dirty()

    def _on_mpv_script_message(self, args: object) -> None:
        names = args if isinstance(args, list) else []
        if names and names[0] == "kongchang-stage":
            self.on_stage_preview()

    def on_stage_preview(self) -> None:
        self._apply_player_config()
        self.controller.stage_loaded_video()
        self._refresh_status()

    def on_stage(self) -> None:
        cue = self.current_cue()
        if cue is None:
            return
        media = self.media_for(cue)
        if cue.type == "video" and (media is None or not media.exists()):
            QMessageBox.warning(self, "没有文件", f"找不到媒体：\n{cue.path or '（空路径）'}")
            return
        self._apply_player_config()
        self.controller.stage_video(cue, media, from_library=False)
        self._refresh_status()

    def on_unstage(self) -> None:
        if self.controller.video_from_library:
            return
        self.controller.unstage_video()
        self._refresh_status()

    def add_media(self, cue_type: str) -> None:
        if self._cues_locked:
            QMessageBox.information(self, "节目单已锁定", "先取消「工程 → 锁定节目单」再改条目。")
            return
        label = "音频" if cue_type == "audio" else "视频"
        self._insert_after_current(
            Cue(
                id=new_id(),
                name=label,
                type=cue_type,
                loop=cue_type == "audio",
            )
        )
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def add_library_category(self) -> None:
        """编辑区分类旁的 + ：新建分类并赋给当前选中的临时媒体。"""
        if getattr(self, "_focus", "cues") != "library":
            QMessageBox.information(self, "新建分类", "请先在右侧素材库选中一条媒体。")
            return
        cue = self.current_library_cue()
        if cue is None or cue.type not in ("audio", "video"):
            QMessageBox.information(self, "新建分类", "请先在右侧素材库选中一条媒体。")
            return
        text, ok = QInputDialog.getText(
            self,
            "新建分类",
            "分类名称（如：颁奖、茶歇、过场）：",
            text=(cue.category or "").strip() or (self._library_default_category or ""),
        )
        if not ok:
            return
        name = text.strip()
        if not name:
            QMessageBox.information(self, "新建分类", "分类名不能为空。")
            return
        self._apply_category_to_cue(cue, name)

    def add_library_media(self, cue_type: str) -> None:
        label = "音频" if cue_type == "audio" else "视频"
        category = ""
        current = self.current_library_cue() if getattr(self, "_focus", "") == "library" else None
        if current is not None and current.type in ("audio", "video"):
            category = (current.category or "").strip()
        if not category:
            category = getattr(self, "_library_default_category", "") or ""
        cue = Cue(
            id=new_id(),
            name=label,
            type=cue_type,
            loop=cue_type == "audio",
            category=category,
        )
        self._push_undo()
        self.project.library.append(cue)
        self.project.mark_dirty()
        self._focus = "library"
        self._library_focus = "audio"
        self.reload_table(self.current_row())
        self.reload_library("audio", keep_id=cue.id)
        self.fill_inspector()
        self._refresh_status()
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _library_lists(self) -> list[QTableWidget]:
        lists = []
        if hasattr(self, "library_audio_list"):
            lists.append(self.library_audio_list)
        return lists

    def _library_of(self, kind: str) -> list[Cue]:
        return [cue for cue in self.project.library if cue.type == kind]

    def _grouped_library(self) -> list[tuple[str, list[Cue]]]:
        """按分类分组。未分类靠后，「默认」（节目单镜像）永远在最底；默认组顺序同节目单。"""
        order: list[str] = []
        buckets: dict[str, list[Cue]] = {}
        for cue in self.project.library:
            if cue.type not in ("audio", "video"):
                continue
            cat = (cue.category or "").strip() or LIB_UNCATEGORIZED
            if cat not in buckets:
                buckets[cat] = []
                order.append(cat)
            buckets[cat].append(cue)
        if LIB_UNCATEGORIZED in order:
            order = [c for c in order if c != LIB_UNCATEGORIZED] + [LIB_UNCATEGORIZED]
        if SHOW_MIRROR_CATEGORY in order:
            order = [c for c in order if c != SHOW_MIRROR_CATEGORY] + [SHOW_MIRROR_CATEGORY]
        if SHOW_MIRROR_CATEGORY in buckets:
            show_order = {cue.id: index for index, cue in enumerate(self.project.cues)}
            buckets[SHOW_MIRROR_CATEGORY] = sorted(
                buckets[SHOW_MIRROR_CATEGORY],
                key=lambda item: show_order.get(item.source_id, 10**9),
            )
        return [(cat, buckets[cat]) for cat in order]

    def _on_library_selected(self, kind: str) -> None:
        self._focus = "library"
        self._library_focus = "audio"
        self.table.blockSignals(True)
        self.table.clearSelection()
        self.table.blockSignals(False)
        # 点到分类标题行时，自动选中下一首媒体
        widget = self.library_audio_list
        row = widget.currentRow()
        item = widget.item(row, 0) if row >= 0 else None
        payload = item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(payload, tuple) and payload and payload[0] == LIB_HEADER:
            title = str(payload[1] if len(payload) > 1 else LIB_UNCATEGORIZED)
            key = "" if title == LIB_UNCATEGORIZED else title
            if key in self._collapsed_cats:
                self._collapsed_cats.discard(key)
            else:
                self._collapsed_cats.add(key)
            keep = None
            self.reload_library("audio", keep_id=keep)
            self.fill_inspector()
            self._refresh_status()
            return
        self.fill_inspector()
        self._refresh_status()

    def _append_library_row(self, target: QTableWidget, cue: Cue) -> int:
        row = target.rowCount()
        target.insertRow(row)
        flags = (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsDragEnabled
        )
        type_item = QTableWidgetItem(TYPE_LABELS.get(cue.type, cue.type))
        type_item.setData(Qt.ItemDataRole.UserRole, cue)
        type_item.setFlags(flags)
        name_item = QTableWidgetItem(cue.name)
        name_item.setData(Qt.ItemDataRole.UserRole, cue)
        name_item.setFlags(flags)
        notes_item = QTableWidgetItem((cue.notes or "").replace("\n", " "))
        notes_item.setData(Qt.ItemDataRole.UserRole, cue)
        notes_item.setFlags(flags)
        if self.media_missing(cue):
            name_item.setToolTip(f"找不到文件：{cue.path or '（空路径）'}")
        if cue.notes:
            notes_item.setToolTip(cue.notes)
        target.setItem(row, 0, type_item)
        target.setItem(row, 1, name_item)
        target.setItem(row, 2, notes_item)
        return row

    def _append_library_header(self, target: QTableWidget, title: str) -> None:
        row = target.rowCount()
        target.insertRow(row)
        header_payload = (LIB_HEADER, title)
        header_flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDropEnabled
        for col, text in enumerate((title, "", "")):
            item = QTableWidgetItem(text if col == 0 else "")
            item.setData(Qt.ItemDataRole.UserRole, header_payload)
            item.setFlags(header_flags)
            target.setItem(row, col, item)
        target.setSpan(row, 0, 1, 2)
        target.setRowHeight(row, 36)
        key = "" if title == LIB_UNCATEGORIZED else title
        mode = self.project.library_play_mode(key)
        btn = QPushButton(_MODE_BTN_TEXT.get(mode, library_play_label(mode)))
        btn.setObjectName("libModeBtn")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedHeight(24)
        btn.setMinimumWidth(76)
        btn.setMaximumWidth(92)
        btn.setProperty("mode", mode)
        btn.setToolTip(library_play_tip(mode) + "\n点击切换：默认 → 单曲 → 顺序 → 列表")
        btn.clicked.connect(lambda _checked=False, cat=key: self._cycle_library_play_mode(cat))
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        holder = QWidget()
        holder.setObjectName("libModeHost")
        holder.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        row_lay = QHBoxLayout(holder)
        row_lay.setContentsMargins(0, 0, 6, 0)
        row_lay.setSpacing(0)
        row_lay.addStretch(1)
        row_lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)
        target.setCellWidget(row, 2, holder)

    def reload_library(
        self,
        keep_kind: str | None = None,
        keep_row: int | None = None,
        keep_id: str | None = None,
    ) -> None:
        del keep_kind  # 仅音频列表
        if keep_id is None and keep_row is not None:
            widget = self.library_audio_list
            item = widget.item(keep_row, 0) if 0 <= keep_row < widget.rowCount() else None
            payload = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(payload, Cue):
                keep_id = payload.id
        if keep_id is None:
            current = self.current_library_cue()
            if current is not None:
                keep_id = current.id

        bar = self.library_audio_list.verticalScrollBar()
        scroll = bar.value() if bar is not None else 0
        self.library_audio_list.blockSignals(True)
        self.library_audio_list.clearSpans()
        self.library_audio_list.setRowCount(0)

        groups = self._grouped_library()
        hot = 0
        for cat, items in groups:
            items = [cue for cue in items if self._library_matches(cue)]
            if not items:
                continue
            self._append_library_header(self.library_audio_list, cat)
            key = "" if cat == LIB_UNCATEGORIZED else cat
            if key in self._collapsed_cats:
                continue
            for cue in items:
                hot += 1
                row = self._append_library_row(self.library_audio_list, cue)
                if self._show_mode and hot <= 9:
                    type_item = self.library_audio_list.item(row, 0)
                    if type_item is not None:
                        type_item.setText(f"{hot} {TYPE_LABELS.get(cue.type, cue.type)}")

        target = self.library_audio_list
        select_row = -1
        if keep_id:
            for r in range(target.rowCount()):
                item = target.item(r, 0)
                payload = item.data(Qt.ItemDataRole.UserRole) if item else None
                if isinstance(payload, Cue) and payload.id == keep_id:
                    select_row = r
                    break
        if self._focus == "library" and select_row >= 0:
            target.selectRow(select_row)
            self._library_focus = "audio"
        self.library_audio_list.blockSignals(False)
        if bar is not None:
            bar.setValue(scroll)

    def current_library_cue(self) -> Cue | None:
        widget = self.library_audio_list
        row = widget.currentRow()
        item = widget.item(row, 0) if row >= 0 else None
        if item is None:
            return None
        payload = item.data(Qt.ItemDataRole.UserRole)
        return payload if isinstance(payload, Cue) else None

    def _select_library_cue(self, cue_id: str) -> None:
        widget = self.library_audio_list
        for row in range(widget.rowCount()):
            item = widget.item(row, 0)
            payload = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(payload, Cue) and payload.id == cue_id:
                widget.blockSignals(True)
                widget.selectRow(row)
                widget.blockSignals(False)
                self._focus = "library"
                self._library_focus = "audio"
                return

    def _library_loop_for(self, cue: Cue) -> bool:
        mode = self.project.library_play_mode(cue_category_key(cue))
        if mode == LIB_PLAY_ONE:
            return True
        if mode in (LIB_PLAY_SEQ, LIB_PLAY_ALL):
            return False
        return bool(cue.loop)

    def _play_library_cue(self, cue: Cue, *, autoplay: bool = False) -> None:
        media = self.media_for(cue)
        if media is None or not media.exists():
            QMessageBox.warning(self, "没有文件", f"找不到媒体：\n{cue.path or '（空路径）'}")
            return
        self._apply_player_config()
        self._focus = "library"
        self._library_focus = "audio"
        loop = self._library_loop_for(cue)
        if cue.type == "audio":
            self.controller.go(cue, media, under_video=True, from_library=True, loop=loop)
        else:
            self.controller.go(cue, media, from_library=True, autoplay=autoplay, loop=loop)
        self._kick_fade_in()

    def _cycle_library_play_mode(self, category_key: str) -> None:
        current = self.project.library_play_mode(category_key)
        nxt = next_library_play_mode(current)
        self._push_undo()
        self.project.set_library_play_mode(category_key, nxt)
        playing = self._find_cue(self.controller.live_library_state()[0])
        if playing is not None and cue_category_key(playing) == category_key:
            self.controller.apply_loop(playing, self._library_loop_for(playing))
        keep_id = None
        current_cue = self.current_library_cue()
        if current_cue is not None:
            keep_id = current_cue.id
        self.reload_library("audio", keep_id=keep_id)
        self.fill_inspector()
        self._refresh_status()

    def on_library_row_dropped(self, source: int, dest: int) -> None:
        widget = self.library_audio_list

        def payload_at(row: int):
            item = widget.item(row, 0)
            return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

        src = payload_at(source)
        if not isinstance(src, Cue):
            return
        self._push_undo()
        visual: list[tuple[str, str]] = []
        for row in range(widget.rowCount()):
            payload = payload_at(row)
            if isinstance(payload, tuple) and payload and payload[0] == LIB_HEADER:
                visual.append(("header", str(payload[1] if len(payload) > 1 else LIB_UNCATEGORIZED)))
            elif isinstance(payload, Cue):
                visual.append(("cue", payload.id))
        if source >= len(visual) or visual[source][0] != "cue":
            return
        moved = visual.pop(source)
        insert_at = dest if dest <= source else dest - 1
        insert_at = max(0, min(insert_at, len(visual)))
        visual.insert(insert_at, moved)
        by_id = {cue.id: cue for cue in self.project.library}
        self.project.library = rebuild_library_from_visual(
            by_id, visual, uncategorized=LIB_UNCATEGORIZED
        )
        self.project.mark_dirty()
        self.reload_library("audio", keep_id=src.id)
        self.fill_inspector()
        self._refresh_status()

    def _maybe_advance_library(self) -> None:
        """顺序 / 列表：音频、视频各自切同分类下一首，叠播互不影响。"""
        self._advance_library_channel("audio")
        self._advance_library_channel("video")

    def _advance_library_channel(self, kind: str) -> None:
        if kind == "audio":
            if self.controller._fading_lib:
                return
            eof = self.controller.library_audio_reached_eof()
            lid = self.controller.lib_audio_cue_id
            handled_attr = "_library_eof_audio"
        else:
            eof = self.controller.library_video_reached_eof()
            lid = self.controller.video_cue_id if self.controller.video_from_library else None
            handled_attr = "_library_eof_video"
        if not eof:
            setattr(self, handled_attr, None)
            return
        cue = self._find_cue(lid)
        if cue is None or cue not in self.project.library or cue.type != kind:
            return
        mode = self.project.library_play_mode(cue_category_key(cue))
        if mode not in (LIB_PLAY_SEQ, LIB_PLAY_ALL):
            return
        if getattr(self, handled_attr) == lid:
            return
        setattr(self, handled_attr, lid)
        nxt = next_library_in_category(
            self.project.library,
            cue,
            wrap=mode == LIB_PLAY_ALL,
            playable=lambda item: not self.media_missing(item),
        )
        if nxt is None:
            return
        selected = self.current_library_cue()
        if selected is None or selected.id == cue.id:
            self._select_library_cue(nxt.id)
            self.fill_inspector()
        self._play_library_cue(nxt, autoplay=True)
        setattr(self, handled_attr, nxt.id)

    def play_library_item(self) -> None:
        self.on_library_play()

    def on_library_play(self) -> None:
        """与节目单主按钮相同：按当前选中条走预览/播放/重播。"""
        cue = self.current_library_cue()
        if cue is None or cue.type not in ("audio", "video"):
            QMessageBox.information(self, "素材库", "请先选中一首音频或视频。")
            return
        self._play_library_cue(cue, autoplay=False)
        self._mark_show_go()
        from src.show_log import log as show_log

        show_log("素材库播放", f"{cue.type}\t{cue.name}")
        self._refresh_status()

    def on_library_pause(self) -> None:
        self.controller.toggle_library_pause()
        self._refresh_status()

    def on_library_stop(self) -> None:
        """主停止：临时垫乐和临时视频一起停。"""
        bed = bool(self.controller.audio_from_library or self.controller._fading_lib)
        vid = bool(
            self.controller.video_from_library
            and self.controller.video is not None
            and self.controller.video.alive
        )
        if bed:
            self._start_fade(library=True)
        if vid:
            self.controller.exit_video()
            self._refresh_status()

    def on_library_stop_bed(self) -> None:
        if self.controller.audio_from_library or self.controller._fading_lib:
            self._start_fade(library=True)

    def on_library_stop_video(self) -> None:
        if self.controller.video_from_library:
            self.controller.exit_video()
            self._refresh_status()

    def on_library_stage(self) -> None:
        cue = self.current_library_cue()
        self._apply_player_config()
        if cue is not None and cue.type == "video":
            media = self.media_for(cue)
            if media is None or not media.exists():
                QMessageBox.warning(self, "没有文件", f"找不到媒体：\n{cue.path or '（空路径）'}")
                return
            self.controller.stage_video(cue, media, from_library=True)
        elif self.controller.video_from_library:
            self.controller.stage_loaded_video()
        else:
            QMessageBox.information(self, "全屏", "请先在素材库选中一条视频。")
        self._refresh_status()

    def on_library_unstage(self) -> None:
        self.controller.unstage_video()
        self._refresh_status()

    def _on_library_audio_seek(self, ratio: float) -> None:
        self._library_seeking_audio = True
        self.controller.seek_library_audio_fraction(ratio)
        self.library_audio_bar.setValue(max(0, min(1000, int(ratio * 1000))))
        QTimer.singleShot(250, lambda: setattr(self, "_library_seeking_audio", False))

    def _on_library_video_seek(self, ratio: float) -> None:
        self._library_seeking_video = True
        self.controller.seek_library_video_fraction(ratio)
        self.library_video_bar.setValue(max(0, min(1000, int(ratio * 1000))))
        QTimer.singleShot(250, lambda: setattr(self, "_library_seeking_video", False))

    def _end_library_seek(self) -> None:
        self._library_seeking_audio = False
        self._library_seeking_video = False

    def _refresh_library_audio_transport(self) -> None:
        """按钮跟「当前选中」走（与节目单底栏同一套 go_action 逻辑）。"""
        if not hasattr(self, "library_audio_bar"):
            return
        cue = self.current_library_cue()
        action = self.controller.go_action(cue, from_library=True)
        go_text = {
            "preview": "播放",
            "play": "播放",
            "playing": "播放中",
            "replay": "重新播放",
            "disabled": "播放",
        }.get(action, "播放")
        self._set_btn(self.library_audio_play, go_text, "libGoBtn")
        media_ok = cue is not None and cue.type in ("audio", "video")
        self.library_audio_play.setEnabled(media_ok and action != "disabled")

        lib_live = self.controller.library_pause_targets()
        if self.controller.is_library_paused():
            self._set_btn(self.library_audio_pause, "继续", "libResumeBtn")
        else:
            self._set_btn(self.library_audio_pause, "暂停", "libPauseBtn")
        self.library_audio_pause.setEnabled(bool(lib_live))

        bed_on = bool(self.controller.audio_from_library)
        lib_video_on = bool(
            self.controller.video_from_library
            and self.controller.video is not None
            and self.controller.video.alive
        )
        self._set_btn(self.library_audio_stop, "停止", "libStopBtn")
        self.library_audio_stop.setEnabled(bed_on or lib_video_on or self.controller._fading)
        self.library_audio_stop.setToolTip("素材库音频和视频一起停")
        if hasattr(self, "library_stop_bed_btn"):
            self.library_stop_bed_btn.setEnabled(bed_on or self.controller._fading_lib)
            self.library_stop_video_btn.setEnabled(lib_video_on)

        staged = bool(self.controller.video_on_stage)
        selected_video = bool(cue and cue.type == "video")
        self._set_btn(
            self.library_stage_btn,
            "已全屏" if staged and selected_video and self.controller.video_from_library else "全屏",
            "libStageBtn",
        )
        self.library_stage_btn.setEnabled(selected_video)
        self.library_unstage_btn.setEnabled(staged and self.controller.video_from_library)

        tag_map = {
            "playing": "播放中",
            "paused": "已暂停",
            "preview": "预监",
            "cover": "封面",
        }
        parts: list[str] = []
        aid, astate = self.controller.live_audio_state()
        if aid:
            parts.append(f"音频{tag_map.get(astate, '播放中')}：{self.controller.lib_audio_name or '（未命名）'}")
        vid, vstate = self.controller.live_library_video_state()
        if vid:
            parts.append(f"视频{tag_map.get(vstate, '播放中')}：{self.controller.video_name or '（未命名）'}")
        if cue is not None and cue.id not in {aid, vid}:
            parts.append(f"选中：{cue.name or cue.label()}")
        if parts:
            self.library_audio_now.setText("　".join(parts))
        elif cue is not None:
            self.library_audio_now.setText(f"选中·{cue.label()}：{cue.name or '（未命名）'}")
        else:
            self.library_audio_now.setText("素材库：未选中")

        # 音量显示（拖动中不打断）
        lib_vol = int(round(self.controller.library_volume))
        if (
            hasattr(self, "library_volume_slider")
            and not self.library_volume_slider.isSliderDown()
            and self.library_volume_slider.value() != lib_vol
        ):
            self._library_volume_user = True
            self.library_volume_slider.setValue(lib_vol)
            self._library_volume_user = False
        if hasattr(self, "library_volume_label"):
            if self.controller.ducked and self.controller.audio_from_library:
                self.library_volume_label.setText(f"音量 {lib_vol}·压低")
            else:
                self.library_volume_label.setText(f"音量 {lib_vol}")

        a_pos, a_dur = self.controller.audio_progress()
        audio_live = bool(self.controller.audio_from_library or a_pos is not None)
        if hasattr(self, "library_audio_row"):
            self.library_audio_row.setVisible(audio_live)
            self.library_audio_time.setVisible(audio_live)
        if not self._library_seeking_audio:
            self.library_audio_time.setText(f"{self._fmt_clock(a_pos)} / {self._fmt_clock(a_dur)}")
            a_ok = a_dur is not None and a_dur > 0 and not self.controller._fading_lib
            self.library_audio_bar.setEnabled(bool(a_ok))
            if a_pos is None or a_dur is None or a_dur <= 0:
                self.library_audio_bar.setValue(0)
            else:
                self.library_audio_bar.setValue(max(0, min(1000, int(a_pos / a_dur * 1000))))
        v_pos, v_dur = self.controller.library_video_progress()
        video_live = bool(
            (
                self.controller.video_from_library
                and self.controller.video is not None
                and self.controller.video.alive
            )
            or v_pos is not None
        )
        if hasattr(self, "library_video_row"):
            self.library_video_row.setVisible(video_live)
            self.library_video_time.setVisible(video_live)
        if hasattr(self, "library_video_bar") and not self._library_seeking_video:
            self.library_video_time.setText(f"{self._fmt_clock(v_pos)} / {self._fmt_clock(v_dur)}")
            v_ok = v_dur is not None and v_dur > 0
            self.library_video_bar.setEnabled(bool(v_ok))
            if v_pos is None or v_dur is None or v_dur <= 0:
                self.library_video_bar.setValue(0)
            else:
                self.library_video_bar.setValue(max(0, min(1000, int(v_pos / v_dur * 1000))))
        if hasattr(self, "library_vol_row"):
            self.library_vol_row.setVisible(audio_live or video_live)

    def delete_library_item(self) -> None:
        cue = self.current_library_cue()
        if cue is None:
            return
        label = cue.name or cue.label()
        box = QMessageBox(self)
        box.setWindowTitle("确认删除")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"删除素材「{label}」？")
        yes = box.addButton("删除", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(yes)
        box.exec()
        if box.clickedButton() != yes:
            return
        self._push_undo()
        kind = cue.type
        self.project.library = [item for item in self.project.library if item.id != cue.id]
        self.project.mark_dirty()
        self._focus = "library"
        self._library_focus = kind
        # 删后尽量停在同分类下一首；没有则不强制选标题行
        next_id = None
        for item in self.project.library:
            if item.type != kind:
                continue
            if (item.category or "").strip() != (cue.category or "").strip():
                continue
            next_id = item.id
            break
        if next_id is None:
            for item in self.project.library:
                if item.type == kind:
                    next_id = item.id
                    break
        self.reload_library(kind, keep_id=next_id)
        self.reload_table(self.current_row())
        self.fill_inspector()
        self._refresh_status()

    def add_note(self) -> None:
        if self._cues_locked:
            QMessageBox.information(self, "节目单已锁定", "先取消「工程 → 锁定节目单」再改条目。")
            return
        self._insert_after_current(Cue(id=new_id(), name="备注", type="note"))

    def _insert_after_current(self, cue: Cue) -> None:
        self._push_undo()
        self._focus_cues()
        row = self.current_row()
        at = row + 1 if row >= 0 else len(self.project.cues)
        self.project.cues.insert(at, cue)
        self.project.mirror_show_cue(cue)
        self.project.mark_dirty()
        self.reload_table(at)
        self.reload_library()

    def on_row_dropped(self, source: int, dest: int) -> None:
        if self._cues_locked:
            return
        self._push_undo()
        cues = self.project.cues
        if not (0 <= source < len(cues)):
            return
        dest = max(0, min(dest, len(cues)))
        item = cues.pop(source)
        if dest > source:
            dest -= 1
        dest = max(0, min(dest, len(cues)))
        cues.insert(dest, item)
        self.project.mark_dirty()
        self.reload_table(dest)

    def browse_media(self) -> None:
        cue = self.active_cue()
        if cue is None or cue.type not in ("audio", "video"):
            return
        if not self._ensure_project():
            return
        filt = AUDIO_FILTER if cue.type == "audio" else VIDEO_FILTER
        path, _ = QFileDialog.getOpenFileName(self, "选择媒体", str(self.project.directory), filt)
        if not path:
            return
        cue.path = self.project.store_path(Path(path))
        if not cue.name or cue.name in ("音频", "视频"):
            cue.name = Path(path).stem
        if self._focus != "library":
            self.project.mirror_show_cue(cue)
        self.project.mark_dirty()
        if self._focus == "library":
            self.reload_library("audio", keep_id=cue.id)
            self.fill_inspector()
        else:
            self.reload_table(self.current_row())
            self.reload_library()

    def on_table_arrow(self, key: int) -> None:
        if key == Qt.Key.Key_Left:
            self.controller.seek_relative(-5)
        elif key == Qt.Key.Key_Right:
            self.controller.seek_relative(5)
        elif key == Qt.Key.Key_Up:
            self._apply_volume(self.controller.nudge_volume(5))
        elif key == Qt.Key.Key_Down:
            self._apply_volume(self.controller.nudge_volume(-5))

    def delete_cue(self) -> None:
        if self._focus == "library":
            self.delete_library_item()
            return
        if self._cues_locked:
            QMessageBox.information(self, "节目单已锁定", "先取消「工程 → 锁定节目单」再删条目。")
            return
        row = self.current_row()
        if row < 0:
            return
        self._push_undo()
        cue = self.project.cues[row]
        label = cue.name or cue.label()
        box = QMessageBox(self)
        box.setWindowTitle("确认删除")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(f"删除第 {row + 1} 条「{label}」？")
        yes = box.addButton("删除", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(yes)
        box.exec()
        if box.clickedButton() != yes:
            return
        del self.project.cues[row]
        self.project.drop_show_mirrors(cue.id)
        self.project.mark_dirty()
        self.reload_table(min(row, len(self.project.cues) - 1))
        self.reload_library()

    def move_cue(self, delta: int) -> None:
        row = self.current_row()
        dest = row + delta
        if row < 0 or not (0 <= dest < len(self.project.cues)):
            return
        cues = self.project.cues
        cues[row], cues[dest] = cues[dest], cues[row]
        self.project.mark_dirty()
        self.reload_table(dest)

    def on_new_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getSaveFileName(self, "新建工程", str(Path.home() / "某场活动.json"), "工程 (*.json)")
        if not path:
            return
        self._adopt_project(Project.create(Path(path)))
        self._remember_project(self.project.path)
        self.reload_table()

    def on_open_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "打开工程", str(Path.home()), "工程 (*.json)")
        if not path:
            return
        try:
            self._adopt_project(Project.load(Path(path)))
            self._drop_stop_cues()
            self._remember_project(self.project.path)
        except Exception as exc:
            QMessageBox.warning(self, "打开失败", str(exc))
            return
        self.reload_table()

    def on_save_project(self) -> None:
        if self.project.path is None:
            self.on_save_project_as()
            return
        self.project.save()
        self._remember_project(self.project.path)
        self.reload_table(self.current_row())

    def on_save_project_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "另存为", str(Path.home() / "某场活动.json"), "工程 (*.json)")
        if not path:
            return
        self.project.save(Path(path))
        self._remember_project(self.project.path)
        self.reload_table(self.current_row())

    def _apply_player_config(self) -> None:
        preview = self._preview_screen_index()
        self.controller.configure(
            self.settings.resolved_mpv(),
            self.settings.projection_screen,
            preview,
            audio_device=self.settings.audio_device,
        )
        video = self.controller.video
        if self.controller.video_on_stage and video is not None and video.alive:
            try:
                video.set("fs-screen", self.settings.projection_screen)
                video.set("screen", self.settings.projection_screen)
            except Exception:
                pass

    def _preview_screen_index(self) -> int:
        """控场窗口所在屏（必须与 mpv fs-screen 同一套 EnumDisplayMonitors 下标）。

        不能用 Qt screens().index()：Qt 顺序经常和 Windows/mpv 不一致，
        会导致「本软件」标错，选了本软件却全屏到另一块。
        """
        displays = list_windows_displays()
        if not displays:
            return 0

        # 1) 窗口句柄 → MonitorFromWindow（最准）
        try:
            hwnd = int(self.winId())
        except Exception:
            hwnd = 0
        idx = display_index_for_hwnd(hwnd, displays) if hwnd else None
        if idx is not None:
            return idx

        # 2) 窗口中心点落在哪块屏
        try:
            geo = self.frameGeometry()
            cx = int(geo.x() + geo.width() / 2)
            cy = int(geo.y() + geo.height() / 2)
            idx = display_index_for_point(cx, cy, displays)
            if idx is not None:
                return idx
        except Exception:
            pass

        # 3) Qt 屏名 ↔ 设备名（仍可能失败，只作兜底）
        current = self.screen()
        if current is not None:
            name = (current.name() or "").strip()
            for item in displays:
                if not name:
                    break
                if item.device == name or item.short_device == name:
                    return item.index
                if name.endswith(item.short_device) or item.device.endswith(name):
                    return item.index
            # 4) Qt 屏几何中心
            try:
                sg = current.geometry()
                idx = display_index_for_point(
                    int(sg.x() + sg.width() / 2),
                    int(sg.y() + sg.height() / 2),
                    displays,
                )
                if idx is not None:
                    return idx
            except Exception:
                pass

        for item in displays:
            if item.primary:
                return item.index
        return 0

    def _ensure_project(self) -> bool:
        if self.project.path is not None:
            return True
        QMessageBox.information(self, "先保存工程", "先新建或打开一份工程，媒体路径才能相对工程目录保存。")
        self.on_new_project()
        return self.project.path is not None

    def _confirm_discard(self) -> bool:
        if not self.project.dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("未保存")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("当前工程有未保存的改动，是否保存？")
        save = box.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("不保存", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save)
        box.exec()
        clicked = box.clickedButton()
        if clicked == cancel:
            return False
        if clicked == save:
            self.on_save_project()
            return not self.project.dirty
        return True

    def _editing_text(self) -> bool:
        focus = self.focusWidget()
        return isinstance(focus, (QLineEdit, QPlainTextEdit))

    @staticmethod
    def _fmt_clock(seconds: float | None) -> str:
        if seconds is None:
            return "--:--"
        total = max(0, int(seconds))
        if total >= 3600:
            return f"{total // 3600}:{total % 3600 // 60:02d}:{total % 60:02d}"
        return f"{total // 60:02d}:{total % 60:02d}"

    def _on_seek(self, ratio: float) -> None:
        self._seeking = True
        self.controller.seek_fraction(ratio)
        self.progress_bar.setValue(max(0, min(1000, int(ratio * 1000))))
        QTimer.singleShot(250, self._end_seek)

    def _end_seek(self) -> None:
        self._seeking = False

    def _on_volume_changed(self, value: int) -> None:
        if self._volume_user:
            return
        self.controller.set_volume(value)
        self.volume_label.setText(f"音量 {value}")
        self.settings.output_volume = value
        self._layout_timer.start()

    def _on_library_volume_changed(self, value: int) -> None:
        if self._library_volume_user:
            return
        self.controller.set_library_volume(value)
        self.library_volume_label.setText(f"音量 {value}")
        self.settings.library_volume = value
        self._layout_timer.start()

    def _apply_volume(self, value: int | None) -> None:
        if value is None:
            return
        self._volume_user = True
        self.volume_slider.setValue(int(value))
        self._volume_user = False
        self.volume_label.setText(f"音量 {int(value)}")
        self.settings.output_volume = int(value)
        self._refresh_status()

    def _apply_library_volume(self, value: int | None) -> None:
        if value is None:
            return
        self._library_volume_user = True
        if hasattr(self, "library_volume_slider"):
            self.library_volume_slider.setValue(int(value))
        self._library_volume_user = False
        if hasattr(self, "library_volume_label"):
            self.library_volume_label.setText(f"音量 {int(value)}")
        self.settings.library_volume = int(value)
        self._refresh_status()

    def _refresh_progress(self, st) -> None:
        if self._seeking:
            return
        pos = st.position
        dur = st.duration
        self.progress_time.setText(f"{self._fmt_clock(pos)} / {self._fmt_clock(dur)}")
        seekable = dur is not None and dur > 0 and not self.controller._fading_show
        self.progress_bar.setEnabled(bool(seekable))
        live = self._find_cue(self.controller.live_cue_state()[0])
        mark_cue = live if live in self.project.cues else self.current_cue()
        if mark_cue is not None and dur and dur > 0:
            self.progress_bar.mark_in = mark_cue.trim_in / dur if mark_cue.trim_in > 0 else 0.0
            self.progress_bar.mark_out = mark_cue.trim_out / dur if mark_cue.trim_out > 0 else 0.0
        else:
            self.progress_bar.mark_in = 0.0
            self.progress_bar.mark_out = 0.0
        if pos is None or dur is None or dur <= 0:
            self.progress_bar.setValue(0)
            self.progress_bar.update()
            return
        self.progress_bar.setValue(max(0, min(1000, int(pos / dur * 1000))))
        self.progress_bar.update()

    def _set_btn(self, btn: QPushButton, text: str, name: str) -> None:
        if btn.text() != text or btn.objectName() != name:
            btn.setText(text)
            btn.setObjectName(name)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _refresh_transport_labels(self, cue: Cue | None) -> None:
        action = self.controller.go_action(cue)
        go_text = {
            "preview": "预览",
            "play": "播放",
            "playing": "播放中",
            "replay": "重新播放",
            "disabled": "播放",
        }.get(action, "播放")
        self._set_btn(self.go_btn, go_text, "goBtn")
        media = cue is not None and cue.type in ("audio", "video")
        self.go_btn.setEnabled(media and action != "disabled")
        live = self.controller.pause_targets()
        if self.controller.is_paused(cue):
            self._set_btn(self.pause_btn, "继续", "resumeBtn")
        else:
            self._set_btn(self.pause_btn, "暂停", "pauseBtn")
        staged = bool(self.controller.video_on_stage and not self.controller.video_from_library)
        selected_video = bool(cue and cue.type == "video")
        self._set_btn(self.stage_btn, "已全屏" if staged and selected_video else "全屏", "stageBtn")
        main_audio = (
            self.controller.audio is not None
            and self.controller.audio.alive
            and self.controller._is_active(self.controller.audio)
        )
        main_video = (
            self.controller.video is not None
            and self.controller.video.alive
            and not self.controller.video_from_library
        )
        self.stop_btn.setEnabled(main_audio or main_video)
        self.pause_btn.setEnabled(bool(live))
        self.stage_btn.setEnabled(selected_video)
        self.unstage_btn.setEnabled(staged)
        if hasattr(self, "mute_btn"):
            muted = self.controller.master_muted
            self._set_btn(self.mute_btn, "取消静音" if muted else "静音", "muteOnBtn" if muted else "muteBtn")
            ducked = self.controller.ducked
            self._set_btn(self.duck_btn, "恢复音频" if ducked else "压低音频", "duckOnBtn" if ducked else "duckBtn")
            has_cover = bool((self.project.hold_cover or "").strip())
            if self.controller.hold_active:
                self._set_btn(self.hold_btn, "收起封面" if has_cover else "取消黑场", "holdOnBtn")
            else:
                self._set_btn(self.hold_btn, "封面" if has_cover else "黑场", "holdBtn")

    def _refresh_status(self) -> None:
        self._maybe_advance_library()
        self._maybe_hold_cover()
        st = self.controller.status()
        playing = bool(
            self.controller.live_cue_state()[0]
            or self.controller.live_library_state()[0]
            or self.controller._fading
        )
        interval = 100 if playing else 400
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        prev_live = self._live_sig
        self._refresh_progress(st)
        self._refresh_library_audio_transport()
        if (
            st.volume is not None
            and not self.volume_slider.isSliderDown()
            and self.volume_slider.value() != st.volume
        ):
            self._volume_user = True
            self.volume_slider.setValue(st.volume)
            self._volume_user = False
        if st.volume is not None:
            if self.controller.ducked and self.controller._show_audio_on():
                self.volume_label.setText(f"音量 {st.volume}·压低")
            else:
                self.volume_label.setText(f"音量 {st.volume}")
        self._sync_live_row()
        if self._live_sig != prev_live:
            self.table.viewport().update()
            for widget in self._library_lists():
                widget.viewport().update()
        self._update_now_next(st)
        self._update_proj_warn()
        self._refresh_transport_labels(self.current_cue())
        self.table.arrow_eaten = st.video_state != "未加载"
        alert = (st.message or "").strip()
        if not self.settings.resolved_mpv().exists():
            alert = "找不到自带 mpv：请确认 vendor/mpv/mpv.exe 还在"
        if alert:
            self.status_label.setText(alert)
            self.status_label.setVisible(True)
        elif not self.status_label.text().startswith("自动保存失败"):
            self.status_label.clear()
            self.status_label.setVisible(False)

    def bring_to_front(self) -> None:
        self.show()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def force_close(self) -> None:
        self._force_closing = True
        self.controller.shutdown()
        self.close()

    def _restore_window_geometry(self) -> None:
        raw = (self.settings.window_geometry or "").strip()
        if not raw:
            return
        ok = self.restoreGeometry(QByteArray.fromHex(raw.encode("ascii")))
        if not ok:
            self.resize(1280, 800)

    @staticmethod
    def _usable_sizes(sizes: list[int], mins: list[int]) -> bool:
        return len(sizes) == len(mins) and all(value >= minimum for value, minimum in zip(sizes, mins))

    def _restore_splitters(self) -> None:
        if hasattr(self, "main_split") and self._usable_sizes(self.settings.splitter_main, [200, 160, 140]):
            self.main_split.setSizes(self.settings.splitter_main)
        self._layout_ready = True
        self._update_proj_warn()

    def _persist_layout(self) -> None:
        if not self._layout_ready:
            return
        self.settings.window_geometry = bytes(self.saveGeometry().toHex()).decode("ascii")
        if hasattr(self, "main_split"):
            sizes = self.main_split.sizes()
            if self._usable_sizes(sizes, [200, 160, 140]):
                self.settings.splitter_main = sizes
        self.settings.output_volume = int(self.controller.output_volume)
        self.settings.library_volume = int(self.controller.library_volume)
        self.settings.save()

    def _finish_fade(self) -> None:
        self._refresh_status()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._force_closing:
            self._autosave_now()
            if not self._confirm_discard():
                event.ignore()
                return
        self._persist_layout()
        self.controller.shutdown()
        event.accept()
