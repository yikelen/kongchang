# AGENTS.md — 给 AI Agent 的安装与使用说明

当用户说「帮我安装 / 打开这个控场软件」时，**按本文执行**。  
仓库：https://github.com/yikelen/kongchang  
平台：**仅 Windows 64 位**（Win10/11）。macOS / Linux 不适用。

---

## 0. 先判断用户手里是什么

| 情况 | 你怎么做 |
|------|----------|
| 用户只要「能打开用」 | **优先**下载 Release 便携包（第 0.1 节），解压后启动 |
| 已有完整文件夹，且存在 `vendor\python\pythonw.exe` 与 `vendor\mpv\mpv.exe` | **跳过下载**，直接启动（第 3 节） |
| 刚 `git clone` 的源码，没有 `vendor` | 第 1–2 节 bootstrap，或改下 Release 包 |
| 用户只要「看看演示」 | 启动后导入 `examples\demo_show.json`（第 4 节） |

**不要**把用户本机的 `data\settings.json`、真实活动工程 json、或含人名客户的素材提交回 Git。

### 0.1 推荐：下载 GitHub Release 便携包（免装 Python）

```powershell
# 在用户选定的目录（如 D:\）执行
$rel = gh release download -R yikelen/kongchang -p "kongchang-windows-portable-*.zip" -D .
# 若无 gh，用浏览器打开：
# https://github.com/yikelen/kongchang/releases/latest
# 下载 kongchang-windows-portable-*.zip

Expand-Archive .\kongchang-windows-portable-*.zip -DestinationPath .
cd kongchang
Start-Process -FilePath ".\启动.bat" -WorkingDirectory (Get-Location)
```

无 `gh` 时也可用：

```powershell
Invoke-WebRequest -Uri "https://github.com/yikelen/kongchang/releases/latest/download/kongchang-windows-portable-v0.1.0.zip" -OutFile "kongchang-windows-portable.zip"
Expand-Archive .\kongchang-windows-portable.zip -DestinationPath .
cd kongchang
Start-Process .\启动.bat
```

（版本号以 Release 页最新文件名为准。）

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

成功标志：出现「简易控场」主窗口（可能先有短暂「正在加载」闪屏）。

若失败：跑 `.\环境检测.bat` 或：

```powershell
.\vendor\python\python.exe .\scripts\diagnose.py
```

查看 `data\diagnose.txt`。常见修复：安装 VC++ x64 运行库后重试。

**单实例：** 再开一次会唤起已有窗口，不会起第二份。

---

## 4. 打开文字演示（无需媒体文件）

1. 菜单：**工程 → 打开 / 导入…**
2. 选择仓库内：`examples\demo_show.json`
3. 左侧节目单应出现多条「备注」演示流程；右侧临时列表有占位音视频（无 path，可显示缺文件，属正常）

Agent 无法可靠操作 GUI 菜单时，可告诉用户上述两步；或说明「演示工程路径为：`<repo>\examples\demo_show.json`」。

---

## 5. 软件在干什么（Agent 背景）

- **不**控制 PPT 翻页；PPT 在画面 1，本软件在画面 2 控音视频。
- 节目单在左侧 `cues`；右侧「临时媒体」可独立播音频（可叠视频）与视频（与节目单视频互斥，同时只一个视频）。
- 工程是 JSON；媒体 `path` 相对 JSON 所在目录。
- 设置写在 `data\settings.json`（本机路径，勿提交 Git）。

---

## 6. 禁止事项

- 不要用系统 `.venv` 替代 `vendor\python` 去「发行」给别人（路径会绑死）。
- 不要把 `vendor\`、`data\settings.json`、真实活动 json 提交到公开仓库。
- 不要在非 Windows 上强行安装本项目的 GUI。

---

## 7. 给用户的最短回复模板

安装完成后可以这样说：

> 已装好便携 Python/Qt 和 mpv。控场已启动。  
> 若要看文字演示：菜单「工程 → 打开」选 `examples\demo_show.json`。  
> 正式活动请自备 mp3/mp4，按 README 做成「文件夹 + json」再导入。

---

## 8. 源码入口速查

| 路径 | 作用 |
|------|------|
| `启动.bat` | 用户入口（闪屏 + 主程序） |
| `scripts/run_app.py` | 真正启动 GUI |
| `scripts/setup_portable_python.py` | 下载 `vendor/python` |
| `scripts/download_mpv.py` | 下载 `vendor/mpv` |
| `scripts/agent_bootstrap.ps1` | Agent 无人值守准备环境 |
| `examples/demo_show.json` | 文字演示工程 |
| `src/ui/main_window.py` | 主界面 |
| `src/controller.py` | 播放控制 |
