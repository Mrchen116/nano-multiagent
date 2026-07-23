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

- Context: M2 需要以真 IM/Gateway 和能用工具的模型验证用户可见实时路径；关键路径客户端须从 typed HTTP timeline 中只取普通消息给回复轮询 consumer。
- Decision: 隔离 HOME/config 将预置和动态创建 Agent 都固定到 provider catalog 已注册的 `kimiCoding:kimi-for-coding`；`IMClient.list_messages()` 过滤 `type="message"` 并解包 `message`，不把 config boundary wrapper 交给普通消息 consumer；权限旅程显式配置后续子 Agent 仍需的 allowlist。
- Rationale: 动态 Agent 原先硬编码的 `kimiCoding:K2.6` 不在隔离 provider catalog，导致 Gateway 在真实上行路径明确报 `no registered provider for model: kimiCoding:K2.6`。随后 Doubao route 在背景通知和 created-agent 回复中返回无 terminal event，导致用户侧轮询超时；将整个验收栈收敛到已验证能完成 tool/agent 轮次的 Kimi route，消除同一套件的 route 分裂。权限测试的 PATCH 会替换 tool allowlist，必须保留后续旅程的 `agent`。这些均属验收配置/客户端适配，不改变 IM/Gateway 协议或 M2 production seam。
- Evidence:
  - Tests: `PYTHONPATH=src pytest tests/e2e/critical_paths/test_im_client.py -q` 先红（wrapper 与普通消息不等）后绿（1 passed）；Kimi route 下 created Agent 真栈路径为 `1 passed, 18 deselected`。
  - Entry: 隔离真栈完整运行验证 Agent config continuity、后台 bash 通知、前台 bash timeout、created Agent 回复、Gateway 韧性、群 @、fork、权限批准/拒绝、restart、stop run、subagent failure、subagent foreground 和 tool call。
  - Gateway HTTP/WS: 旧连接 replacement、非法 frame、online control RPC、Channel bootstrap、relay receipt、offline 503、`agent.message` 的实时 `message.created`/`message.completed`、刷新一致、幂等和双 owner 隔离，以及 M1 owner/message/policy/metrics 场景均由公开 HTTP/WS 真栈保留；精确 event/message/control/relay IDs 见本文件 R4 前次真栈记录。
  - E2E/Regression: `HOME=<isolated> scripts/e2e-critical.sh -m "not slow"` 为 `17 passed, 2 deselected in 333.17s`。`PYTHONPATH=src pytest -m "not e2e"` 为 `3676 passed, 1 skipped, 22 deselected`；`PYTHONPATH=src pytest tests/ --collect-only -q` 为 `3699 tests collected`；`ruff check .`、`ruff format --check .`、`git diff --check` 通过。
  - Frontend State Matrix / Browser QA / Visual / Prototype Comparison: N/A；未修改前端，用户可见实时事件由真实 `/im/ws/user` 验证。
- Rollback: C2 前可回退至 `fd4c7dc29`。
- Commits: C1=`13a84ae2d`，C2=`7da848968`、`ca1051d1f`、`c9bf98477`、`85516fc34`，C3=`748fdde9d`；follow-up C2=`5a61bceea`，C3=本提交。
- Next: R4 已完成；终态 follow-up 已合并至 `f282ba8c2`。
