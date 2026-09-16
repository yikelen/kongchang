"""控场使用说明（帮助菜单）。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
)

from src import __version__

_GUIDE = """
<h2>两个列表，别混</h2>
<p><b>左边节目单</b>：这场会的正式顺序。按「上一条 / 下一条 / 播放」走。音视频互斥，同时只出一条。</p>
<p><b>右边素材库</b>：随时点播。颁奖垫、茶歇、采访、应急片都放这里。节目单里的音视频会自动出现在最底下的「默认」分类，顺序和左边一样。</p>
<p>无声视频要垫乐：节目单或素材库播视频，再在素材库点一首音频。视频会静音，垫乐单独走。</p>

<h2>开场怎么投屏</h2>
<ol>
<li>右上角「全屏投影到」选<b>观众那块屏</b>，不要选「本软件」。</li>
<li>节目单视频先点<b>预览</b>（操作台小窗），确认后再<b>播放</b>，再点<b>全屏</b>。</li>
<li>素材库视频<b>没有预览</b>：点哪条切哪条；已经全屏就接着全屏，小窗就接着小窗。</li>
</ol>

<h2>停止</h2>
<ul>
<li>节目单底栏「停止」：停节目单这一路（音频渐停 + 视频一起停）。</li>
<li>「全停」或 Ctrl+Esc：节目单和素材库全部立刻停。</li>
<li>素材库「停音频 / 停视频」：叠播时只停其中一路。</li>
</ul>

<h2>分类播放（素材库）</h2>
<p>每个分类头右侧按钮：<b>默认 → 单曲 → 顺序 → 列表</b>。</p>
<ul>
<li><b>默认</b>：选中谁播谁；勾了循环就单曲循环，没勾就播完停。</li>
<li><b>单曲</b>：当前条循环。</li>
<li><b>顺序</b>：同分类、同类型播完切下一首，到末尾停。</li>
<li><b>列表</b>：同分类、同类型列表循环（采访轮播用这个）。</li>
</ul>
<p>音频、视频各切各的，叠播时互不影响。</p>

<h2>底栏常用键</h2>
<ul>
<li><b>静音</b>：所有声道立刻无声，再按恢复。</li>
<li><b>封面</b>：切到封面图（没设封面就是黑场）。视频不循环播完也会自动落封面。工程菜单里可设置封面图。</li>
<li><b>压低音频</b>：约 0.9 秒把当前垫乐渐变到音量的 60%，再按渐变恢复。讲话时用。</li>
</ul>

<h2>演出模式</h2>
<p>菜单「工程 → 演出模式」或 <b>F11</b>：收起中间编辑栏，放大正在出 / 下一条。数字键 1–9 点播素材库当前看得见的第 n 条。</p>

<h2>其它</h2>
<ul>
<li>改单约 1.5 秒自动保存。锁定节目单（Ctrl+L）后不能改顺序，仍能播。</li>
<li>「高级」里的从第几秒起 / 播到第几秒 / 渐强渐弱，一般不用。</li>
<li>检查媒体、封面图、演出日志都在「工程」菜单。</li>
</ul>

<h2>怎么更新</h2>
<p>本机这份如果是 git 克隆的，双击文件夹里的 <b>从GitHub更新.bat</b>，或菜单「帮助 → 检查更新」。只拉源码，不重下 Python/mpv，也不动 data 和工程 json。</p>
<p>现场用的便携 zip：到 GitHub Releases 下最新包，解压后把旧的 <code>data</code> 文件夹和活动 json 拷进新目录。</p>
<p>GitHub 上必须先有人把新版本 push / 发 Release，更新才能拿到新功能。</p>
"""

_KEYS = """
<table cellpadding="6">
<tr><td><b>空格</b></td><td>播放当前选中（节目单或素材库，看焦点在哪）</td></tr>
<tr><td><b>P</b></td><td>暂停 / 继续</td></tr>
<tr><td><b>← →</b></td><td>进度 ±5 秒</td></tr>
<tr><td><b>↑ ↓</b></td><td>音量 ±5</td></tr>
<tr><td><b>M</b></td><td>静音 / 取消静音</td></tr>
<tr><td><b>B</b></td><td>封面 / 黑场</td></tr>
<tr><td><b>D</b></td><td>压低音频 / 恢复</td></tr>
<tr><td><b>Esc</b></td><td>焦点在素材库：停素材库；否则全停</td></tr>
<tr><td><b>Ctrl+Esc</b></td><td>全停（所有声画）</td></tr>
<tr><td><b>F11</b></td><td>演出模式</td></tr>
<tr><td><b>F1</b></td><td>本说明</td></tr>
<tr><td><b>1–9</b></td><td>演出模式下点播素材库可见第 n 条</td></tr>
<tr><td><b>Ctrl+Z / Y</b></td><td>撤销 / 重做</td></tr>
<tr><td><b>Ctrl+S / O / N</b></td><td>保存 / 打开 / 新建</td></tr>
<tr><td><b>Ctrl+K</b></td><td>检查媒体</td></tr>
<tr><td><b>Ctrl+L</b></td><td>锁定节目单</td></tr>
</table>
"""


class HelpDialog(QDialog):
    def __init__(self, parent=None, page: str = "guide") -> None:
        super().__init__(parent)
        self.setWindowTitle("使用说明")
        self.resize(640, 520)
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._page(_GUIDE), "怎么用")
        tabs.addTab(self._page(_KEYS), "快捷键")
        if page == "keys":
            tabs.setCurrentIndex(1)
        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _page(html: str) -> QTextBrowser:
        view = QTextBrowser()
        view.setOpenExternalLinks(False)
        view.setHtml(html)
        return view


def show_about(parent) -> None:
    QMessageBox.information(
        parent,
        "关于简易控场",
        f"简易控场  v{__version__}\n\n"
        "年会 / 启动会控场：节目单顺序播，素材库点播，双屏投影。\n"
        "按 F1 查看使用说明。",
    )
