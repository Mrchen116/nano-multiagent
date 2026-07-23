# Verification Report: refactor-472

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks complete；3/3 requirements implemented |
| Correctness | 10/10 motivation scenarios covered |
| Coherence | Followed（1 项测试边界 WARNING） |

本轮在 `ff9cc5d9e879ca219beb2efc9bf6684b47c4b53a` 验证。执行结果：

- 聚焦 persistence/Gateway 回归：`70 passed, 1 skipped`。
- `PYTHONPATH=src pytest -m "not e2e"`：`3676 passed, 1 skipped, 22 deselected`。
- `PYTHONPATH=src pytest tests/ --collect-only -q`：`3699 tests collected`；`ruff check .` 与 `ruff format --check .` 均通过。
- `scripts/e2e-critical.sh -m "not slow"`：`17 passed, 2 deselected`。

## Completeness

- Tasks: M1 5/5、M2 5/5 complete。两个 milestone 的退出标准均已标记完成；没有未完成 checkbox。
- 最终边界：`src/IM/infra/repositories.py`、`src/IM/ws/gateway_handler.py`、`src/IM/ws/gateway_protocol.py` 均已物理删除；两个 canonical package 的 `__init__.py` 均为空。`tests/contract/test_im_persistence_seam_contract.py:104-163` 与 `tests/contract/test_im_gateway_seam_contract.py:36-96` 将该结构和禁止 aggregate re-export 固化为回归契约。
- 原型 / Reference Contract: N/A。`design.md` 没有前端原型或 must-match reference contract；M2 的 Web IM 可观察事件链由真实 HTTP/WS 和 critical-path E2E 证据覆盖，而非视觉原型比较。

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 账号、租户与持久化数据稳定：owner scope、完整 timeline/read model、会话/Agent/节点管理 | `src/IM/infra/repositories/conversations.py:40-189`；`messages.py:64-300`；`agents.py`；`nodes.py`；`bindings.py`；`metrics.py` | `tests/im_service/integration/test_auth_multiuser_isolation.py:29-129`、`test_messages_api.py:265-285`、`test_account_binding_api.py:110`、`test_nodes_metrics_api.py:177-243`；M1 真栈记录 `M1-persistence-modules/progress.md:101-114` | covered |
| 刷新后完整会话历史、过程和投递状态不丢失或重复 | `src/IM/infra/repositories/messages.py:249-300`；`_message_projection.py`；`config_boundaries.py:107-144` | `tests/im_service/integration/test_messages_api.py:285`；`tests/im_service/contract/test_gateway_protocol_contract.py:175`；`tests/e2e/critical_paths/test_im_client.py:52-62` | covered |
| Gateway 注册、心跳、双向 relay 与在线状态 | `src/IM/ws/gateway/runtime.py:66-105`；`sessions.py:223-418`；`relay.py:51-93` | `tests/im_service/integration/test_gateway_websocket_api.py:63-128,193-245`；`tests/im_service/unit/test_gateway_status_broadcast.py:53-212` | covered |
| Web IM 消息实时回复，过程/投递状态与刷新一致 | `src/IM/ws/gateway/execution.py:147-397`；`relay.py:170-363`；`src/IM/application/event_bridge.py` | `tests/im_service/unit/test_gateway_handler.py:1494-1557`；`tests/e2e/critical_paths/test_bash_background_notify_critical_path.py`、`test_tool_call_reply_critical_path.py`；M2 真栈记录 `M2-gateway-modules/progress.md:67-80` | covered |
| replacement 后旧 socket 迟到断开不误伤新连接 | `src/IM/ws/gateway/sessions.py:73-108,291-317,401-418` | `tests/im_service/unit/test_gateway_handler.py:339`；`tests/im_service/integration/test_gateway_websocket_api.py` | covered |
| 非法或不支持 Gateway frame 有明确错误且连接/其他会话不受影响 | `src/IM/ws/gateway/runtime.py:74-89,122-141,182-195`；`execution.py:65-100` | `tests/im_service/contract/test_gateway_protocol_contract.py:141-156,437`；`tests/im_service/integration/test_gateway_websocket_api.py:547-624` | covered |
| 在线配置/control、Channel 与 RPC 的 request-id、timeout、empty fallback 和 finally cleanup 保持 | `src/IM/ws/gateway/control.py:94-148,253-557,559-787`；`channel_control.py:58-250` | `tests/im_service/integration/test_gateway_websocket_api.py:193-245`、`test_agent_channels_api.py:47-150`；Gateway control/unit suite 已纳入全量回归 | covered |
| 后台/群/外部事件不重复、owner 隔离且 user/conversation target 实时产生气泡 | `src/IM/ws/gateway/relay.py:170-363`（委托 `GatewayExecution.emit_instant_message`）；`execution.py:55-63` | `tests/im_service/unit/test_gateway_handler.py:626-702,1494-1557`；`tests/im_service/integration/test_gateway_auth_boundary.py:140-243`；`test_bash_background_notify_critical_path.py`、`test_group_chat_directed_mention_critical_path.py` | covered |
| Gateway/目标节点离线时返回既有降级反馈，配置中心/历史仍可用 | `src/IM/ws/gateway/sessions.py:401-418`；`relay.py:51-63`；API offline guard | `tests/im_service/integration/test_gateway_websocket_api.py:430-473,627-657`；`tests/e2e/critical_paths/test_gateway_im_resilience_critical_path.py` | covered |

