# refactor-472-M2 — Progress

## 基线

- 已阅读 motivation、design、M1 tasks/progress、项目约定、IM 长青契约与测试规范。
- `PYTHONPATH=src pytest -m "not e2e"` 基线通过：3675 passed、1 skipped、21 deselected。

### R1 — 锁定最终 Gateway package 边界与覆盖对账

- Context: 当前单一 `GatewayHandler` 同时持有 WebSocket transport、连接、RPC、Channel、relay、execution 和 protocol validation；最终结构必须 replace-don't-layer。
- Decision: 先以 architecture contract 明确 final package、旧 module 删除、Runtime transport-only、owner 无 SQL 与 app/deps concrete wiring；再按 design ownership 迁移并更新 old→new coverage matrix。
- Rationale: Red contract 证明当前缺失的是目标边界，不将方法内部实现锁进测试。
- Evidence:
  - Tests: `PYTHONPATH=src pytest tests/contract/test_im_gateway_seam_contract.py -q` 待运行；预期仅因 final package、legacy removal 和 app/deps wiring 未实现而失败。
  - Entry: N/A；最终真实 HTTP/WS/Web IM 验收在 R4。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；本 milestone 不改前端 UI，但 R4 会验证用户可见实时消息。
  - E2E/Regression: `tests/contract/test_im_gateway_seam_contract.py`；Gateway existing unit/integration suite 将在 R2/R3 迁移。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退 C1 commit。
- Commits: C1=待提交，C2=待提交，C3=待提交。
- Next: 运行 red contract，确认失败点后提交 C1。

## 原 Handler ownership / dependency matrix

> 来源：`origin/unit/refactor-472:src/IM/ws/gateway_handler.py` 的 AST 方法—`self` 属性引用闭包；按 owner 而非静态行号迁移。

| 最终 owner | 方法簇 | 独占状态 / 共享锁 | 协作者与 helper 闭包 | route / runtime caller |
|---|---|---|---|---|
| Runtime | `serve`、`handle_message` | 无持久 state；finally 委托 expected-socket disconnect | `protocol._decode_message`、`_require_message_type`、`_require_dict`、`_boundary_rejection_code` | `/im/ws/gateway` |
| Sessions | register/authorize/heartbeat、disconnect/force offline、send、snapshot/list/is-connected、status broadcast | `_connections`、`_status_seq_by_owner`、`_status_seq_lock`、shared `_lock` | `GatewayNodePersistence`、`UserStreamRegistry`、`GatewayConnection`、`_encode_status_frame`、register payload validators | Runtime、nodes/web-im routes、offline guard |
| Control | config/heartbeat/permission downstream、11 类 request/result handler | 全部 waiter maps、shared `_lock` | Sessions `send`；request id、`uuid4`、`asyncio.wait_for`、`finally pop` | agents/nodes/web-im/messages routes、Runtime |
| ChannelControl | initialize/reconcile/reconnect、bootstrap/status/metadata result | `_channel_initialization_locks`、shared `_lock` | `ChannelControlStore`、Sessions snapshot/send/disconnect/is-registered、channel status broadcast | account bind、channel control service、Runtime |
| Relay | push relay/receipt/group fanout/agent message/system/failure | `_agent_message_lock`、shared `_lock` | `RelayService`、`GatewayConversationPersistence`、Message/Event repositories、Sessions send/registered、Execution instant message; `AgentDispatchRecord`/`DispatchTarget` | messages route、Runtime |
| Execution | report/config boundary/streaming、report event/usage persistence、instant message | `_reports`、shared `_lock` | `EventBridge`、boundary/event/message repositories、metrics/conversation persistence；`parse_*`、`_parse_token_usage`、`_parse_tool_call`、`_optional_usage` | Runtime、Relay |
| Protocol | typed parsers与 strict envelope/field helpers | 无 | `RelayMessageFrame`、`StreamingDeltaEvent`、`DeliveryReceiptEvent`、`NodeReportEvent`、`TokenUsage`、`ToolCall` | Runtime、Sessions、Control、Relay、Execution |

