# Verification Report: refactor-459

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 18/18（15/15 milestone 退出项；3/3 Requirements 有实现） |
| Correctness | 7/8 Scenario 完全匹配；1/8 有顺序偏差 |
| Coherence | 关键 seam 与架构边界遵守；1 处 design typed-result 约束与行为不变目标冲突 |

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).

## Completeness

- Tasks: 15/15 complete。M1、M2、M3 各 5 项退出标准均已勾选，Roadpoint 全部为 `DONE`。
- Spec / 首文档覆盖: 3/3 Requirements 均有实现；8 个 Scenario 中 7 个完全覆盖，Node 注册状态 Scenario 有 1 处顺序偏差，详见 `W1`。
- Prototype / Reference 覆盖: N/A。design 与三个 milestone 均明确无前端、视觉或 reference contract 变化。
- 永久回归面完整：新增 5 个测试文件均低于 `docs/TESTING_GUIDE.md` 的 400 行软上限；interface 行为、真实 SQLite、HTTP/WS 接线、架构 seam 与关键重启旅程均有对应测试。
- 本轮独立门禁：
  - 聚焦 persistence / HTTP / WS 集合：`126 passed, 1 skipped`。
  - `pytest -q -m 'not e2e'`：`3483 passed, 2 skipped, 23 deselected`。
  - `pytest -q tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py::test_restart_readiness_rejects_pre_restart_online_snapshot`：`1 passed`。
  - `ruff check .`：通过；`ruff format --check .`：`778 files already formatted`。
  - `git diff --check origin/main...HEAD`：通过。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| owner 只能访问自己的会话与消息 | `src/IM/infra/repositories.py:713`; `src/IM/api/routes/web_im.py:178` | `tests/im_service/integration/test_auth_multiuser_isolation.py:28`; `tests/im_service/integration/test_routes_require_auth.py:64` | covered |
| direct 与 group 会话继续稳定持久化 | `src/IM/infra/repositories.py:376`; `src/IM/infra/repositories.py:1700` | `tests/im_service/integration/test_messages_api.py:45`; `tests/im_service/integration/test_group_chat_flow.py:145` | covered |
| 外部 channel shadow conversation 保持幂等 | `src/IM/infra/repositories.py:519`; `src/IM/application/web_im_service.py:76`; `src/IM/api/routes/web_im.py:308` | `tests/im_service/unit/test_conversation_repository_intents.py:84`; `tests/im_service/integration/test_messages_api.py:71` | covered |
| Node 注册和状态变化继续实时可见 | `src/IM/infra/gateway_persistence.py:98`; `src/IM/ws/gateway_handler.py:902`; `src/IM/ws/user_stream.py:136` | `tests/im_service/unit/test_gateway_node_persistence.py:37`; `tests/im_service/unit/test_gateway_status_broadcast.py:62`; `tests/im_service/unit/test_offline_guard.py:52` | 偏离：注册时多 Agent 广播顺序被排序，见 `W1` |
| relay 投递与回执继续收口 | `src/IM/ws/gateway_handler.py:1291`; `src/IM/ws/gateway_handler.py:1923` | `tests/im_service/integration/test_gateway_websocket_api.py:214`; `tests/im_service/unit/test_relay_service_task.py:66` | covered |
| group reply context 与 agent 间投递保持不变 | `src/IM/infra/gateway_persistence.py:307`; `src/IM/ws/gateway_handler.py:1312`; `src/IM/ws/gateway_handler.py:1629` | `tests/im_service/unit/test_gateway_conversation_persistence.py:148`; `tests/im_service/unit/test_gateway_handler.py:315`; `tests/im_service/unit/test_gateway_handler.py:521` | covered |
| 工具、思考、权限与终态事件实时展示并可回放 | `src/IM/infra/repositories.py:3096`; `src/IM/ws/user_stream.py:191`; `src/IM/application/event_service.py:32` | `tests/im_service/unit/test_event_bridge.py:136`; `tests/im_service/unit/test_event_bridge.py:186`; `tests/im_service/unit/test_event_bridge.py:258`; `tests/im_service/integration/test_user_stream_auth.py:41` | covered |
| 使用既有数据库重启 IM | `src/IM/infra/db.py:165`; `src/IM/infra/gateway_persistence.py:441`; `tests/e2e/critical_paths/_im_client.py:91` | `tests/im_service/unit/test_db_init.py:50`; `tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py:65`; M3 `progress.md` 同 DB 重启证据 | covered |

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 1. caller-oriented seam，不建万能 facade | 是 | `src/IM/infra/repositories.py:376`; `src/IM/infra/repositories.py:3096`; `src/IM/infra/gateway_persistence.py:81`; `src/IM/infra/gateway_persistence.py:292` |
| 2. concrete SQLite，无 Port/Protocol/fake | 是 | `src/IM/infra/gateway_persistence.py:6`; `tests/im_service/unit/test_gateway_node_persistence.py:16`; `tests/im_service/unit/test_gateway_conversation_persistence.py:22` |
| 3. GatewayHandler 只保留协议/连接/投递编排 | 是（广播输入顺序冲突另见 `W1`） | `src/IM/ws/gateway_handler.py:71`; `tests/contract/test_im_persistence_seam_contract.py:74` |
| 4. Web IM/user-stream 深化既有 repository | 是 | `src/IM/application/web_im_service.py:76`; `src/IM/ws/user_stream.py:108`; `src/IM/infra/repositories.py:3257` |
| 5. sequencing 收口但不新增 operation transaction/lock | 是 | `src/IM/infra/gateway_persistence.py:81`; `src/IM/infra/gateway_persistence.py:189`; `tests/im_service/unit/test_gateway_node_persistence.py:116` |
| 6. owner policy 由 caller 显式提供且不 repair | 是 | `src/IM/infra/gateway_persistence.py:345`; `src/IM/ws/gateway_handler.py:1662`; `tests/contract/test_im_persistence_seam_contract.py:82` |
| 7. dispatch DDL 归 schema initialization 且 shape 不变 | 是 | `src/IM/infra/db.py:165`; `tests/im_service/unit/test_db_init.py:50` |
| 8. replace-don't-layer，interface 是 test surface | 是 | `tests/im_service/unit/test_gateway_conversation_persistence.py:52`; `tests/im_service/unit/test_gateway_node_persistence.py:37`; `tests/contract/test_im_persistence_seam_contract.py:39` |
| 9. 三个纵向 milestone 串行且无双实现 | 是 | `src/IM/app.py:318`; `src/IM/app.py:319`; `docs/changes/refactor-459-im-persistence-depth/M3-gateway-delivery-persistence/progress.md:1` |

