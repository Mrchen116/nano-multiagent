# Operator Runbook: IM + Gateway + Agent Kernel

本文档描述如何在同一台机器上启动完整的 IM 服务 + Node Gateway + Agent 内核三进程系统。

> 所有步骤已在 M112 里程碑中被真实执行验证。

## 前置条件

1. Python 3.11+，已安装项目依赖（`pip install -e ".[dev]"`）
2. 项目源码目录：`<repo>/src` 需在 PYTHONPATH 中
3. 无需外部 LLM API key 即可启动基础设施（LLM 仅在 agent 处理消息时需要）

## 1. 启动 Agent 内核

Agent 内核是 FastAPI HTTP 服务，提供 session/run/health 等 API。

```bash
cd <repo>
PYTHONPATH=src python -m uvicorn agent.platform.http_api.app:app \
  --host 127.0.0.1 --port 8000
```

验证：

```bash
curl -s http://127.0.0.1:8000/v1/health | python -m json.tool
# 应返回 {"healthy": true, ...}
```

环境变量（可选）：
- `NANO_MULTIAGENT_API_TOKEN`: API 认证令牌（设置后所有请求需携带 `Authorization: Bearer <token>`）
- `NANO_MULTIAGENT_LLM_PROVIDER`: LLM 提供商（`openai_compat` 或 `anthropic`）
- `NANO_MULTIAGENT_LLM_BASE_URL`: LLM API 地址
- `NANO_MULTIAGENT_LLM_API_KEY`: LLM API 密钥
- `NANO_MULTIAGENT_LLM_MODEL`: 模型名称

## 2. 启动 IM 服务

IM 服务是独立的 FastAPI 应用，提供 Web IM API 和 Gateway WebSocket 端点。

```bash
cd <repo>
PYTHONPATH=src python -m uvicorn IM.app:app \
  --host 127.0.0.1 --port 8011
```

验证：

```bash
curl -s http://127.0.0.1:8011/docs | head -5
# 应返回 HTML（FastAPI Swagger UI）
```

环境变量（可选）：
- `IM_DB_PATH`: SQLite 数据库路径（默认 `data/im_service.sqlite3`）

## 3. 准备 Gateway 配置

创建 `node-config.yaml`：

```yaml
node:
  node_id: my-macbook
  # user_id: <绑定后自动关联>

agents:
  - agent_id: assistant
    workspace_root: /path/to/agent/workspace
    title: My Assistant

channels:
  - name: web_relay
    enabled: true

kernel:
  base_url: http://127.0.0.1:8000
  # token: <与内核的 NANO_MULTIAGENT_API_TOKEN 一致>
  command: "python -m uvicorn agent.platform.http_api.app:app --host 127.0.0.1 --port 8000"
  startup_timeout_seconds: 15
  health_poll_interval_seconds: 0.25
  shutdown_grace_seconds: 5

heartbeat:
  tick_interval_seconds: 30

im_service:
  url: http://127.0.0.1:8011
  # token: <可选认证令牌>
```

注意：
- `workspace_root` 必须是已存在的目录
- 如果 kernel 已经在外部启动，可以省略 `kernel.command` 并手动启动
- `im_service` 块可选，省略则 Gateway 以本地自治模式运行（外部 IM channel 仍可用）

## 4. 启动 Node Gateway

```bash
cd <repo>
PYTHONPATH=src python -m personal_assistant.main --config /path/to/node-config.yaml
```

Gateway 启动顺序（符合 NodeGateway-SPEC §2）：
1. 加载本地配置
2. 启动/探活 agent 内核（轮询 `/v1/health`）
3. 启动所有已配置 channel 适配器
4. 启动 heartbeat 调度器
5. 如配置了 IM 服务地址，主动建立 WebSocket 连接并注册节点
6. 进入就绪状态，保持常驻

关闭（Ctrl+C 或 SIGTERM）顺序（符合 NodeGateway-SPEC §2）：
1. 停止 heartbeat 调度器
2. 停止所有 channel 适配器
3. 断开 IM WebSocket 连接
4. 关闭 agent 内核子进程
5. 清理资源退出

## 5. 验证消息往返

### 5.1 创建用户和会话

