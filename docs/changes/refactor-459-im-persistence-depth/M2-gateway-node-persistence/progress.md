# refactor-459-M2 — Progress

## 基线

- Context: M2 开始前确认 node/register/status/offline 与 M1 seam contract 的现有行为可用。
- Evidence: `pytest -q tests/contract/test_im_persistence_seam_contract.py tests/im_service/unit/test_gateway_handler.py tests/im_service/unit/test_gateway_status_broadcast.py tests/im_service/unit/test_offline_guard.py tests/im_service/unit/test_nodes_metrics_repositories.py tests/im_service/integration/test_gateway_im_registration.py tests/im_service/integration/test_gateway_websocket_api.py` → `76 passed`。

## R1 — GatewayNodePersistence interface 与 durable failure compatibility

- 状态：DONE
- Context: GatewayHandler 同时拥有 node/profile/user repository 构造、逐 agent 默认值与 preserve 规则、binding/stale SQL 以及 commit placement；简单改成外层 transaction 会改变 agent N 失败后的已提交数据。
- Decision: 新增 concrete `GatewayNodePersistence` 与 immutable `GatewayRegistrationResult` / `NodeTransition`。register 复用既有 repository write，并刻意保留“node commit → 每个 profile/user commit → binding pending → stale + final commit”的 sequencing；没有 `with connection`、`BEGIN` 或 lock。heartbeat/offline/stale scan 由同一 seam 返回 handler 所需 domain facts。
- Rationale: caller-oriented operation 隐藏跨表 schema/顺序，同时不虚构原子性。真实 SQLite trigger 在第二个 agent profile INSERT 注入 `RAISE(FAIL)`，验证的是数据库 durable rows，而非 mock 调用次数。
- Evidence:
  - Tests: `pytest -q tests/im_service/unit/test_gateway_node_persistence.py` → `7 passed`；目标 `ruff check`、`ruff format --check` 全绿。
  - Entry: R1 是 persistence interface；真实 Gateway WS 接线与广播在 R2/R3 验证。
  - Durable failure baseline（重构前 GatewayHandler，真实 SQLite trigger 在 `agent-b` INSERT 失败）：`nodes=[('node-1','online',2,'v1')]`；`profiles=[('agent-a', node_id=None, display_name='A', workspace_root='/a', is_stale=0)]`；`users=[('agent:agent-a','A')]`；`connection.in_transaction=False`。
  - Durable failure after（重构后 `GatewayNodePersistence.register`，同一 trigger / agent 顺序 / payload）：与 baseline 逐项完全相同；尤其 node 已提交、agent-a profile/user 已提交、agent-a binding 因 agent-b failure 所在 transaction 回滚而仍为 `NULL`，没有整次 register 回滚，也没有额外提交 binding。
  - Frontend State Matrix: N/A（无前端变化）。
  - Browser QA: N/A（无前端变化）。
  - E2E/Regression: `tests/im_service/unit/test_gateway_node_persistence.py` 使用真实临时 SQLite 覆盖 first register、re-register preserve、empty advertise、stale reconcile、heartbeat、offline no-op/error、stale cutoff 与 agent-N failure durable state。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退到 C1 `ac81fc57` 可移除 module 实现并保留失败 interface 测试。
- Commits: C1=`ac81fc57`；C2=`7bb94d7a`；C3=本次 docs commit。
- Next: R2 将 handler node lifecycle 改为只消费 typed outcome，并保持 WS ack/广播不变。

## R2 — Gateway handler node lifecycle 接线与广播不变

- 状态：DOING

## R3 — Timeout scan 与 seam contract 收口

- 状态：TODO
