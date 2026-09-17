# AGENTS.md — 给 AI Agent 的安装与使用说明

当用户说「帮我安装 / 打开这个控场软件」时，**按本文执行**。  
改功能、排工程 JSON、写文档时也以本文为准。  
仓库：https://github.com/yikelen/kongchang  
平台：**仅 Windows 64 位**（Win10/11）。macOS / Linux 不适用。

当前版本号在 `src/__init__.py`（例如 `0.2.4`）。GitHub 便携包文件名带对应 git 标签，例如 `kongchang-windows-portable-v0.2.4.zip`。**不要写死旧版本号去下载 zip。**

界面用语：**右侧叫「素材库」**，不要再叫「临时列表 / 临时媒体」。

应用内帮助（`帮助 → 使用说明`，F1）写在 `src/ui/help_dialog.py`。改播放规则或快捷键时，必须同步：

1. `README.md`（用户文档）
2. 本文
3. `src/ui/help_dialog.py`

---

## 0. 先判断用户手里是什么

| 情况 | 你怎么做 |
|------|----------|
| 用户只要「能打开用」 | **优先**下载 Release 便携包（第 0.1 节），解压后启动 |
| 已有完整文件夹，且存在 `vendor\python\pythonw.exe` 与 `vendor\mpv\mpv.exe` | **跳过下载**，直接启动（第 3 节） |
| 刚 `git clone` 的源码，没有 `vendor` | 第 1–2 节 bootstrap，或改下 Release 包 |
| 用户只要「看看演示」 | 启动后导入 `examples\demo_show.json`（第 4 节） |
| 用户要更新已有安装 | 第 7 节 |

**不要**把用户本机的 `data\settings.json`、真实活动工程 json、或含人名客户的素材提交回 Git。

### 0.1 推荐：下载 GitHub Release 便携包（免装 Python）

```powershell
# 在用户选定的目录（如 D:\）执行
gh release download -R yikelen/kongchang -p "kongchang-windows-portable-*.zip" -D .
Expand-Archive .\kongchang-windows-portable-*.zip -DestinationPath .
cd kongchang
Start-Process -FilePath ".\启动.bat" -WorkingDirectory (Get-Location)
```

无 `gh` 时：打开浏览器

https://github.com/yikelen/kongchang/releases/latest

下载最新的 `kongchang-windows-portable-*.zip`（文件名含当时的 `v*` 标签）。  
**禁止**用写死的 `.../download/kongchang-windows-portable-v0.1.0.zip` 这类旧链接。

推送 git 标签 `v*` 时，`.github/workflows/portable.yml` 会打 zip 并挂到该 Release。`workflow_dispatch` 也可手跑，但只有打在 `v*` 标签上的才会挂 Release 附件。

---

## 1. 环境前提（只用于首次引导下载）

本机需要**任意** Python 3.11+（仅用来跑下载脚本；跑起来之后用的是仓库里的便携 Python）。

在仓库根目录检测：

```powershell
py -3 -c "import sys; assert sys.version_info >= (3,11), sys.version; print(sys.version)"
```

若 `py` 不可用，试 `python`。若都没有：引导用户安装 https://www.python.org/downloads/ （勾选 Add to PATH），或改用已带 `vendor` 的完整发行夹。

可选但强烈建议：若目标机缺 VC++ 运行库导致 Qt 报错，安装  
https://aka.ms/vs/17/release/vc_redist.x64.exe

打不开时让用户看仓库根目录 `打不开请先看.txt`，或跑 `环境检测.bat`。

---

## 2. 下载程序依赖的文件（Agent 必做清单）

工作目录 = 仓库根目录（含 `启动.bat`、`src\`、`scripts\` 的那一层）。

### 2.1 便携 Python + PySide6（Qt）

```powershell
py -3 scripts\setup_portable_python.py
```

成功标志：

- 存在 `vendor\python\pythonw.exe`
- 存在 `vendor\python\Lib\site-packages\PySide6`

脚本会从 GitHub 下载 python-build-standalone，并 `pip install -r requirements.txt`（当前主要是 `PySide6_Essentials`）。  
耗时：视网络数分钟；输出里出现「完成」即 OK。

### 2.2 便携 mpv（解码播放）

```powershell
py -3 scripts\download_mpv.py
```

成功标志：

- 存在 `vendor\mpv\mpv.exe`

脚本从 `mpv-player/mpv` 的 `git-release` 拉 Windows x64 zip。

### 2.3 一键等价命令（无人值守）

不要用带 `pause` 的 `一键准备运行环境.bat` 做自动化；Agent 请直接跑上面两条，或：

```powershell
py -3 scripts\setup_portable_python.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
py -3 scripts\download_mpv.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
```

也可用仓库里的：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\agent_bootstrap.ps1
```

### 2.4 校验（启动前）

```powershell
Test-Path .\vendor\python\pythonw.exe
Test-Path .\vendor\mpv\mpv.exe
.\vendor\python\python.exe -c "from PySide6.QtWidgets import QApplication; print('qt-ok')"
```