```bash
# 创建用户
curl -s -X POST http://127.0.0.1:8011/im/v1/users \
  -H "Content-Type: application/json" \
  -d '{"username": "operator", "display_name": "Operator"}' | python -m json.tool

# 记下返回的 user id，创建会话
curl -s -X POST http://127.0.0.1:8011/im/v1/conversations \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Chat", "participant_ids": ["<user_id>"]}' | python -m json.tool
```

### 5.2 发送消息

```bash
curl -s -X POST http://127.0.0.1:8011/im/v1/conversations/<conversation_id>/messages \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: test-1" \
  -d '{"sender_user_id": "<user_id>", "content": "Hello Agent", "target_node_id": "my-macbook"}' \
  | python -m json.tool
```

消息流转路径：
```
Browser HTTP → IM 服务 → WebSocket relay.message → Gateway → InboundPipeline → Kernel HTTP → Agent 执行 → 回复 → OutboundRouter → Web IM
```

### 5.3 检查节点状态

```bash
curl -s http://127.0.0.1:8011/im/v1/nodes | python -m json.tool
# 应显示 gateway 节点 status=online
```

## 6. Smoke 测试脚本

项目内置了 smoke 测试脚本，可自动验证 Gateway 启动/常驻/关闭生命周期：

```bash
PYTHONPATH=src python -m personal_assistant.smoke_runtime \
  --config /path/to/node-config.yaml \
  --ready-timeout 20 \
  --steady-seconds 0.5 \
  --shutdown-timeout 10
```

预期输出：
```
READY pid=<pid> url=http://127.0.0.1:8000/v1/health
RUNNING steady_seconds=0.5 alive=true
SHUTDOWN exit_code=0
```

## 7. 设备绑定

```bash
# 发起绑定
curl -s -X POST http://127.0.0.1:8011/im/v1/bind \
  -H "Content-Type: application/json" \
  -d '{"action": "start", "node_id": "my-macbook"}' | python -m json.tool

# 确认绑定（使用返回的 bind_id）
curl -s -X POST http://127.0.0.1:8011/im/v1/bind \
  -H "Content-Type: application/json" \
  -d '{"action": "confirm", "bind_id": "<bind_id>", "user_id": "<user_id>"}' | python -m json.tool

# 验证归属
curl -s "http://127.0.0.1:8011/im/v1/me?user_id=<user_id>" | python -m json.tool
# owned_node_ids 应包含 my-macbook
```

## 8. 故障排查

| 现象 | 可能原因 | 排查步骤 |
|---|---|---|
| Gateway 启动后立即退出 | 内核健康检查超时 | 确认内核进程已启动且 `/v1/health` 返回 `{"healthy": true}` |
| WebSocket 连接失败 | IM 服务未启动或端口不匹配 | 确认 IM 服务在 `im_service.url` 所指端口监听 |
| 消息发送后无回复 | 无 LLM API key | 设置 `NANO_MULTIAGENT_LLM_API_KEY` 环境变量 |
| 节点显示 offline | Gateway 未连接或已断开 | 检查 Gateway 进程是否存活；检查 IM 服务日志 |
| 401 Unauthorized | Token 不匹配 | 确认 Gateway config 的 `kernel.token` 与内核的 `NANO_MULTIAGENT_API_TOKEN` 一致 |
| `workspace_root does not exist` | 配置路径不存在 | 创建 `workspace_root` 指向的目录 |

## 9. IM 离线降级

IM 服务离线时，Gateway 以本地自治模式运行：
- 外部 IM channel（如 QQ/飞书）通过本地 channel 适配器直接工作，不受 IM 影响
- Heartbeat 调度完全在本地，不依赖 IM
- WebSocket 断开后 Gateway 自动指数退避重连（最长 60 秒间隔）
- 重连后自动重新注册节点

## 10. 自动化验收测试

完整的真实进程联调验收测试：

```bash
cd <repo>
PYTHONPATH=src python -m pytest tests/e2e/test_m112_real_process_roundtrip_e2e.py -v
```

覆盖的 SPEC 验收条目：
- NodeGateway-SPEC §16: 1(channel启动), 2(四步决策), 4(回发原目标), 5(IM离线降级), 6(heartbeat)
- IM-SPEC §12: 1(消息往返), 3(设备绑定), 5(节点状态), 9(离线降级), 10(幂等)
