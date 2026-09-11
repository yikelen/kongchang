# Security / 隐私说明

## 请勿提交到公开仓库的内容

| 路径 | 原因 |
|------|------|
| `data/settings.json` | 含本机绝对路径、用户名、显示器设备名、窗口布局 |
| `data/diagnose.txt` / `data/crash.log` | 本机路径与环境信息 |
| `data/*.pid` / `splash.*` | 运行时状态 |
| `vendor/python/`、`vendor/mpv/` | 体积大；且为第三方二进制发行物 |
| `*.lnk` | 本机快捷方式 |
| 真实活动工程 json | 可能含真实人名、公司、客户名单 |

以上已在 `.gitignore` 中忽略（`data/**`、`vendor/python/`、`vendor/mpv/` 等）。

## 开源仓库应包含

- `src/`、`scripts/`、`assets/`（图标等）
- `examples/demo_show.json`（无真实隐私的示例工程）
- `README.md`、`LICENSE`、`requirements.txt`、启动脚本

## 运行时依赖

请用脚本生成便携运行时，或从 Release 附件获取 `vendor`，不要把 `vendor` 推进 Git 历史。
