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
