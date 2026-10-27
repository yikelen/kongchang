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

# The desktop console uses the same neutral player palette in both themes.
# Keep the semantic live, paused and warning colors distinct for show operation.
DARK.update({
    "bg": "#17171b", "panel": "#202024", "table": "#202024", "table_alt": "#242428",
    "fg": "#f3f2f4", "muted": "#b1adb5", "border": "#39383d", "grid": "#343338",
    "btn": "#323136", "btn_hover": "#414046", "btn_pressed": "#29282d", "add_btn": "#323136",
    "nav": "#29282d", "nav_hover": "#414046", "nav_fg": "#f3f2f4",
    "go": "#f3f2f4", "go_hover": "#ffffff", "go_fg": "#202024",
    "stop": "#ac4856", "stop_hover": "#c95b69", "stop_fg": "#ffffff",
    "disabled_bg": "#2c2b30", "disabled_fg": "#8d8990",
    "pause": "#39383d", "resume": "#386c62", "resume_hover": "#468579", "resume_fg": "#ffffff",
    "stage": "#cba369", "stage_fg": "#2c2114", "unstage": "#514e52",
    "select": "#53343d", "select_fg": "#ffffff", "combo_border": "#514e54",
    "covers": "#e3aa5e", "menu_sel": "#6f3b49", "menu_sel_fg": "#ffffff",
    "now_bar": "#202024", "now_card": "#343338", "now_kicker": "#f18a9b", "now_title": "#ffffff",
    "now_notes": "#bdb9c0", "now_idle_bg": "#29282d", "now_idle_accent": "#c0b9bd",
    "now_idle_title": "#f7f5f6", "status_bg": "#202024", "progress_chunk": "#f18a9b",
    "slider_handle": "#f7f5f6", "slider_disabled": "#77747a",
    "playing": "#765b36", "playing_sel": "#8a6c40", "playing_fg": "#fff6e5", "playing_accent": "#f1c67c",
    "paused": "#514d40", "paused_sel": "#67604b", "paused_fg": "#fff1d5", "paused_accent": "#dfbd7c",
    "note_bg": "#242428", "note_fg": "#b8b4bc", "type_audio": "#ec8396", "type_video": "#e5ba7c",
    "type_note": "#aaa6ad", "missing": "#f2949f", "missing_live": "#ffe2e5", "lib_hover": "#39383e",
    "lib_notes": "#aaa6ad", "lib_notes_sel": "#f0ccd3", "lib_notes_playing": "#fff2dd",
    "lib_notes_paused": "#fff1d5", "lib_cat_bg": "#29282d", "lib_cat_fg": "#dbbdc6",
})
LIGHT.update({
    "bg": "#f1eff1", "panel": "#ffffff", "table": "#ffffff", "table_alt": "#f8f6f8",
    "fg": "#252328", "muted": "#69636b", "border": "#dedade", "grid": "#e9e6e9",
    "btn": "#efedef", "btn_hover": "#e2dfe3", "btn_pressed": "#d8d3d8", "add_btn": "#efedef",
    "nav": "#efedef", "nav_hover": "#e2dfe3", "nav_fg": "#29272b",
    "go": "#262429", "go_hover": "#464249", "go_fg": "#ffffff",
    "stop": "#aa3444", "stop_hover": "#c34757", "stop_fg": "#ffffff",
    "disabled_bg": "#ece9ec", "disabled_fg": "#827d83",
    "pause": "#6d6870", "resume": "#35765f", "resume_hover": "#438a71", "resume_fg": "#ffffff",
    "stage": "#e3c285", "stage_fg": "#30220d", "unstage": "#68626a",
    "select": "#f7dce3", "select_fg": "#48232e", "combo_border": "#cdc7cd",
    "covers": "#a36212", "menu_sel": "#f5d8e0", "menu_sel_fg": "#48232e",
    "now_bar": "#ffffff", "now_card": "#f8e9eb", "now_kicker": "#aa3d54", "now_title": "#2b2024",
    "now_notes": "#69636b", "now_idle_bg": "#f3f0f2", "now_idle_accent": "#a2495c",
    "now_idle_title": "#262429", "status_bg": "#ffffff", "progress_chunk": "#c34560",
    "slider_handle": "#302b31", "slider_disabled": "#b5afb6", "playing": "#f3d8a4",
    "playing_sel": "#eec984", "playing_fg": "#3c2a12", "playing_accent": "#8d5b1b",
    "paused": "#e9e0cf", "paused_sel": "#dfd1b7", "paused_fg": "#46371e", "paused_accent": "#93703f",
    "note_bg": "#f6f4f6", "note_fg": "#6e686f", "type_audio": "#a33950", "type_video": "#a45c1f",
    "type_note": "#6e686f", "missing": "#b02c3a", "missing_live": "#8b1a1a", "lib_hover": "#efedef",
    "lib_notes": "#6e686f", "lib_notes_sel": "#60434b", "lib_notes_playing": "#57411e",
    "lib_notes_paused": "#564a32", "lib_cat_bg": "#f2eef1", "lib_cat_fg": "#76505d",
})

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