### Architecture self-consistency

- 依赖方向保持：生产改动闭合在 `src/IM/`；未引入 `agent` / `personal_assistant` import，也未让 IM 直接读取 Gateway workspace。
- raw connection locality 保持：目标 application/route/WS callers 无 `._connection`、`execute`、`commit`；静态合同覆盖该边界（`tests/contract/test_im_persistence_seam_contract.py:39`）。
- 未建立平行 read model 或单 adapter Protocol；Gateway cross-table persistence 分为 node/conversation 两个 concrete module。
- `app.state.connection` 仅在 composition/lifecycle 与既有允许路径保留；GatewayHandler 显式注入两个 persistence module、MessageRepository 与 EventBridge（`src/IM/app.py:318`）。

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

- **W1 — `node.register` 改变了多 Agent 状态广播的帧/seq 顺序。** 首文档要求重构前后 WebSocket 帧与 Node/Agent 状态变化时机保持一致（`docs/changes/refactor-459-im-persistence-depth/motivation.md:45`、`:50`、`:71`）。重构前 `_handle_register` 将协议帧的 `agents` 原顺序直接传给 `_broadcast_status_change`；当前 `GatewayNodePersistence.register()` 却在 `src/IM/infra/gateway_persistence.py:204` 返回 `tuple(sorted(agent_ids))`，并由 `src/IM/ws/gateway_handler.py:950` 逐个分配 seq/广播。若 Gateway 上报 `['zeta', 'alpha']`，浏览器现在会先收到 `alpha`，属于 behavior-preserving scope 内的可观察偏差；现有广播测试只使用已排序数据，未捕获该回归。**修复建议：**让 `GatewayRegistrationResult.agent_ids` 保留协议顺序（例如 `tuple(agent_ids)`），同时把 `design.md:274` 的“稳定排序”修正为“协议顺序”，并在 `tests/im_service/unit/test_gateway_status_broadcast.py:89` 增加非字典序 advertisement，断言 `agent.status_changed` 的 agent_id 与 seq 顺序和输入一致。heartbeat/disconnect 仍可沿用按 DB 查询的稳定排序，因为重构前这两条路径本就 `ORDER BY agent_id`。

### SUGGESTION（可以修）

无。

# Round 2

## Verification Report: refactor-459

### Summary

Mode: full
Delta range: `60035122..1dab03a4`
Focus issues: `W1 node.register advertisement/broadcast order`
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 22/22（19/19 milestone 退出项；3/3 Requirements 有实现） |
| Correctness | 8/8 Scenario covered；W1 closed |
| Coherence | 生产实现遵守架构与 transaction 决策；design 有 1 处 post-acceptance 同步遗漏 |

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).

## Completeness