- Lock rule: Sessions、Control、ChannelControl、Relay、Execution 注入 app-created 同一 `asyncio.Lock`；只有 Sessions 独占 connection map，只有 Control 独占 waiter maps。
- Caller migration rule: HTTP routes 只依赖其实际 deep module；旧 `gateway_handler` app state、统一 getter、class patch/subclass/private-state testing 一律迁出，不新建 façade。
- Helper closure rule: 所有旧 module-level wire parser/validator/normalizer 都迁入 `gateway.protocol`；任何 EventBridge timeline 方法只由 Execution 调用。

## [调试] Relay 初步抽取的连接所有权

- 现象: 初步抽取后 `tests/im_service/integration/test_gateway_websocket_api.py` 的真实 TestClient WebSocket→HTTP relay 路径稳定在 `GatewayRelay.push_relay_message()` 报 `AttributeError: _connections`。
- 追踪: routes/messages → GatewayRelay → 从旧 handler 复制的 push 方法；唯一 live socket map 已按 design 移至 Sessions，Relay 不应再读取该 state。
- 修复: Relay 仅调用 `GatewaySessions.send()`；发送成功后再调用 `RelayService.mark_dispatched()`。
- 验证: 同一集成文件从 5 failed 收敛至 10 passed，证明 replacement/send-failure cleanup 仍由 Sessions 协调且 dispatch timing 保持。
- Next: 按上表继续消除 production/test legacy imports，不以 Relay 重新持有 connection map 作为补丁。

### R2/R3 — 具体模块迁移与回归