/* Modern console surfaces; the original semantic controls remain separate. */
QMainWindow, QWidget#root { font-family: "Microsoft YaHei UI", "Segoe UI"; }
QMenuBar { background: @bg; border: none; padding: 4px 10px; }
QMenuBar::item { padding: 6px 9px; border-radius: 5px; }
QMenu { border: 1px solid @border; border-radius: 8px; padding: 5px; }
QMenu::item { padding: 7px 22px; border-radius: 5px; }
QWidget#workspace, QWidget#footerWrap { background: @bg; }
QFrame#cuePanel, QFrame#sidePanel, QFrame#transport, QFrame#nowNext {
    background: @panel; border: none; border-radius: 12px;
}
QFrame#topBar, QFrame#library, QFrame#inspector { background: @panel; border: none; }
QFrame#libraryBed { background: @panel; border: none; border-top: 1px solid @grid; }
QTabWidget#sideTabs::pane { background: @panel; border: none; }
QTabWidget#sideTabs::tab-bar { left: 18px; }
QTabBar::tab { background: transparent; color: @muted; padding: 13px 15px 10px; border: none; border-bottom: 2px solid transparent; font-weight: 600; }
QTabBar::tab:selected { color: @fg; border-bottom: 2px solid @progress_chunk; }
QTabBar::tab:hover:!selected { color: @fg; }
QLabel#pageTitle { font-size: 26px; font-weight: 700; color: @fg; }
QLabel#pageSubtitle, QLabel#panelDescription, QLabel#hint { color: @muted; font-size: 13px; }
QLabel#secTitle { color: @fg; font-size: 16px; font-weight: 700; }
QLabel#countBadge { color: @muted; background: @btn; padding: 5px 10px; border-radius: 11px; font-size: 12px; }
QLabel#emptyState { color: @muted; background: transparent; font-size: 14px; }
QPushButton { border-radius: 7px; padding: 8px 12px; }
QPushButton:focus { border: 1px solid @progress_chunk; }
QPushButton#addBtn { background: @add_btn; font-size: 13px; font-weight: 600; }
QPushButton#addBtn:hover { background: @btn_hover; }
QLineEdit, QPlainTextEdit, QDoubleSpinBox, QComboBox { background: @bg; border: 1px solid @border; border-radius: 7px; padding: 7px; }
QLineEdit:focus, QPlainTextEdit:focus, QDoubleSpinBox:focus { border: 1px solid @progress_chunk; }
QTableWidget, QTableWidget#libraryList { border: none; border-radius: 7px; }
QTableWidget#libraryList { background: @table_alt; }
QHeaderView::section { background: transparent; border-right: none; border-bottom: 1px solid @grid; padding: 9px 8px; font-size: 12px; }
QSplitter::handle:horizontal { background: @bg; width: 10px; }
QSplitter::handle:horizontal:hover { background: @border; border-radius: 4px; }
QFrame#nowCard, QFrame#nextCard { border: none; border-radius: 9px; }
QFrame#nowCard { background: @now_card; }
QFrame#nextCard { background: @table_alt; }
QLabel#nowKicker, QLabel#nextKicker { font-size: 11px; font-weight: 600; }
QLabel#nowTitle, QLabel#nextTitle { font-size: 16px; font-weight: 700; }
QLabel#nowNotes { font-size: 12px; }
QLabel#nowRemain { font-size: 18px; }
QLabel#playerArtwork { background: @btn; border-radius: 10px; }
QLabel#progressClock, QLabel#libSeekTime { color: @muted; font-size: 12px; min-width: 0; }
QLabel#volumeLabel { color: @muted; font-size: 12px; min-width: 0; }
QProgressBar#mediaProgress { background: @border; border: none; border-radius: 4px; }
QProgressBar#mediaProgress::chunk { background: @progress_chunk; border-radius: 4px; }
QProgressBar#vuBar { background: @border; border: none; border-radius: 4px; }
QProgressBar#vuBar::chunk { background: @progress_chunk; border-radius: 4px; }
QSlider#volumeSlider::groove:horizontal { background: @border; border: none; height: 5px; border-radius: 2px; }
QSlider#volumeSlider::sub-page:horizontal { background: @progress_chunk; border-radius: 2px; }
QSlider#volumeSlider::handle:horizontal { background: @slider_handle; width: 12px; margin: -4px 0; border-radius: 6px; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: @border; border-radius: 4px; min-height: 24px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
/* Buttons for global, potentially disruptive operations stay labelled and distinct. */
QPushButton#panicBtn { background: #9e3343; color: #ffffff; min-width: 56px; min-height: 38px; padding: 0 12px; font-size: 13px; font-weight: 700; }
QPushButton#panicBtn:hover { background: #bf4657; }
QPushButton#muteBtn, QPushButton#holdBtn, QPushButton#duckBtn,
QPushButton#muteOnBtn, QPushButton#holdOnBtn, QPushButton#duckOnBtn {
    min-width: 0; min-height: 38px; padding: 0 10px; font-size: 13px; border-radius: 7px;
}
QPushButton#muteBtn, QPushButton#holdBtn, QPushButton#duckBtn { background: @btn; color: @fg; }
QPushButton#muteOnBtn { background: @stop; color: @stop_fg; }
QPushButton#holdOnBtn { background: @stage; color: @stage_fg; }
QPushButton#duckOnBtn { background: @resume; color: @resume_fg; }
QPushButton#libStopSplitBtn { background: @btn; color: @fg; border-radius: 6px; }
QPushButton#libStopSplitBtn:hover { background: @btn_hover; }
QPushButton#libStopSplitBtn:disabled { background: @disabled_bg; color: @disabled_fg; }
QPushButton#libModeBtn { color: @lib_cat_fg; border-radius: 5px; }
QPushButton#libModeBtn[mode="repeat_one"], QPushButton#libModeBtn[mode="sequence"],
QPushButton#libModeBtn[mode="repeat_all"] { border-color: @progress_chunk; color: @type_audio; }