三条都应为 True / 打印 `qt-ok`。

---

## 3. 启动软件

```powershell
Start-Process -FilePath ".\启动.bat" -WorkingDirectory (Get-Location)
```

或：

```powershell
Start-Process -FilePath ".\vendor\python\pythonw.exe" -ArgumentList ".\scripts\run_app.py" -WorkingDirectory (Get-Location)
```

成功标志：出现「简易控场」主窗口（标题带版本号，可能先有短暂「正在加载」闪屏）。首次启动会尝试在桌面创建「简易控场」快捷方式。

若失败：跑 `.\环境检测.bat` 或：

```powershell
.\vendor\python\python.exe .\scripts\diagnose.py
```

查看 `data\diagnose.txt`。常见修复：安装 VC++ x64 运行库后重试。

**单实例：** 再开一次会唤起已有窗口，不会起第二份。不要去杀用户其它 `pythonw` 进程。

---

## 4. 打开文字演示（无需媒体文件）

1. 菜单：**工程 → 打开 / 导入…**
2. 选择仓库内：`examples\demo_show.json`
3. 左侧节目单应出现多条「备注」演示流程；右侧 **素材库** 有占位音视频（无 path，可显示缺文件，属正常）

Agent 无法可靠操作 GUI 菜单时，可告诉用户上述两步；或说明「演示工程路径为：`<repo>\examples\demo_show.json`」。

---

## 5. 软件在干什么（Agent 背景）

窗口标题：**简易控场**。操作台一块屏，视频全屏到另一块屏。

- **不**控制 PPT 翻页；PPT 通常在另一台电脑或另一块屏。
- 工程是 JSON；媒体 `path` 相对 JSON 所在目录。
- 设置写在 `data\settings.json`（本机路径、投影屏、主题、两路音量、最近打开等，勿提交 Git）。
- 播放：本进程只发 IPC。节目单音频、素材库音频是两个 `mpv` 进程；**全场只有一个视频进程**。

### 5.1 两个列表

| | 节目单（左，`cues`） | 素材库（右，`library`） |
|--|----------------------|-------------------------|
| 用途 | 这场会的正式顺序 | 随时点播 |
| 前进 | **只手动**。播完不停、不切下一条 | 分类模式可在 **同分类、同类型** 内切下一首 |
| 视频 | 先预览（小窗暂停）再播放再全屏 | **无预览**；点另一条即切播，保持全屏或小窗 |
| 音频 | 与本路视频互斥 | 可叠在无声视频上 |
| 停止 | 底栏「停止」：本路音频渐停约 1.6s + 本路视频立刻停 | 「停止」停素材库声画；另有「停音频 / 停视频」 |

### 5.2 互斥与叠播（改播放逻辑时必须保持）

实现见 `src/controller.py`：

1. **全场同时只一个视频**（`self.video`）。
2. **节目单音频 XOR 素材库音频**（`self.audio` vs `self.lib_audio`）。两路音乐不得叠。
3. **节目单自己的音视频互斥**。点节目单视频要停节目单音频，反之亦然。底栏「停止」一次停干净这一路（以前叠过两次停止是 bug）。
4. **允许的叠播**：任意视频 + **素材库音频**。此时视频轨静音，垫乐走 `lib_audio`。
5. 素材库分类循环：音频 EOF 切下一首音频，视频 EOF 切下一首视频，互不等待。
6. **压低音频**：约 0.9 秒渐变到当前设定音量的 **60%**（`DUCK_RATIO = 0.6`），再按渐变恢复。不要瞬间改音量，更不要当成停止。
7. **全停**（`panic_stop` / `Ctrl+Esc`）：两路立刻停，不做渐停。
8. 视频不循环播完 → 封面图（`hold_cover`）或内置黑场 PNG。

### 5.3 素材库分类

- 分类头按钮循环：`default` → `repeat_one` → `sequence` → `repeat_all`（界面：默认 / 单曲 / 顺序 / 列表）。
- **默认**：跟该条 `loop`；不循环则播完停，不自动下一首。
- **单曲**：当前条循环。
- **顺序**：同分类同类型切下一首，末尾停（`wrap=False`）。
- **列表**：同分类同类型循环（`wrap=True`）。采访轮播用这个。
- **不跨分类，不把音频和视频排成一条队列。**
- 节目单音视频自动镜像到分类 **「默认」**（`SHOW_MIRROR_CATEGORY`），分组永远在最底下，顺序与节目单一致，用 `source_id` 指回原条目。生成 JSON 时不要手写 `source_id`，不要往「默认」里抄节目单。

### 5.4 用户明确不要的功能（不要擅自加回来）

- 节目单 **自动下一条**
- **双击播放**（防误触；单击选中 + 播放/空格）
- Inkue 导入 UI（`scripts/import_inkue.py` 可留着，不要做进菜单）
- PPT 翻页 / 控制另一台电脑上的 PPT
- 第二块提词屏（会占第三块显示器）