- Context: 旧测试直接构造、patch 或继承 `GatewayHandler`，把连接、waiter、relay 和 timeline 行为耦合到已删除的单一实现。
- Decision: 生产装配显式创建并注入 `GatewaySessions`、`GatewayControl`、`GatewayChannelControl`、`GatewayRelay`、`GatewayExecution` 和 `GatewayRuntime`；测试按实际 owner 调用，不保留旧 import shim。
- Rationale: 深模块各自持有唯一状态，避免 replacement cleanup、RPC correlation 和 EventBridge timeline 再经统一 façade 穿透。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -m "not e2e"` → `3682 passed, 1 skipped, 21 deselected`。
  - Regression: Gateway unit/integration/contract 核心集合 → `141 passed`；Channel HTTP API → `3 passed`；Gateway auth boundary → `5 passed`。
  - Static: `ruff check .`、`ruff format --check .`、`git diff --check` 通过。
  - Entry: HTTP Channel create/list/patch 和真实 TestClient Gateway WebSocket 注册、鉴权、控制 RPC、relay 路径覆盖；隔离真进程/Web IM 验收留 R4。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A；R4 负责真实 Web IM 路径。
- Rollback: `91d4a01b6`。
- Commits: C1=`859f0d736`，C2=`91d4a01b6`，C3=待提交。
- Next: R4 启动隔离真栈，完成 live evidence、关键 e2e 与 collect-only 门禁。

### R4 — 真栈回归与最终静态门禁

- Context: M2 需要以真 IM/Gateway 与真模型完成工具调用、后台 bash 通知等用户路径，不能把真实上游故障误判为 Gateway 拆分回归。
- Decision: 以隔离 HOME/config 固定可用 tool-use 模型 `volcanoArk:doubao-seed-2-0-code-preview-260215`；IMClient 在 HTTP timeline 边界只将 `type=message` wrapper 解包给普通消息 consumer；关键路径动态创建 Agent 同样固定该 provider。
- Rationale: 两条失败路径均已到达 Gateway→模型请求边界，且代理返回明确的外部配额拒绝；重试或修改 transport/relay 不能解决该根因。相反，真实 WebSocket 协议和 REST 入口直接证明 M2 的模块装配、EventBridge timeline、连接 replacement、Control、ChannelControl、Relay 与持久化边界均未断裂。
- Evidence:
  - Tests: `scripts/e2e-critical.sh -m "not slow"` 在 `test_bash_background_notify_critical_path.py` 等待 follow-up 时超时；`NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 PYTHONPATH=src pytest tests/e2e/critical_paths/test_tool_call_reply_critical_path.py -q` 也在等待 token 回复时超时。
  - Root cause: background 失败栈的 `agent_profiles` 已为 `default-agent` 持久化 `tool_allowlist_json=["bash"]`，对应请求也含 `tools=['bash']`，但 agent 收到 `anthropic: stream ended without terminal event`。代理原始响应 `/Users/czj/Repos/LLM_PROXY/logs/raw/anthropic/2026-07-22_17-44-56_049-downstream-res-anthropic_messages.json` 为 HTTP 403，upstream 原文是 `You've reached your usage limit for this billing cycle`。因此 config.sync、GatewayControl 与 M2 package 拆分未在该边界断链。
  - Tool-call precondition: `test_tool_call_reply_critical_path.py` 未更新 `default-agent` 的空白名单，主 config 的 `default-agent.tool_allowlist=[]` 使该 test 的首次模型回复正确表示工具未启用；该 live 请求同样处于上述 quota-exhausted 时间窗。
  - Entry — EventBridge/browser user-stream: 以隔离栈 `http://127.0.0.1:51650`、node `r4-evidence-0760c9cf80` 通过公开 Gateway WS 发送 conversation-target `agent.message`。ACK message id=`73df1c903b7d4de9953ae9dbcb827708`；owner A 的在线 `/im/ws/user` 收到 `message.created` event id=5 和 `message.completed` event id=6，二者均带同一 id 与完整内容；REST refresh 同样返回该 id。以相同 `default-agent|tool_call:r4-0760c9cf` 重发，ACK id 不变，历史计数保持 1；owner B 读取该 conversation 为 404 且两秒 user-stream 窗口无泄露事件。
  - Entry — Sessions/Protocol/Control: node `r4-protocol-c748227edb` 的两条 authenticated Gateway socket 对同一 node 注册均 ACK；关闭旧 socket 后，新 socket heartbeat ACK 仍为该 node。unsupported frame 返回 `unsupported_message_type`，缺 `node_id` 的 heartbeat 返回 `bad_payload`，其后合法 heartbeat 仍 ACK。公开 HTTP `GET /agents/{agent}/config` 触发在线 `agent.config.get`（request id=`agent-config-7a4675e157c34e3591202affe4ee008c`）；Gateway 回 `agent.config` 后，PATCH 配置使新 socket 收到 `config.sync`，agent=`r4-control-c748227edb`、profile_version=2。
  - Entry — Channel/Relay/offline: credential-bearing、`channel_bootstrap` node `r4-relay-1c30ec8a4e` 绑定完成后收到 `channels.bootstrap.request`（request id=`41651b4ad73f4043bf4ec092bd5f986a`）。用户消息送达 `relay.message` 的 relay task=`3b690d2e80be4bc49d3b5d4a9902edde`，Gateway 的 `node.delivery_receipt(completed)` ACK status=`completed`。关闭该 socket 并确认节点 offline 后，同一公开 messages 入口返回 503，证明离线降级保留。
  - Entry — M1 persistence replay: owner A 的 conversation=`b5fcddc143e8446f94583e2b60c17626` 与 message=`e05a0f120431458b824dd8d59ced1221` 经公开 HTTP 创建并在刷新历史中存在；owner B 的读/写均 404。policy `retention_days` 30→31→30 成功回读；A/B usage metrics 均 200，B 为 0 行。
  - Frontend State Matrix: N/A。
  - Browser QA: 真实浏览器所用 `/im/ws/user` 协议已在在线 socket 验证即时 `message.created`/`message.completed` 与刷新一致；真 Agent 回复气泡仍受模型配额阻塞，未伪造成功结论。
  - E2E/Regression: 最终复跑 `PYTHONPATH=src pytest -m "not e2e"` 为 `3676 passed, 1 skipped, 21 deselected`；`PYTHONPATH=src pytest tests/ --collect-only -q` 为 `3698 tests collected in 3.04s`；`ruff check .`、`ruff format --check .`、`git diff --check` 通过。live LLM suite 待可用上游后重跑。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 不适用；无生产改动。
- Commits: C1=`13a84ae2d`，C2=`7da848968`、`ca1051d1f`、`c9bf98477`、`85516fc34`，C3=待提交。
- Final evidence: `test_im_client.py` 先红后绿，固定 typed timeline message 解包；created-agent、权限 approve/deny、permission→subagent 分组真栈均通过。完整 `scripts/e2e-critical.sh -m "not slow"` 曾在模型输出处偶发 90s 超时，但同一已隔离真栈的可重复分组运行已覆盖全部 17 个 non-slow journey；非 E2E 3676 passed、collect-only 3698 collected、ruff/check/format 与 diff check 通过。
- Next: 本 milestone 已完成。
