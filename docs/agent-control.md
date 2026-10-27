# 本机 Agent 控制接口

运行中的「简易控场」可供本机 Agent 查询和操控。接口在 Qt 主线程执行，工程列表、撤销历史、自动保存和播放规则与界面共用。

## 开始使用

先启动控场软件。服务只监听 `127.0.0.1` 的随机端口，连接信息保存在 `data/agent-control.json`。文件包含控制令牌，仅供当前 Windows 用户访问；不要提交、转发或打印它。软件退出后会清理连接信息。

从仓库根目录调用：

```powershell
.\vendor\python\python.exe scripts\agent_ctl.py call system.info
.\vendor\python\python.exe scripts\agent_ctl.py call state.get
.\vendor\python\python.exe scripts\agent_ctl.py call project.get
```

程序可从任意工作目录执行，默认连接脚本所在软件目录的实例。每次输出一行 JSON，成功时 `ok: true`；失败时 `ok: false`，`error` 包含 `code` 和 `message`，进程退出码为 1。可用 `--timeout 30` 设置超时。

带参数的请求可通过 UTF-8 文件传入，避免 PowerShell 转义问题：

```powershell
$agentParams = Join-Path $env:TEMP 'kongchang-agent-params.json'
@'
{"type":"note","name":"开场提示","notes":"主持人上台"}
'@ | Set-Content -Encoding utf8 $agentParams
.\vendor\python\python.exe scripts\agent_ctl.py call cue.add --params-file $agentParams
```

也可用 `--params` 传入 JSON 对象；`--params-file -` 从标准输入读取。不要在命令行或回复中打印发现文件里的 token。

## 接口方法

`system.info` 返回软件版本和方法清单；`state.get` 返回实时播放状态、音量、当前选择、全屏和全局开关；`project.get` 返回工程内容、路径、未保存状态和 `revision`。`cue.list`、`library.list` 分别列出条目；素材库结果包含自动镜像及 `source_id`。

| 方法 | 参数 | 说明 |
|---|---|---|
| `project.open` / `project.create` | `path`，可选 `expected_revision` | 绝对 `.json` 路径。创建不会覆盖现有文件；有未保存修改或声画正在运行时拒绝切换。 |
| `project.save` | 可选 `expected_revision` | 保存当前已有路径的工程。 |
| `project.save_as` | `path`，可选 `expected_revision` | 保存到不存在的绝对 `.json` 路径，保留媒体引用并重基准相对路径。 |
| `cue.add` / `library.add` | `type`, `name`，可选 `path`, `notes`, `loop`, `index`, `trim_in`, `trim_out`, `fade_in`, `fade_out`；素材库可选 `category` | 节目单支持 `audio`、`video`、`note`；素材库只支持音视频。`index` 从 0 开始。 |
| `cue.update` / `library.update` | `id`, `changes` | 按 ID 修改上述字段；不支持直接修改类型。 |
| `cue.delete` / `library.delete` | `id` | 只删除工程条目，不删除磁盘媒体文件。 |
| `cue.move` / `library.move` | `id`, `index` | 移动到从 0 开始的最终位置。 |
| `playback.play` | `channel`: `show` 或 `library`；`id` | 节目单视频遵循先预览再播放；素材库视频遵循原有直接播放规则。 |
| `playback.pause` / `playback.resume` / `playback.stop` | `channel`: `show` 或 `library` | 分通道控制；停止通常沿用渐停规则，仍在加载的媒体会立即停止。 |
| `playback.seek` | `channel`: `show`、`library_audio` 或 `library_video`；`ratio`: 0–1 | 跳转指定通道的进度。 |
| `playback.stage` | `channel`: `show` 或 `library`；可选视频 `id` | 将该通道的视频投到设置的投影屏；不传 ID 时使用已加载视频。 |
| `playback.unstage` | `channel`: `show` 或 `library` | 收起该通道的视频全屏。 |
| `playback.panic` | 无 | 立即全停节目单和素材库的声画。 |
| `playback.mute` / `playback.duck` / `playback.hold` | `value`: 布尔值 | 设置全局静音、压低音频、封面／黑场开关。 |
| `volume.set` | `channel`: `show` 或 `library`；`value`: 0–100 | 设置独立通道音量。 |
| `system.show_mode` | `value`: 布尔值 | 设置演出模式。 |

增删改移动接口以及工程保存、切换支持可选 `expected_revision`。建议先读 `project.get`，再在写入请求中带回该 revision；期间工程发生变化会返回 `revision_conflict`，避免覆盖新的修改。

节目单锁定时不能修改节目单；素材库中 `source_id` 对应节目单的自动镜像，不能直接修改或删除，应该修改源节目。播放中的条目不能删除或更改媒体路径与裁剪参数。界面有尚未提交的名称或时间编辑时，接口会返回 `editor_busy`；有模态对话框时普通写入和播放会返回 `modal_active`，全停仍可使用。

CLI 超时或连接中断不代表动作一定没有执行。重试增删改或播放前应先查询状态和工程，避免重复操作。

请求由界面主线程串行处理；如果前一个操作正等待 mpv 响应，后续命令（包括全停）可能排队，接口不提供硬实时响应保证。现场仍应保留人工操作和应急流程。

## 本地协议

客户端从发现文件读取 `host`、`port`、`token`、`protocol`，建立 TCP 连接并发送一行 UTF-8 JSON：

```json
{"id":"unique-request-id","token":"<token>","method":"state.get","params":{}}
```

服务返回一行 `{"id":"unique-request-id","ok":true,"result":{...}}`，或 `{"id":"unique-request-id","ok":false,"error":{"code":"...","message":"..."}}`。每个连接只处理一条请求；请求上限 1 MiB，响应上限 4 MiB。只使用本机地址，不能将控制令牌传给不可信程序。
