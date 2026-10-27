---
name: kongchang-control
description: Control the local 简易控场 (Kongchang) Windows application through its Agent CLI. Use when a user asks to inspect or edit a show or media library, control playback or projection, or stop all media in this application.
---

# 简易控场本机控制

使用本 Skill 自带的 `scripts/agent_ctl.py` 操作正在运行、已启用 Agent 接口的简易控场。仅适用于 Windows 本机；这是 JSON 命令行接口，不是 MCP 服务。

安装器会将软件目录记录在本 Skill 的 `app-location.json`；软件移动后重新安装，或设置 `KONGCHANG_HOME`，或对每次 `call` 传 `--app-dir <软件目录>`。直接从便携包内运行时自动定位软件。使用软件自带 Python 或其他 Python 3.11+，CLI 无第三方依赖。安装后用本 Skill 目录的绝对路径运行脚本，例如：

```powershell
$codexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$skillDir = Join-Path $codexDir 'skills\kongchang-control'
$appDir = (Get-Content -Raw (Join-Path $skillDir 'app-location.json') | ConvertFrom-Json).app_dir
& (Join-Path $appDir 'vendor\python\python.exe') (Join-Path $skillDir 'scripts\agent_ctl.py') call system.info
& (Join-Path $appDir 'vendor\python\python.exe') (Join-Path $skillDir 'scripts\agent_ctl.py') call state.get
```

软件没有便携 Python 时可使用本机 Python 3.11+。接口找不到服务时，确认软件已运行且该安装包含 Agent 接口；必要时按软件目录下 `AGENTS.md` 启动。不要读取或输出 `data/agent-control.json` 的令牌内容。

根据用户请求先查询 `state.get`、`project.get`、`cue.list` 或 `library.list`，按返回的 ID 选择目标。操作参数和规则见 [references/api.md](references/api.md)；实际可用方法以 `system.info` 为准。需要参数时优先通过 `--params-file` 传 UTF-8 JSON 文件，或用 `--params-file -` 从标准输入读取，避免 PowerShell 引号和中文编码问题。CLI 每次输出一行 JSON；检查 `ok`、错误码及进程退出码，并根据需要重新查询状态确认结果。

增删改和保存可携带读取工程时返回的 `expected_revision`，以避免覆盖并发修改；发生冲突时重新读取并根据用户意图处理。不能直接改删素材库的节目单镜像，应修改对应源节目。修改条目只影响工程，不删除磁盘媒体文件。切换工程前关注未保存修改及播放状态。对用户未请求的工程、媒体或播放状态不要擅自修改。

播放控制沿用软件现有互斥与投屏规则；`playback.panic` 是全停。请求串行执行，前一个请求阻塞时全停也可能排队，不能承诺硬实时。超时或断线不代表动作没有执行；重试可能重复的操作前先读取状态。
