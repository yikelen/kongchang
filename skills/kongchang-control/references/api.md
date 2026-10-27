# 本机接口速查

所有方法通过 `call <方法名>` 调用；可用 `--app-dir <目录>` 或 `--discovery <文件路径>` 选择实例。参数为 JSON 对象。读取 `system.info` 检查实际版本的方法。

| 方法 | 参数及作用 |
|---|---|
| `system.info`、`state.get`、`project.get` | 读取方法、播放状态或工程及 revision。 |
| `cue.list`、`library.list` | 列出节目或素材，素材库镜像含 `source_id`。 |
| `project.open`、`project.create`、`project.save_as` | `path` 为绝对 `.json` 路径；创建和另存不会覆盖现有文件。 |
| `project.save` | 保存当前已有路径的工程。 |
| `cue.add`、`library.add` | `type`、`name`；可选 `path`、`notes`、`loop`、`index`、`trim_in`、`trim_out`、`fade_in`、`fade_out`；素材库可选 `category`。节目支持 `audio`、`video`、`note`，素材库仅支持音视频。 |
| `cue.update`、`library.update` | `id` 和 `changes` 对象；类型不可修改。 |
| `cue.delete`、`library.delete` | `id`；仅删除工程条目。 |
| `cue.move`、`library.move` | `id`、`index`；位置从 0 开始。 |
| `playback.play` | `channel` 为 `show` 或 `library`，以及 `id`。节目单视频先预览再播放，素材库视频直接播放。 |
| `playback.pause`、`playback.resume`、`playback.stop` | `channel` 为 `show` 或 `library`。停止通常渐停，加载中的媒体立即停止。 |
| `playback.seek` | `channel` 为 `show`、`library_audio` 或 `library_video`；`ratio` 为 0–1。 |
| `playback.stage` | `channel` 为 `show` 或 `library`，可选视频 `id`。 |
| `playback.unstage` | `channel` 为 `show` 或 `library`。 |
| `playback.panic` | 无参数，立即全停所有通道。 |
| `playback.mute`、`playback.duck`、`playback.hold` | 布尔值 `value`，设置全局静音、压低音频、封面／黑场。 |
| `volume.set` | `channel` 为 `show` 或 `library`，`value` 为 0–100。 |
| `system.show_mode` | 布尔值 `value`，设置演出模式。 |

增删改移动、工程保存和切换支持可选 `expected_revision`。节目单锁定、条目正在播放或界面编辑尚未提交时，部分修改会被拒绝；有模态对话框时普通写入和播放被拒绝，全停仍可调用。

示例：在临时 UTF-8 文件写入 `{"type":"note","name":"开场提示","notes":"主持人上台"}`，然后执行 `agent_ctl.py call cue.add --params-file <该文件>`。播放示例参数为 `{"channel":"show","id":"<节目 ID>"}`。先查状态并使用实际 ID，不要把示例占位符直接用于操作。
