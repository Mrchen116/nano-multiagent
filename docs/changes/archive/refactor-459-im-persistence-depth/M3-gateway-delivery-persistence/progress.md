# refactor-459-M3 — Progress

## 基线

- `pytest -m "not e2e"`: 3474 passed, 2 skipped, 22 deselected（2026-07-11）。
- 边界确认: 当前 agent-message caller 必须显式传 `caller_owner_id=None`；不推断 owner，不 repair 历史 conversation，不新增 orphan-owner 产品断言，不修 issue #128。

## R1 — 建立 Gateway conversation persistence interface

- Context: Gateway handler 自己创建 dispatch table，并掌握 target 解析、direct conversation、fanout 与 dispatch-log SQL，无法把 persistence interface 当成稳定 test surface。
- Decision: 在 `infra/db.py` 中原样初始化 dispatch table；新增 `GatewayConversationPersistence` 及 immutable typed results，集中 target、canonical direct、fanout、first-write-wins、system identity、node/usage lookup。`resolve_send_target` 只消费 caller 显式传入的 owner policy。
- Rationale: concrete SQLite module 能隐藏跨 users/profiles/conversations/dispatch-log 的查询与顺序，不引入单 adapter Protocol；`caller_owner_id=None` 保留现有 agent-message 语义，不把 issue #128 混入 refactor。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_db_init.py tests/im_service/unit/test_gateway_conversation_persistence.py` → 13 passed；相关 ruff check/format 通过。
  - Entry: 真 SQLite `GatewayConversationPersistence` interface 覆盖 explicit/implicit agent/user/conversation target、canonical reuse、caller-supplied owner、missing node、group peer 排序/过滤、dispatch first-write-wins 和 system/usage lookup。真进程产品入口留在 R2。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 永久 regression 在 `tests/im_service/unit/test_gateway_conversation_persistence.py` 和 `test_db_init.py`；真进程临时验收属 R2。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `87eedb9e` 回退 module/DDL，revert `b082f411` 回退对应测试。
- Commits: C1=`b082f411`, C2=`87eedb9e`, C3=本文档提交。
- Next: R2 将 handler/composition 切换到新 seam，并完成真进程恢复验收。

## R2 — 收口 handler 并完成真栈恢复验收

- Context: handler 仍从 `ConversationRepository._connection` 反向构造 user/message repository，并自行查 group participant/profile、dispatch log、target node、system user 与 usage owner。
- Decision: composition root 显式注入 `GatewayConversationPersistence`、`MessageRepository` 和 `EventBridge`；handler 只消费 typed result 并保留 WS/relay/event 编排。删除 handler 内重复 target/direct/dispatch helper 与被替代的 private-state target 测试。agent-message 路径显式传 `caller_owner_id=None`；heartbeat owner-direct 单独保留 human creator 与 caller owner 输入。
- Rationale: 这使 handler 源码无 raw connection/SQL，同时不用新 module 推断 owner，不混入 issue #128。
- Evidence:
  - Tests: 聚焦 handler/module/contract 100 passed；IM + contract 509 passed；最终 `pytest -m "not e2e"` → 3483 passed, 2 skipped, 23 deselected；`ruff check .` 与 `ruff format --check .` 全绿。
  - Entry: 真 Gateway `POST /internal/dispatch` 经 Gateway WS 到 IM；user/conversation/agent target 均返回正确 kind/id/conversation/message ack。user 与 conversation target 的消息均为 `completed`，各自持久 `message.created(completed)` + `message.completed(completed)`。完整 e2e-critical 中 relay/group directed mention/unmentioned silence 真栈通过。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `PATH=.venv/bin:$PATH ./scripts/e2e-critical.sh -m "not slow"` → 15 passed, 2 deselected (262.88s)。专项同 DB 重启前后，`default-agent:m3-owned-restart-key` 重放 ack 返回原 message id `cd01474de42440729d8cb0a364c4eabe`；DB 前后均为 dispatch=1/messages=1/events=3，HTTP 历史中原 completed 消息=1、replay 文本=0。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `5f802e29` 恢复 handler 旧 persistence 路径，revert `81e3ea76` / `f3999379` 回退对应边界测试。
- Commits: C1=`81e3ea76` + `f3999379`, C2=`5f802e29`, C3=本文档提交。
- Next: R3 已完成；milestone 可合入 unit branch。

## R3 — 根治 Gateway 重启验收的 stale-online readiness

- Context: 完整 e2e 在 Gateway restart 后连续复现 503；时间线为旧 node `GET /nodes` 200 先命中、消息 POST 503，之后 replacement Gateway WS 才 accepted/config sync。旧 log marker 也会让 restart helper 提前返回。
- Decision: 新增确定性 regression，restart journey 记住同 node 重启前 heartbeat，等公开 `/nodes` 显示同 node `online` 且 heartbeat 严格前进。`restart_gateway` 只负责拉起/fail-fast，不再从 append-only 日志判定 ready。
- Rationale: generation 条件无法被旧 durable row 满足，且使公开状态成为唯一 readiness 真源；没有加 sleep 或放宽产品断言。
- Tracking: 根因取证期间建立 #187；经 orchestrator 确认为 M3 必跑门禁的 test-only 基础设施修复后，治本实现已落在 R3。
- Evidence:
  - Tests: 确定性 stale-online regression 1 passed；restart journey 连跑 3 次均通过（31.82s / 19.16s / 24.79s）。
  - Entry: 真 IM + Gateway 重启后会话上下文哨兵原样复述；最终完整 e2e-critical 15/15 selected 通过。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `test_restart_readiness_rejects_pre_restart_online_snapshot` + `test_context_survives_gateway_restart`；最终完整命令 15 passed, 2 deselected。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `b2ecd02f` + `5c1e30f0`，revert `5428a2ce` 回退红测。
- Commits: C1=`5428a2ce`, C2=`5c1e30f0` + `b2ecd02f`, C3=本 R3 文档提交。
- Next: milestone 已完成。