- Tasks: 19/19 complete。M1–M3 各 5 项、M4 共 4 项退出标准全部勾选，所有 Roadpoint 为 `DONE`。
- Spec / 首文档覆盖: 3/3 Requirements、8/8 Scenario 均有实现与永久回归证据；上一轮 W1 已由 M4 的真实 FastAPI user/gateway WS 测试关闭。
- M4 dispatch winner 完成：两个独立 SQLite connection/handler 竞争同一 dispatch key 时，两条已提交 message 仍保留，只有 durable winner 产生 relay，两个 ack 均复用 winner。
- Reviewer HTTP duplicate finding 已在 `origin/main` 与 unit 使用相同公开入口、headers、body 做差分，两边均为两条不同 message，确认是 baseline-equivalent；本 refactor 未改变该既有行为（`M4-fix-dispatch-order/progress.md:7`）。
- Prototype / Reference 覆盖: N/A。无前端、视觉或 reference contract 变化。
- 本轮独立门禁：
  - 聚焦 persistence / HTTP / WS 集合：`129 passed, 1 skipped`。
  - dispatch cross-connection regression 连续执行 20 次：`20/20 passed`。
  - `pytest -q -m 'not e2e'`：`3484 passed, 2 skipped, 23 deselected`。
  - `ruff check .`：通过；`ruff format --check .`：`779 files already formatted`。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| owner 只能访问自己的会话与消息 | `src/IM/infra/repositories.py:713`; `src/IM/api/routes/web_im.py:178` | `tests/im_service/integration/test_auth_multiuser_isolation.py:28`; `tests/im_service/integration/test_routes_require_auth.py:64` | covered |
| direct 与 group 会话继续稳定持久化 | `src/IM/infra/repositories.py:376`; `src/IM/infra/repositories.py:1700` | `tests/im_service/integration/test_messages_api.py:45`; `tests/im_service/integration/test_group_chat_flow.py:145` | covered |
| 外部 channel shadow conversation 保持幂等 | `src/IM/infra/repositories.py:519`; `src/IM/application/web_im_service.py:76`; `src/IM/api/routes/web_im.py:308` | `tests/im_service/unit/test_conversation_repository_intents.py:84`; `tests/im_service/integration/test_messages_api.py:71`; M4 main/unit 差分证据 | covered（baseline unchanged） |
| Node 注册和状态变化继续实时可见 | `src/IM/infra/gateway_persistence.py:98`; `src/IM/infra/gateway_persistence.py:205`; `src/IM/ws/gateway_handler.py:902` | `tests/im_service/integration/test_status_broadcast_e2e.py:61`; `tests/im_service/unit/test_gateway_status_broadcast.py:157`; `tests/im_service/unit/test_offline_guard.py:52` | covered；W1 closed |
| relay 投递与回执继续收口 | `src/IM/infra/gateway_persistence.py:442`; `src/IM/ws/gateway_handler.py:1727`; `src/IM/ws/gateway_handler.py:1923` | `tests/im_service/unit/test_gateway_dispatch_concurrency.py:64`; `tests/im_service/integration/test_gateway_websocket_api.py:214`; `tests/im_service/unit/test_relay_service_task.py:66` | covered |
| group reply context 与 agent 间投递保持不变 | `src/IM/infra/gateway_persistence.py:307`; `src/IM/ws/gateway_handler.py:1312`; `src/IM/ws/gateway_handler.py:1629` | `tests/im_service/unit/test_gateway_conversation_persistence.py:148`; `tests/im_service/unit/test_gateway_handler.py:315`; `tests/im_service/unit/test_gateway_dispatch_concurrency.py:64` | covered |
| 工具、思考、权限与终态事件实时展示并可回放 | `src/IM/infra/repositories.py:3096`; `src/IM/ws/user_stream.py:191`; `src/IM/application/event_service.py:32` | `tests/im_service/unit/test_event_bridge.py:136`; `tests/im_service/unit/test_event_bridge.py:186`; `tests/im_service/unit/test_event_bridge.py:258`; `tests/im_service/integration/test_user_stream_auth.py:41` | covered |
| 使用既有数据库重启 IM | `src/IM/infra/db.py:165`; `src/IM/infra/gateway_persistence.py:442`; `tests/e2e/critical_paths/_im_client.py:91` | `tests/im_service/unit/test_db_init.py:50`; `tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py:65`; M3/M4 真栈证据 | covered |

### W1 closure

- `GatewayNodePersistence.register()` 现在返回 `tuple(agent_ids)`，保留 protocol advertisement 顺序（`src/IM/infra/gateway_persistence.py:202`）。
- 真实 FastAPI `/im/ws/gateway` + owner `/im/ws/user` regression 使用 `agent-z, agent-a`，断言 online agent frames 同序且 seq 递增（`tests/im_service/integration/test_status_broadcast_e2e.py:61`）。
- heartbeat/disconnect 仍通过 `_agent_ids()` 的 `ORDER BY agent_id` 读取稳定 DB 顺序（`src/IM/infra/gateway_persistence.py:284`）。
- 结论：`W1 closed`。

