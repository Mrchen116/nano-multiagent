# Local Stack

本机开发运行 TypeScript IM + Node + DSH，生产拓扑另见 [fleet](prod-fleet.md)。临时验证用 [worktree 隔离脚本](../development/worktree-runtime.md)，不要占生产 `8011` 或复用生产数据。

## 准备

先按 [开发环境](../development/local-development.md) 安装并构建后端与 Web。配置 `~/.nanoassistant/config.yaml`，字段见 [Gateway](gateway.md)。

为本地 IM 准备持久、私有 JWT secret，并在同一启动环境设置 `IM_JWT_SECRET`。已有数据库重启不能更换此密钥。可设置 `IM_DB_PATH`、`IM_UPLOAD_DIR`、`IM_FRONTEND_DIST_DIR` 为明确的绝对路径；默认分别为 `data/im_service.sqlite3`、`data/uploads` 与仓内 `src/IM/frontend/dist`。

## 启动

空库仅执行一次管理员初始化，再启动 IM：

```bash
pnpm im init-admin --username root --password '<strong-password>' --display-name Root
pnpm im serve --host 127.0.0.1 --port 8011
```

保持该 IM 终端运行。`curl -fsS http://127.0.0.1:8011/health` 验证监听；浏览器打开 `http://127.0.0.1:8011/` 登录。

另一个终端启动节点：

```bash
pnpm pa start --config ~/.nanoassistant/config.yaml
```

首次启动通过终端显示的设备绑定页面，以目标 owner 登录并完成确认。`--auto-bind` 只用于配置了测试登录身份的隔离自动化。已有绑定不会重复创建所有者身份。

`Gateway started` 表示 DSH 已完成初始化和持久恢复，IM 与飞书连接仍需分别观察。在节点页面确认 online，再向目标 Agent 发消息，确认真实回复出现在同一聊天。

```text
Web/iOS → IM HTTP/WS → Node 产品路由 → stdio DSH → 产品交付 → 原聊天
```

## 停止和恢复

```bash
pnpm pa status --config ~/.nanoassistant/config.yaml
pnpm pa stop --config ~/.nanoassistant/config.yaml
```

先停节点，让 DSH 排空和刷盘，再在 IM 终端按 Ctrl-C。macOS 登录自启、PID/birth 身份校验、降级处理与恢复见 [Gateway 操作](gateway.md)；消息不通按 [排障顺序](troubleshooting.md) 保存首个错误。