---

## 6. 生成或修改工程 JSON

给用户排一场活动时，输出 **一个文件夹 + 一份 json**，`path` 相对 json 所在目录。

提示词要点（可直接转述给另一个模型）：

```text
写一份简易控场工程 JSON。规则：
- version: 1
- cues = 节目单，从上到下。type 为 audio / video / note（也可用中文 音频/视频/备注）。
- 节目单不会自动下一条，按现场手动走。
- library = 素材库点播。用 category 分组（过场/颁奖/茶歇/采访 等）。
- 不要写 source_id，不要在 library 里建「默认」分类去复制节目单（软件会自动镜像）。
- path 相对本 json；没有文件可空 path。备注条不要 path。
- 音频不写 loop 时默认循环；视频默认不循环。
- 可选 hold_cover（封面图相对路径）。
- 可选 library_play_modes，例如 {"采访":"repeat_all"}。
  取值 default / repeat_one / sequence / repeat_all（或中文 默认/单曲/顺序/列表）。
- 不要用 type=stop（旧字段，界面已不用）。
```

字段容错：`Cue.from_dict` / `Project.load` 会忽略多余键、把 `\` 改成 `/`、缺 `id` 就生成。中文 type 别名可用。

改完逻辑后跑：

```powershell
.\vendor\python\python.exe -m unittest tests.test_playback_logic
```

覆盖分类切歌、镜像「默认」、部分互斥。GUI / mpv 行为仍需在 Windows 上点一遍。

---

## 7. 更新已有安装

| 用户手里是 | 做法 |
|------------|------|
| git 克隆（有 `.git`） | 工作区干净时：`powershell -ExecutionPolicy Bypass -File scripts\update_from_github.ps1` 或让用户双击 `从GitHub更新.bat`。只 `git pull --ff-only origin main`。脏工作区不要强拉。 |
| 菜单「帮助 → 检查更新」 | git 安装：fetch 后询问再跑上面的脚本；便携 zip：打开 Releases 页 |
| Release 便携 zip | 下最新 zip，解压到新目录，把旧的 `data\` 和活动 json 拷过去 |

不要重下 `vendor`，除非用户明确说 Python/mpv 坏了。不要动用户的活动 json。

发新版本给现场用：改 `src/__init__.py` → 提交推 `main` → 打标签 `vX.Y.Z` 并 push 标签，等 Actions `portable-zip` 把 zip 挂到 Release。

---

## 8. 禁止事项

- 不要用系统 `.venv` 替代 `vendor\python` 去「发行」给别人（路径会绑死）。
- 不要把 `vendor\`、`data\settings.json`、真实活动 json 提交到公开仓库。
- 不要在非 Windows 上强行安装本项目的 GUI。
- 不要把右侧再改回「临时列表」这个名字。
- 不要为了「专业」加回第 5.4 节否决的功能。
- 不要在 README 截图上叠编号圈，除非编号与当前控件一一对得上。宁可无标注。

---

## 9. 给用户的最短回复模板

安装完成后可以这样说：

> 已装好便携 Python/Qt 和 mpv。控场已启动。  
> 若要看文字演示：菜单「工程 → 打开」选 `examples\demo_show.json`。  
> 正式活动请自备 mp3/mp4，按 README 做成「文件夹 + json」再导入。  
> 左边节目单手动走单，不会自动下一条；右边素材库随时点播。PPT 仍由你自己翻。

---

## 10. 源码入口速查

| 路径 | 作用 |
|------|------|
| `启动.bat` | 用户入口（闪屏 + 主程序） |
| `从GitHub更新.bat` | 包装 `scripts/update_from_github.ps1` |
| `创建桌面快捷方式.bat` | 桌面 + 本夹 `.lnk` |
| `scripts/run_app.py` | 真正启动 GUI |
| `scripts/setup_portable_python.py` | 下载 `vendor/python` |
| `scripts/download_mpv.py` | 下载 `vendor/mpv` |
| `scripts/agent_bootstrap.ps1` | Agent 无人值守准备环境 |
| `scripts/update_from_github.ps1` | `git fetch` + fast-forward `origin/main` |
| `examples/demo_show.json` | 文字演示工程 |
| `src/__init__.py` | `__version__` |
| `src/ui/main_window.py` | 主界面 |
| `src/ui/help_dialog.py` | F1 使用说明 / 快捷键 / 关于 |
| `src/controller.py` | 播放控制（两路音频 + 一路视频、渐停、压低） |
| `src/models.py` | `Cue` / `Project`、分类模式、节目单镜像 |
| `src/settings.py` | `data/settings.json` |
| `src/shortcut.py` | 桌面快捷方式 |
| `src/show_log.py` | 演出日志 |
| `src/instance.py` | 单实例（唤起已有窗口；只清本软件残留 mpv） |
| `tests/test_playback_logic.py` | 分类 / 镜像等单测 |
| `.github/workflows/portable.yml` | `v*` 标签打 Windows 便携 zip |
