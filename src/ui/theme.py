from __future__ import annotations

Theme = dict[str, str]

DARK: Theme = {
    "bg": "#121416",
    "panel": "#1b1f23",
    "table": "#16191c",
    "table_alt": "#1a1e22",
    "fg": "#e6e8ea",
    "muted": "#9aa3ab",
    "border": "#2a3036",
    "grid": "#23282e",
    "btn": "#2a3036",
    "btn_hover": "#353c44",
    "btn_pressed": "#1a1e22",
    "add_btn": "#23282d",
    "nav": "#2a333b",
    "nav_hover": "#3a4550",
    "nav_fg": "#e6e8ea",
    "go": "#2aa35c",
    "go_hover": "#34c26e",
    "go_fg": "#06140c",
    "stop": "#d64545",
    "stop_hover": "#ef5555",
    "stop_fg": "#ffffff",
    "disabled_bg": "#3a4046",
    "disabled_fg": "#7a828a",
    "pause": "#5c6570",
    "resume": "#1f8a5b",
    "resume_hover": "#26a56c",
    "resume_fg": "#f4fff8",
    "stage": "#c49214",
    "stage_fg": "#1a1303",
    "unstage": "#6d5b45",
    "select": "#1b6b42",
    "select_fg": "#f4fff8",
    "combo_border": "#3a424a",
    "covers": "#e0a14a",
    "menu_sel": "#2f8f5b",
    "menu_sel_fg": "#08140e",
    "now_bar": "#0e1012",
    "now_card": "#241e12",
    "now_kicker": "#f0b429",
    "now_title": "#ffe9a8",
    "now_notes": "#9aa3ab",
    "now_idle_bg": "#14241c",
    "now_idle_accent": "#34c26e",
    "now_idle_title": "#f4fff8",
    "status_bg": "#0e1012",
    "progress_chunk": "#2aa35c",
    "slider_handle": "#d7e0e6",
    "slider_disabled": "#5a636b",
    "playing": "#d4a017",
    "playing_sel": "#f0b429",
    "playing_fg": "#1a1303",
    "playing_accent": "#7a5a08",
    "paused": "#5c4c22",
    "paused_sel": "#8a7330",
    "paused_fg": "#ffe9a8",
    "paused_accent": "#c9a227",
    "note_bg": "#1c1f22",
    "note_fg": "#8b939b",
    "type_audio": "#6ec8c0",
    "type_video": "#e0a14a",
    "type_note": "#8b939b",
    "missing": "#e07070",
    "missing_live": "#8b1a1a",
    "lib_hover": "#2a3036",
    "lib_notes": "#8b939b",
    "lib_notes_sel": "#b7d4c6",
    "lib_notes_playing": "#6a5420",
    "lib_notes_paused": "#8a7a4a",
    "lib_cat_bg": "#14181c",
    "lib_cat_fg": "#8fb9a3",
}

LIGHT: Theme = {
    "bg": "#f3f4f6",
    "panel": "#ffffff",
    "table": "#ffffff",
    "table_alt": "#eef0f3",
    "fg": "#17191c",
    "muted": "#5e6770",
    "border": "#d2d7de",
    "grid": "#e2e6eb",
    "btn": "#e8ebef",
    "btn_hover": "#dce0e6",
    "btn_pressed": "#cfd4db",
    "add_btn": "#e8ebef",
    "nav": "#2a333b",
    "nav_hover": "#3a4550",
    "nav_fg": "#e6e8ea",
    "go": "#2aa35c",
    "go_hover": "#34c26e",
    "go_fg": "#06140c",
    "stop": "#d64545",
    "stop_hover": "#ef5555",
    "stop_fg": "#ffffff",
    "disabled_bg": "#d8dde3",
    "disabled_fg": "#8b939b",
    "pause": "#5c6570",
    "resume": "#1f8a5b",
    "resume_hover": "#26a56c",
    "resume_fg": "#f4fff8",
    "stage": "#c49214",
    "stage_fg": "#1a1303",
    "unstage": "#6d5b45",
    "select": "#1b6b42",
    "select_fg": "#f4fff8",
    "combo_border": "#c5ccd3",
    "covers": "#c47a10",
    "menu_sel": "#2f8f5b",
    "menu_sel_fg": "#08140e",
    "now_bar": "#eceff2",
    "now_card": "#f7edd0",
    "now_kicker": "#8a6400",
    "now_title": "#3a2a08",
    "now_notes": "#5e6770",
    "now_idle_bg": "#e5f4eb",
    "now_idle_accent": "#1f8a5b",
    "now_idle_title": "#0f2e1c",
    "status_bg": "#eceff2",
    "progress_chunk": "#2aa35c",
    "slider_handle": "#17191c",
    "slider_disabled": "#b0b6bc",
    "playing": "#e0b13a",
    "playing_sel": "#f0b429",
    "playing_fg": "#1a1303",
    "playing_accent": "#7a5a08",
    "paused": "#5c4c22",
    "paused_sel": "#8a7330",
    "paused_fg": "#ffe9a8",
    "paused_accent": "#c9a227",
    "note_bg": "#f0f2f4",
    "note_fg": "#6a727a",
    "type_audio": "#1a8a84",
    "type_video": "#b56b0a",
    "type_note": "#6a727a",
    "missing": "#c42b2b",
    "missing_live": "#8b1a1a",
    "lib_hover": "#e8ebef",
    "lib_notes": "#6a727a",
    "lib_notes_sel": "#b7d4c6",
    "lib_notes_playing": "#6a5420",
    "lib_notes_paused": "#8a7a4a",
    "lib_cat_bg": "#eef2f0",
    "lib_cat_fg": "#2f6b4f",
}

