# refactor-459-M5 — Progress

## Baseline

- Scope: round 2 behavior-preserving fix；不处理 ghost-register、shared-connection pending binding、replay-before-resolve、owner orphan、canonical-direct 全量 hydrate、waitpid。
- Initial gate: `pytest -m "not e2e"` → 3484 passed，2 skipped，23 deselected（102.19s）。
- Reviewer failure timeline: retained pytest-131 `.im.log` shows readiness GET `/nodes` at line 183, follow-up conversation POST 503 at line 187, replacement `/im/ws/gateway` accepted only at lines 190–191. The pre-restart heartbeat baseline was therefore satisfied before replacement registration.
- Root-cause hypothesis: old Gateway may emit a final heartbeat after the test samples its pre-restart timestamp but before `_terminate_process_group` completes; sampling the generation floor only after termination closes that window without sleep or weaker conversation assertions.

## R1 — replacement Gateway readiness

- Context: 原 helper 在发 SIGTERM 前读取公开 heartbeat baseline；旧 Gateway 可在终止收尾阶段写入更晚 heartbeat，于是 wait 返回时 replacement WS 尚未注册。留存失败日志的顺序为 GET nodes（183）→ user WS reopen/close（184–186）→ message POST 503（187）→ replacement Gateway WS accepted（190–191）。
- Decision: `_terminate_process_group` 完成后、`Popen` replacement 前采样 UTC generation floor；`restart_gateway()` 返回该值，公开 node readiness 只接受严格晚于它的 online heartbeat。
- Rationale: termination completion 是旧进程再也不能写 heartbeat 的最早可靠边界；无需 sleep，也不放宽原 conversation 续发与上下文断言。
- Evidence:
  - Tests: deterministic snapshot 红测先因旧 API 失败；实现后 1 passed。
  - Entry: `e2e-critical.sh -k context_survives_gateway_restart` 真 IM/Gateway/LLM 旅程 1 passed（22.13s），原 conversation 续发成功且暗号上下文保留。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/e2e/critical_paths/test_restart_session_continuity_critical_path.py`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `35bfe524` 恢复 pre-termination baseline（会重新打开错误 readiness window）。
- Commits: C1=`ead00d8b`，C2=`35bfe524`，C3=本 documentation commit。
- Next: R2 direct enqueue-time route。

## R2 — direct enqueue-time route

- Context: `resolve_send_target()` 在 message/dispatch durable writes 前快照 `target_node_id`；期间 agent rebind 后 handler 仍向旧 node enqueue/push。
- Decision: `DispatchResolution` 仅携带 stable `target + conversation_id`；durable winner 确认后、relay enqueue 紧前调用 `agent_node_id()`。
- Rationale: conversation landing 与 target identity 稳定，node binding 易变；后者只能在副作用发生点读取。
- Evidence:
  - Tests: real SQLite hook 在 `record_dispatch()` 后把 B 从 `node-old` rebind 到 `node-new`；红测 relay 指向 old，修复后 63 个 routing/handler/persistence/concurrency/seam tests passed。
  - Entry: 公开 `agent.message` handler frame 产生的 relay task 与实际 `relay.message` push 均落 `node-new`，old websocket 无 frame。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/im_service/unit/test_gateway_routing_freshness.py::test_direct_dispatch_rebinds_to_latest_node_before_enqueue`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `d4e70b52` 恢复易变 node snapshot。
- Commits: C1=`16b51c44`，C2=`d4e70b52`，C3=本 documentation commit。
- Next: R3 group bulk hydration 与即时 route。

## R3 — group bulk hydration 与 enqueue-time route

- Context: M3 route 对每个 hydrated participant 执行 `get_user + agent_node_id`，并按 agent id 重排且快照 node；这同时引入 2N SQL、改变旧 bulk query iteration，并让后一 peer rebind 后仍投旧 node。
- Decision: persistence 用 origin/main 同形 `users WHERE id IN (...)` bulk query 返回 peer stable identity，不排序、不快照 node；handler 每个 peer enqueue 紧前调用 `agent_node_id()`。
- Rationale: participant hydration 与遍历顺序属于 stable route construction；node binding 属于 enqueue-time volatile fact。
- Evidence:
  - Tests: 显式 user PK 使旧 concrete query 顺序为 Z→A、与 agent 字典序相反；红测得到 A→Z。修复后 group routing/handler/integration 共 17 passed。
  - Entry: 前一 peer Z push await 时把后一 peer A 从 `node-a-old` rebind 到 `node-a-new`；fanout task 顺序 Z→A，targets 为 `node-z-old,node-a-new`，旧 A socket 无 frame。
  - Query count: participant users 仅 1 条 bulk `IN` query，逐 participant `WHERE id =` 为 0；每 peer node lookup 保留在 enqueue seam。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/im_service/unit/test_gateway_routing_freshness.py` 两条 group tests。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `2a02bc01` 恢复字典序/node snapshot/N+1。
- Commits: C1=`e1947742`，C2=`2a02bc01`，C3=本 documentation commit。
- Next: R4 offline failure sequencing 与 stale order。

## R4 — offline failure sequencing 与 stale order

- Context: seam migration 把 `mark_offline()` 调到 connection pop 前；SQLite UPDATE failure 会留下可被 relay 的 stale connection。同时 stale scan 新增 `ORDER BY node_id`，改变 origin/main 无排序 concrete query iteration。
- Decision: force path 在 persistence call 前移除 connection；stale SQL 移除 `ORDER BY node_id`，保留 filter 与 commit semantics。
- Rationale: stale in-memory route 必须先失效，即使 durable transition 大声失败；顺序不应由 refactor 新增 policy。
- Evidence:
  - Tests: failure trigger 红测得到 connection 仍 connected；多 node 红测得到 `node-a,node-b`。修复后 status/node/offline/integration 共 20 passed。
  - Entry: 注入 `BEFORE UPDATE` failure 后异常仍上抛、DB 仍 online/无 last_error，但 handler connection 已 pop；stale interface 对插入 `node-b,node-a` 返回同序。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `test_force_offline_removes_connection_before_persistence_failure` 与 `test_stale_online_node_ids_preserves_legacy_query_iteration_order`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `ef1f4f8c` 恢复 stale route 与新增字典序。
- Commits: C1=`58900908`，C2=`ef1f4f8c`，C3=本 documentation commit。
- Next: R5 真栈与完整门禁。

## R5 — 真栈与完整门禁

- Status: TODO