### M4 dispatch winner / 非原子边界

- 顺序未收紧：handler 先通过 MessageRepository/EventBridge 提交 message（`src/IM/ws/gateway_handler.py:1710`），之后才调用 `record_dispatch()`（`:1730`）；未新增跨 operation transaction、global lock 或 schema 变更。
- SQLite durable row 仍是跨 process authority：`INSERT OR IGNORE` 后 commit，再读回 winner（`src/IM/infra/gateway_persistence.py:468`）。
- loser 不 enqueue relay，并把 conversation/target/message ack 切到 durable winner（`src/IM/ws/gateway_handler.py:1746`、`:1766`）。
- 两 connection 测试明确断言 `messages == 2`，但 `relay_tasks == [winner.message_id]`，两个 ack 同时引用 winner（`tests/im_service/unit/test_gateway_dispatch_concurrency.py:97`）。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 1. caller-oriented seam，不建万能 facade | 是 | `src/IM/infra/repositories.py:376`; `src/IM/infra/repositories.py:3096`; `src/IM/infra/gateway_persistence.py:81`; `src/IM/infra/gateway_persistence.py:293` |
| 2. concrete SQLite，无 Port/Protocol/fake | 是 | `src/IM/infra/gateway_persistence.py:6`; `tests/im_service/unit/test_gateway_dispatch_concurrency.py:25` |
| 3. GatewayHandler 只保留协议/连接/投递编排 | 是 | `src/IM/ws/gateway_handler.py:71`; `tests/contract/test_im_persistence_seam_contract.py:74` |
| 4. Web IM/user-stream 深化既有 repository | 是 | `src/IM/application/web_im_service.py:76`; `src/IM/ws/user_stream.py:108`; `src/IM/infra/repositories.py:3257` |
| 5. sequencing 收口但不改变 transaction boundary | 是 | `src/IM/infra/gateway_persistence.py:84`; `src/IM/ws/gateway_handler.py:1710`; `tests/im_service/unit/test_gateway_dispatch_concurrency.py:110` |
| 6. owner policy 由 caller 显式提供且不 repair | 是 | `src/IM/infra/gateway_persistence.py:346`; `src/IM/ws/gateway_handler.py:1662`; `tests/contract/test_im_persistence_seam_contract.py:82` |
| 7. dispatch DDL 归 schema initialization且 shape 不变 | 是 | `src/IM/infra/db.py:165`; `tests/im_service/unit/test_db_init.py:50` |
| 8. replace-don't-layer，interface 是 test surface | 是 | `tests/im_service/unit/test_gateway_conversation_persistence.py:52`; `tests/im_service/unit/test_gateway_dispatch_concurrency.py:64`; `tests/contract/test_im_persistence_seam_contract.py:39` |
| 9. 纵向 milestone 串行且无双实现 | 是（design 文字未完整同步 M4，见 `R2-W1`） | `src/IM/app.py:318`; `docs/changes/refactor-459-im-persistence-depth/M4-fix-dispatch-order/tasks.md:26` |

### Architecture self-consistency

- 生产改动仍闭合于 `src/IM/`，依赖方向和跨机边界未改变。
- GatewayHandler 未恢复 raw connection / SQL；M4 继续消费 persistence typed winner。
- 跨 process authority 复用既有 SQLite dispatch log，没有新增 process-local 假全局互斥或平行 idempotency 机制。
- M4 保留 message-before-dispatch 的既有非原子副作用，未把 refactor 偷换成 transaction redesign。

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

- **R2-W1 — post-acceptance design 同步不完整，仍保留会重新引入 W1 的冲突约束。** Changelog 已明确把 `GatewayRegistrationResult.agent_ids` 修正为 Gateway advertisement 顺序（`docs/changes/refactor-459-im-persistence-depth/design.md:8`），M4 退出标准和实现也一致；但关键 typed-result 表仍写 `agent_ids 稳定排序`（`:278`）。同一 design 的决策 9 与 milestone 概述仍称“ 三个/三段 ”（`:230`、`:396`），而 milestone 表已有 M4（`:403`）。这使实现虽然正确，却无法被 design 唯一解释，后续 worker 依表实现会重新引入上一轮 W1。**修复建议：**把 `design.md:278` 改为“register 保留 protocol advertisement 顺序；NodeTransition 使用稳定 DB 顺序”，并把 `:230`、`:232`、`:396` 更新为三段原始迁移 + 一段 post-acceptance M4 closure，保持 Changelog、关键决策、typed result 与 milestone 表一致；无需修改源码或测试。

### SUGGESTION（可以修）

无。