_QSS = """
QMainWindow, QWidget#root {
    background: @bg;
    color: @fg;
    font-family: "Microsoft YaHei UI";
    font-size: 14px;
}
QMenuBar {
    background: @panel;
    color: @fg;
    border-bottom: 1px solid @border;
}
QMenuBar::item:selected { background: @border; }
QMenu { background: @panel; color: @fg; }
QMenu::item:selected { background: @menu_sel; color: @menu_sel_fg; }
QMenuBar QLabel#projLabel {
    color: @muted;
    padding-left: 14px;
    padding-right: 6px;
}
QMenuBar QLabel#projWarn {
    color: @covers;
    padding-left: 8px;
    padding-right: 4px;
    font-weight: 600;
}
QComboBox {
    background: @bg;
    color: @fg;
    border: 1px solid @combo_border;
    padding: 2px 8px;
    min-width: 148px;
    max-width: 200px;
    min-height: 22px;
}
QComboBox#categoryCombo {
    min-width: 80px;
    max-width: 16777215;
    min-height: 28px;
}
QComboBox:hover { border-color: @go; }
QComboBox[covers="true"] { border-color: @covers; color: @covers; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: @panel;
    color: @fg;
    selection-background-color: @select;
    selection-color: @select_fg;
    border: 1px solid @border;
    outline: none;
    padding: 4px;
    min-width: 160px;
}
QPushButton {
    border: none;
    padding: 8px 12px;
    background: @btn;
    color: @fg;
}
QPushButton:hover { background: @btn_hover; }
QPushButton:pressed { background: @btn_pressed; }
QPushButton#addBtn { background: @add_btn; }
QPushButton#navBtn, QPushButton#goBtn, QPushButton#stopBtn,
QPushButton#pauseBtn, QPushButton#resumeBtn, QPushButton#stageBtn,
QPushButton#unstageBtn, QPushButton#muteBtn, QPushButton#muteOnBtn,
QPushButton#holdBtn, QPushButton#holdOnBtn, QPushButton#duckBtn,
QPushButton#duckOnBtn, QPushButton#panicBtn {
    font-size: 18px;
    font-weight: 700;
    min-width: 108px;
    min-height: 72px;
    padding: 8px 14px;
}
QPushButton#navBtn {
    background: @nav;
    color: @nav_fg;
    min-width: 96px;
}
QPushButton#navBtn:hover { background: @nav_hover; }
QPushButton#goBtn {
    background: @go;
    color: @go_fg;
    min-width: 176px;
    font-size: 22px;
}
QPushButton#goBtn:hover { background: @go_hover; }
QPushButton#goBtn:disabled {
    background: @disabled_bg;
    color: @disabled_fg;
}
QPushButton#stopBtn {
    background: @stop;
    color: @stop_fg;
}
QPushButton#stopBtn:hover { background: @stop_hover; }
QPushButton#stopBtn:disabled,
QPushButton#pauseBtn:disabled,
QPushButton#resumeBtn:disabled,
QPushButton#stageBtn:disabled,
QPushButton#unstageBtn:disabled,
QPushButton#muteBtn:disabled,
QPushButton#holdBtn:disabled,
QPushButton#duckBtn:disabled {
    background: @disabled_bg;
    color: @disabled_fg;
}
QPushButton#pauseBtn {
    background: @pause;
    color: @stop_fg;
}
QPushButton#resumeBtn {
    background: @resume;
    color: @resume_fg;
}
QPushButton#resumeBtn:hover { background: @resume_hover; }
QPushButton#stageBtn {
    background: @stage;
    color: @stage_fg;
}
QPushButton#unstageBtn {
    background: @unstage;
    color: @stop_fg;
}
QPushButton#panicBtn {
    background: #8a1f1f;
    color: #fff;
}
QPushButton#panicBtn:hover { background: @stop; }
QLabel#hotkeyBar, QPushButton#showClock {
    color: @muted;
    font-size: 12px;
    font-weight: 600;
}
QLabel#nextKicker {
    color: @muted;
    font-size: 12px;
    font-weight: 700;
}
QLabel#nextTitle {
    color: @fg;
    font-size: 20px;
    font-weight: 800;
}
QLabel#projStatus {
    color: @now_kicker;
    font-size: 13px;
    font-weight: 700;
}
QLabel#vuKicker {
    color: @muted;
    font-size: 11px;
    font-weight: 700;
}
QLabel#vuLabel {
    color: @muted;
    font-size: 11px;
}
QProgressBar#vuBar {
    background: @bg;
    border: 1px solid @border;
    min-height: 8px;
    max-height: 10px;
}
QProgressBar#vuBar::chunk { background: @go; }
QFrame#nextCard {
    background: @panel;
    border-left: 4px solid @border;
}
QPushButton#muteBtn, QPushButton#holdBtn, QPushButton#duckBtn {
    min-width: 88px;
    font-size: 16px;
}
QPushButton#muteOnBtn {
    background: @stop;
    color: @stop_fg;
    min-width: 88px;
    font-size: 16px;
}
QPushButton#holdOnBtn {
    background: @stage;
    color: @stage_fg;
    min-width: 88px;
    font-size: 16px;
}
QPushButton#duckOnBtn {
    background: @resume;
    color: @resume_fg;
    min-width: 88px;
    font-size: 16px;
}
/* 临时区操作键：样式同底栏，尺寸更紧凑，文字居中 */
QPushButton#libGoBtn, QPushButton#libStopBtn, QPushButton#libPauseBtn,
QPushButton#libResumeBtn, QPushButton#libStageBtn, QPushButton#libUnstageBtn {
    font-size: 14px;
    font-weight: 700;
    min-width: 0;
    min-height: 36px;
    max-height: 40px;
    padding: 0 6px;
    text-align: center;
}
QPushButton#libGoBtn {
    background: @go;
    color: @go_fg;
}
QPushButton#libGoBtn:hover { background: @go_hover; }
QPushButton#libGoBtn:disabled {
    background: @disabled_bg;
    color: @disabled_fg;
}
QPushButton#libStopSplitBtn {
    font-size: 13px;
    font-weight: 700;
    min-width: 0;
    min-height: 28px;
    max-height: 30px;
    padding: 0 6px;
    text-align: center;
    background: @unstage;
    color: @stop_fg;
}
QPushButton#libStopSplitBtn:hover { background: @stop; }
QPushButton#libStopSplitBtn:disabled {
    background: @disabled_bg;
    color: @disabled_fg;
}
QPushButton#libStopBtn {
    background: @stop;
    color: @stop_fg;
}
QPushButton#libPauseBtn {
    background: @pause;
    color: @stop_fg;
}
QPushButton#libResumeBtn {
    background: @resume;
    color: @resume_fg;
}
QPushButton#libStageBtn {
    background: @stage;
    color: @stage_fg;
}
QPushButton#libUnstageBtn {
    background: @unstage;
    color: @stop_fg;
}
QPushButton#libStopBtn:disabled, QPushButton#libPauseBtn:disabled,
QPushButton#libResumeBtn:disabled, QPushButton#libStageBtn:disabled,
QPushButton#libUnstageBtn:disabled {
    background: @disabled_bg;
    color: @disabled_fg;
}
QWidget#libModeHost {
    background: transparent;
}
QPushButton#libModeBtn {
    font-size: 12px;
    font-weight: 600;
    min-width: 72px;
    max-width: 92px;
    min-height: 24px;
    max-height: 24px;
    padding: 0 6px;
    background: @add_btn;
    color: @lib_cat_fg;
    border: 1px solid @border;
    border-radius: 3px;
}
QPushButton#libModeBtn:hover { background: @btn_hover; }
QPushButton#libModeBtn[mode="repeat_one"],
QPushButton#libModeBtn[mode="sequence"],
QPushButton#libModeBtn[mode="repeat_all"] {
    border-color: @go;
    color: @go;
}
QTableWidget {
    background: @table;
    alternate-background-color: @table_alt;
    color: @fg;
    gridline-color: @grid;
    border: 1px solid @border;
    outline: none;
}
QTableWidget::item {
    color: @fg;
    padding-left: 6px;
}
QTableWidget::item:selected {
    background: @select;
    color: @select_fg;
}
QHeaderView::section {
    background: @panel;
    color: @muted;
    border: none;
    border-right: 1px solid @border;
    border-bottom: 1px solid @border;
    padding: 8px;
    font-weight: 600;
}
QLineEdit, QPlainTextEdit {
    background: @bg;
    color: @fg;
    border: 1px solid @border;
    padding: 6px;
}
QCheckBox { color: @fg; }
QLabel { color: @fg; }
QLabel#status {
    background: @status_bg;
    border-top: 1px solid @border;
    padding: 10px 14px;
    font-size: 15px;
    font-family: "Consolas", "Microsoft YaHei UI";
}
QLabel#hint, QLabel#secTitle { color: @muted; }
QFrame#nowNext {
    background: @now_bar;
    border-top: 1px solid @border;
}
QFrame#nowCard {
    background: @now_card;
    border-left: 4px solid @now_kicker;
}
QLabel#nowKicker {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
    color: @now_kicker;
}
QLabel#nowTitle {
    color: @now_title;
    font-size: 22px;
    font-weight: 700;
}
QLabel#nowRemain {
    color: @now_kicker;
    font-size: 28px;
    font-weight: 700;
    font-family: "Consolas", "Microsoft YaHei UI";
}
QLabel#nowNotes {
    color: @now_notes;
    font-size: 16px;
}
QFrame#inspector, QFrame#library {
    background: @panel;
    border-left: 1px solid @border;
}
QTableWidget#libraryList {
    background: @table;
    color: @fg;
    border: 1px solid @border;
    outline: none;
    gridline-color: @grid;
}
QTableWidget#libraryList::item:selected {
    background: @select;
    color: @select_fg;
}
QFrame#transport {
    background: @panel;
    border-top: 1px solid @border;
}
QProgressBar#mediaProgress {
    background: @bg;
    border: 1px solid @border;
    min-height: 18px;
    max-height: 18px;
    min-width: 0;
    padding: 0;
    margin: 0;
    border-radius: 3px;
    text-align: left;
}
QProgressBar#mediaProgress::chunk {
    background: @progress_chunk;
    margin: 0;
    border-radius: 2px;
}
QLabel#libSeekTag {
    color: @fg;
    font-size: 13px;
    font-weight: 700;
    min-width: 0;
    max-width: 36px;
}
QLabel#libSeekTime {
    color: @fg;
    font-family: "Consolas", "Microsoft YaHei UI";
    font-size: 13px;
    font-weight: 700;
    min-width: 0;
}
QLabel#progressTime {
    color: @fg;
    font-family: "Consolas", "Microsoft YaHei UI";
    font-size: 16px;
    font-weight: 700;
    min-width: 148px;
}
QLabel#volumeLabel {
    color: @muted;
    font-size: 13px;
    min-width: 64px;
}
QSlider#volumeSlider::groove:horizontal {
    background: @bg;
    border: 1px solid @border;
    height: 8px;
    border-radius: 3px;
}
QSlider#volumeSlider::sub-page:horizontal {
    background: @progress_chunk;
    border-radius: 3px;
}
QSlider#volumeSlider::handle:horizontal {
    background: @slider_handle;
    width: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider#volumeSlider:disabled::handle:horizontal {
    background: @slider_disabled;
}
QSlider#volumeSlider:disabled::sub-page:horizontal {
    background: @disabled_bg;
}
"""


def normalize_theme(raw: object) -> str:
    text = str(raw or "dark").strip().lower()
    if text in ("light", "white", "白", "白色"):
        return "light"
    return "dark"


def theme_colors(name: str) -> Theme:
    return LIGHT if name == "light" else DARK


def stylesheet(name: str) -> str:
    colors = theme_colors(name)
    text = _QSS
    for key in sorted(colors, key=len, reverse=True):
        text = text.replace("@" + key, colors[key])
    return text