/* Icon-only transport: a generous hit target with the same ring on each channel. */
QPushButton#goBtn, QPushButton#libGoBtn {
    background: @panel; border: 3px solid @progress_chunk; border-radius: 29px;
    min-width: 52px; max-width: 52px; min-height: 52px; max-height: 52px; padding: 0;
}
QPushButton#goBtn:hover, QPushButton#libGoBtn:hover { background: @btn_hover; border-color: @progress_chunk; }
QPushButton#goBtn:disabled, QPushButton#libGoBtn:disabled { background: @panel; border-color: @disabled_fg; }
QPushButton#navBtn, QPushButton#pauseBtn, QPushButton#resumeBtn, QPushButton#stopBtn,
QPushButton#stageBtn, QPushButton#unstageBtn, QPushButton#libPauseBtn, QPushButton#libResumeBtn,
QPushButton#libStopBtn, QPushButton#libStageBtn, QPushButton#libUnstageBtn {
    background: transparent; border: none; min-width: 44px; max-width: 44px;
    min-height: 44px; max-height: 44px; padding: 0; border-radius: 22px;
}
QPushButton#navBtn:hover, QPushButton#pauseBtn:hover, QPushButton#resumeBtn:hover, QPushButton#stopBtn:hover,
QPushButton#stageBtn:hover, QPushButton#unstageBtn:hover, QPushButton#libPauseBtn:hover, QPushButton#libResumeBtn:hover,
QPushButton#libStopBtn:hover, QPushButton#libStageBtn:hover, QPushButton#libUnstageBtn:hover { background: @btn_hover; }
QPushButton#pauseBtn:disabled, QPushButton#resumeBtn:disabled, QPushButton#stopBtn:disabled,
QPushButton#stageBtn:disabled, QPushButton#unstageBtn:disabled, QPushButton#libPauseBtn:disabled,
QPushButton#libResumeBtn:disabled, QPushButton#libStopBtn:disabled, QPushButton#libStageBtn:disabled,
QPushButton#libUnstageBtn:disabled { background: transparent; }
QPushButton#goBtn:focus, QPushButton#libGoBtn:focus { border: 3px solid @progress_chunk; }
QProgressBar#mediaProgress { min-height: 20px; max-height: 20px; border: none; background: transparent; }
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
