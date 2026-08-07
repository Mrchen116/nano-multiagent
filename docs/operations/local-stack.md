# Local Stack

本文用于启动**本机一体**的 IM + Gateway + Web IM 开发主链路（IM 也跑在本机 `:8011`）。个人生产舰队是另一套拓扑——IM 只在 Mac mini，本机只跑第二 Gateway——见 [`prod-fleet.md`](prod-fleet.md)。临时开发验证需要隔离端口、config、数据库和进程，请改用 [`../development/worktree-runtime.md`](../development/worktree-runtime.md)。

## 前置条件

- 已按 [`../development/local-development.md`](../development/local-development.md) 安装 Python 依赖。
- 已准备包含有效 `llm:` 段的 `~/.nanoassistant/config.yaml`；结构和生命周期命令见 [`gateway.md`](gateway.md)。
- Web IM 需要 `src/IM/frontend/dist/`。本地尚未构建时，在 `src/IM/frontend/` 执行 `npm install && npm run build`；前端开发模式见 [`../../src/IM/frontend/README.md`](../../src/IM/frontend/README.md)。

## 1. 启动 IM

在仓库根目录执行：

```bash
PYTHONPATH=src .venv/bin/python -m uvicorn IM.app:app \
  --host 127.0.0.1 \
  --port 8011
```

把 IM 保持在当前终端或一个明确命名的持久终端会话中。先验证 HTTP 服务，再继续启动 Gateway：

```bash
curl -fsS http://127.0.0.1:8011/openapi.json >/dev/null
```

浏览器入口为：

- `http://127.0.0.1:8011/`
- `http://127.0.0.1:8011/chat`

未登录时页面会进入登录页；新用户可以从页面注册。空库需要先创建运维账号时，可使用 [`troubleshooting.md`](troubleshooting.md#认证和节点-api-诊断) 中的 `init_admin` 命令。

## 2. 启动 Gateway

默认配置位于 `~/.nanoassistant/config.yaml`：

```bash
PYTHONPATH=src .venv/bin/python -m personal_assistant.main
```

使用其他配置或临时覆盖 IM 地址时显式传参：

```bash
PYTHONPATH=src .venv/bin/python -m personal_assistant.main \
  --config /absolute/path/to/config.yaml \
  --im-service-url http://127.0.0.1:8011
```

默认命令在后台启动 Gateway 并返回 `Gateway started (pid=...)`、IM 地址和日志路径。这只证明后台 child 已建立运行态且当时仍存活；继续查看 config 同目录的 `gateway.log`，并在 Web IM 的节点页面确认节点已经连接。

首次连接一个尚未绑定的节点时，Gateway 会尝试打开绑定页，并把 `ACTION ...` / `NEXT ...` 写入日志。按页面完成绑定即可；`--auto-bind` 只用于自动化和隔离 E2E。

## 3. 验证用户主链路

1. 登录 Web IM，打开 `/chat`。
2. 若页面提示打开 bind flow，先完成节点绑定。
3. 若页面提示 Gateway offline，回到 `gateway.log` 和节点页面确认连接状态。
4. 输入区可用后发送一条消息，并确认用户消息和 Agent 回复都出现在当前会话。

主链路为：

```text
Browser / Web IM
  → IM HTTP API
  → IM WebSocket relay
  → Gateway
  → in-process Agent Kernel
  → Gateway
  → Web IM
```

需要判断某一层失败时，按 [`troubleshooting.md`](troubleshooting.md) 的证据顺序排查。

## 4. 停止

先停止与该 config 对应的 Gateway：

```bash
PYTHONPATH=src .venv/bin/python -m personal_assistant.main stop
```

使用非默认配置时带上同一文件：

```bash
PYTHONPATH=src .venv/bin/python -m personal_assistant.main stop \
  --config /absolute/path/to/config.yaml
```

看到 `STOPPED`、`NOT RUNNING` 或 `STALE` 后，再在 IM 所在终端发送 `Ctrl-C`。`STOPPED` 表示实例已关闭，`NOT RUNNING` 表示该 config 没有运行态，`STALE` 表示 CLI 识别并清理了失效记录；详细语义见 [`gateway.md`](gateway.md#运行状态与可用性)。

## Current behavior

- Gateway 后台启停、状态文件、断线重连和绑定行为：[`../specs/gateway/service-lifecycle.md`](../specs/gateway/service-lifecycle.md)
- Web IM 登录、会话和不可用状态：[`../specs/im/auth-tenancy.md`](../specs/im/auth-tenancy.md) / [`../specs/im/web-chat-ux.md`](../specs/im/web-chat-ux.md)