M2 对 typed timeline 的 E2E client 适配也符合设计：`tests/e2e/critical_paths/_im_client.py` 的 `list_messages()` 只返回 `type="message"` 内部 message，回归断言在 `tests/e2e/critical_paths/test_im_client.py:21-62`，不会将 config-boundary wrapper 交给普通回复轮询 consumer。

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 1. repository 按 durable aggregate / transaction owner 拆分 | 是 | canonical modules 位于 `src/IM/infra/repositories/`；`messages.py:249-300` 保持 message、event、projection 的同 transaction 写入。 |
| 2. SQLite concrete seam，不新增 Protocol/fake adapter | 是 | repository constructors 直接接收 `sqlite3.Connection`，例如 `messages.py:50-61`、`events.py:42-54`；测试使用 schema 初始化的真实 SQLite。 |
| 3. `_event_rows` 仅 transaction-neutral private primitive | 是 | `src/IM/infra/repositories/_event_rows.py:11-46` 只有插入/映射，无 commit/notify；三 owner 直接使用，契约见 `test_im_persistence_seam_contract.py:145-156`。 |
| 4. 删除旧 repository 文件和聚合出口 | 是 | legacy file 缺失，`repositories/__init__.py` 为空，契约见 `test_im_persistence_seam_contract.py:104-124,159-163`。 |
| 5. Runtime + Sessions/Control/Channel/Relay/Execution 分属状态和流程 owner | 是 | `src/IM/app.py:332-380` 显式装配同一 lock 的具体协作者；`runtime.py:51-197` 仅做认证后 dispatch。 |
| 6. Sessions 连接状态和 Control waiter 状态各自独占、共享既有 lock，保持 request-id-only / finally cleanup | 是 | `sessions.py:65-71,73-108`；`control.py:94-120,122-148`，其余 RPC 使用同一登记—wait—finally pop 模式。 |
| 7. API routes/deps 使用窄 concrete module，不回到统一 facade | 是 | `src/IM/api/deps.py:214-231` 暴露分模块 getter；Gateway seam contract `:85-96` 禁止 `get_gateway_handler` / `GatewayHandler`。 |
| 8. replace-don't-layer，最终 interface/真实入口为测试面 | 部分遵守 | production 无 shim，主要测试已迁到 concrete graph/HTTP/WS；但仍有一条本轮迁移后的 private-method 单测，见 WARNING。 |
| 9. 不引入 spec delta 或跨机直接文件访问 | 是 | 变更没有 schema/协议兼容 facade；`GatewayControl` 仍通过 WS RPC 请求 workspace 数据（例如 `control.py:392-557`），IM 未直接读取 Gateway workspace。 |

架构自洽性检查通过：IM 没有新增对 `agent` / `personal_assistant` 的 import；Gateway transport owner 没有直接 SQL `execute` / `commit`（回归契约见 `tests/contract/test_im_gateway_seam_contract.py:45-68`）；已有 `EventBridge`、`Gateway*Persistence` 和 `ChannelControlStore` 被注入复用，未新建平行机制。

## Issues

### CRITICAL（提 PR 前必须修）

- 无。

### WARNING（应该修）

- **W1 — 仍有测试通过 private owner 方法断言实现细节，未完全满足 replace-don't-layer 测试面。** `tests/im_service/unit/test_gateway_handler.py:601-623` 在本次迁移后直接调用 `GatewayRelay._broadcast_group_reply_context()`，并以 `object()` 作为 task 只命中早退分支；该断言既不经 Runtime/receipt public flow，也无法证明真实的 “NO_REPLY 不创建 peer relay” 行为。`tests/im_service/unit/test_gateway_handler.py:852` 也通过 `execution._event_bridge` 设置前置状态。按 `design.md:221-227` 和 `docs/TESTING_GUIDE.md:9-13`，应把前者改为经 `GatewayRuntime.handle_message()` 发送包含有效 relay task 的 completed receipt（或经已公开的 Relay receipt interface），然后断言无 peer relay；后者应让 fixture 显式返回其构造的 `EventBridge`，避免穿透 `GatewayExecution` 私有字段。随后按 owner 拆分/重命名 `test_gateway_handler.py`，避免旧 Handler 名称继续成为测试组织边界。

### SUGGESTION（可以修）

- 无。

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).
