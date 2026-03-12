# Operator Runbook: IM + Gateway + Web IM

本文档只围绕默认用户路径：在同一台机器上启动 IM 服务和 Gateway，让正常用户从 Web IM 入口完成绑定并发起第一条聊天消息。

> 历史 operator-only API 验证命令保留在附录；默认主链路不需要手工拼 `bind` / `message` curl。

## 前置条件

1. Python 3.11+，并已执行 `pip install -e ".[dev]"`。
2. 在仓库根目录运行命令，或显式带上 `PYTHONPATH=src`。
3. 基础设施启动不需要外部 LLM API key；只有 agent 真正生成回复时才需要上游 LLM 配置。

## 1. 启动 IM 服务

```bash
cd <repo>
PYTHONPATH=src python -m uvicorn IM.app:app \
  --host 127.0.0.1 --port 8011
```

默认 Web IM URL：
- `http://127.0.0.1:8011/`
- `http://127.0.0.1:8011/chat`

当前行为说明：
- 仓内已交付 `src/IM/frontend/dist` 时，IM host 会直接服务 `/`、`/chat`、`/settings/*`、`/bind/confirm`。
- 正常用户默认走 IM host，不需要先知道前端 dev server `4173`。

## 2. 准备最小 Gateway 配置

创建 `node-config.yaml`：

```yaml
node:
  node_id: my-macbook

agents:
  - agent_id: assistant
    title: My Assistant
    # workspace_root: ~/nano-assistant/workspace/assistant

channels:
  - name: web_relay
    enabled: true

kernel:
  command: "python -m uvicorn agent.platform.http_api.app:app --host 127.0.0.1 --port 8000"
  startup_timeout_seconds: 15
  health_poll_interval_seconds: 0.25
  shutdown_grace_seconds: 5

heartbeat:
  tick_interval_seconds: 30

im_service:
  url: http://127.0.0.1:8011
```

说明：
- 默认本地路径不需要填写 `kernel.token`；Gateway 会自动补齐本地 kernel bearer token。
- 省略 `agents[].workspace_root` 时，Gateway 默认使用 `~/nano-assistant/workspace/<agent_id>/`，并在首次加载配置时自动创建目录。
- `kernel.base_url` 属于内部实现细节，最小配置无需填写。
- `im_service.url` 指向 IM 服务后，Gateway 才会把节点接到 Web IM 的 relay 链路上。

## 3. 启动 Gateway

```bash
cd <repo>
PYTHONPATH=src python -m personal_assistant.main --config ./node-config.yaml
```

Gateway 默认启动顺序：
1. 读取本地配置。
2. 启动并探活本地 kernel。
3. 启动已配置 channel。
4. 连接 IM WebSocket 并注册节点。
5. 检查节点是否已绑定；必要时给出绑定下一步。
6. 保持常驻，等待 Web IM 消息。

## 4. 观察未绑定 / 已绑定行为

### 未绑定节点

预期现象：
- Gateway 终端输出 `ACTION ...` 与 `NEXT ...`。
- Gateway 会尝试打开绑定页；默认绑定 URL 形如 `http://127.0.0.1:8011/bind/confirm?token=...`。
- 浏览器进入绑定确认页后，确认绑定即可把当前用户与该节点关联起来。

如果浏览器没有自动打开：
- 直接复制 Gateway 终端里打印的 `NEXT Open ...` 链接到浏览器。

### 已绑定节点

预期现象：
- Gateway 不会再次要求绑定，也不会重复打开浏览器。
- 终端保持常驻，等待 Web IM 消息。
- 打开 `http://127.0.0.1:8011/` 或 `http://127.0.0.1:8011/chat` 即可进入聊天应用。

### 启动失败 / Bootstrap 失败

预期现象：
- Gateway 不应只留下 Python 异常；会输出 `NEXT ...` 指出下一步。
- 同样的可执行提示会回写到 IM 节点板 `last_error`。

推荐查看：
- Gateway 当前终端输出。
- `http://127.0.0.1:8011/im/v1/nodes` 中对应节点的 `status` / `last_error`。

## 5. 进入 Web IM 并发送第一条消息

1. 打开 `http://127.0.0.1:8011/`。
2. 浏览器会落到 `/chat`。
3. Web IM 会自动准备本地 `You` 用户与默认 starter conversation，并根据当前绑定/在线状态决定 composer 是否可用。
4. 若页面显示 `Chat unavailable`，先按卡片中的下一步完成绑定或恢复在线节点；只有 composer 恢复可输入后再发送消息。

说明：
- 正常用户主链路不需要先手工创建用户、会话或调用 `message` API。
- 未绑定时，composer 会预先禁用，并显示统一的 `Chat unavailable` 卡片，要求先完成 Gateway 绑定。
- 已绑定但节点离线时，composer 同样预先禁用，并显示同一套 `Chat unavailable` 卡片，要求 bring the node online or bind another online node。
- 若提交瞬间节点变为 unavailable，页面会保留草稿并在发送区显示同样的 `Chat unavailable` 失败提示；用户不需要依赖终端日志理解状态。

消息主链路：

```text
Browser / Web IM -> IM HTTP API -> IM WebSocket relay.message -> Gateway -> Kernel -> Gateway -> Web IM
```

## 6. 日常检查

查看节点状态：

```bash
curl -s http://127.0.0.1:8011/im/v1/nodes | python -m json.tool
```

预期：
- 已启动且已连上 IM 的节点显示为 `online`。
- 若启动失败但节点板仍可见，会带上 actionable `last_error`。

运行 smoke 脚本验证 Gateway 生命周期：

```bash
PYTHONPATH=src python -m personal_assistant.smoke_runtime \
  --config ./node-config.yaml \
  --ready-timeout 20 \
  --steady-seconds 0.5 \
  --shutdown-timeout 10
```

预期输出：

```text
READY pid=<pid> url=http://127.0.0.1:8000/v1/health
RUNNING steady_seconds=0.5 alive=true
SHUTDOWN exit_code=0
```

## 7. 故障排查

| 现象 | 可能原因 | 建议动作 |
|---|---|---|
| 打开 `http://127.0.0.1:8011/` 仍不是 Web IM | IM 服务未启动，或你连到的不是当前仓库实例 | 先确认 IM 服务进程和端口，再确认 `src/IM/frontend/dist` 已随仓库提供 |
| Gateway 启动后立刻退出 | kernel 健康检查失败或 IM bootstrap 失败 | 看终端里的 `NEXT ...`，再核对 `http://127.0.0.1:8011/im/v1/nodes` 的 `last_error` |
| 未绑定时没有完成关联 | 绑定页未打开或未确认 | 从终端复制 `NEXT Open ...` 链接，完成绑定后刷新 `/chat` |
| Web IM 能打开但发消息时报无可用节点 | Gateway 未连上 IM，或节点还未 `online` | 先看 Gateway 是否常驻，再看 `/im/v1/nodes` 是否已有在线节点 |
| 401 Unauthorized | 你改成了自定义 kernel token，但 Gateway/Kernel 不一致 | 对齐 `kernel.token` 与 kernel 进程实际使用的 token；默认本地路径无需手工设置 |
| `workspace_root does not exist` | 显式配置了不存在的目录 | 创建该目录，或删掉配置让 Gateway 使用默认路径 |

## 8. 调试附录：API 路径

下面的 HTTP API 只用于调试或脚本化验证，不是正常用户默认主链路。

### 8.1 手工检查绑定状态

```bash
curl -s http://127.0.0.1:8011/im/v1/nodes | python -m json.tool
curl -s "http://127.0.0.1:8011/im/v1/me?user_id=<user_id>" | python -m json.tool
```

### 8.2 手工发起 / 确认绑定

```bash
curl -s -X POST http://127.0.0.1:8011/im/v1/bind \
  -H "Content-Type: application/json" \
  -d '{"action": "start", "node_id": "my-macbook"}' | python -m json.tool

curl -s -X POST http://127.0.0.1:8011/im/v1/bind \
  -H "Content-Type: application/json" \
  -d '{"action": "confirm", "bind_id": "<bind_id>", "user_id": "<user_id>"}' | python -m json.tool
```

### 8.3 手工创建会话并发消息

```bash
curl -s -X POST http://127.0.0.1:8011/im/v1/users \
  -H "Content-Type: application/json" \
  -d '{"username": "operator", "display_name": "Operator"}' | python -m json.tool

curl -s -X POST http://127.0.0.1:8011/im/v1/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Chat", "participant_ids": ["<user_id>"]}' | python -m json.tool

curl -s -X POST http://127.0.0.1:8011/im/v1/conversations/<conversation_id>/messages \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: debug-1" \
  -d '{"sender_user_id": "<user_id>", "content": "Hello Agent", "target_node_id": "my-macbook"}' \
  | python -m json.tool
```

## 9. 自动化验收测试

真实进程联调验收测试入口：

```bash
cd <repo>
PYTHONPATH=src python -m pytest tests/e2e/test_m112_real_process_roundtrip_e2e.py -v
```

覆盖的核心验收面：
- NodeGateway-SPEC §16：channel 启动、四步决策、回发原目标、heartbeat、IM 离线降级。
- IM-SPEC §12：消息往返、设备绑定、节点状态、离线降级、幂等。
