# refactor-459-M4 — Progress

## Baseline

- Scope: behavior-preserving round 1 fix；不修改 motivation/spec，design 只读。
- Initial gate: `PATH=.venv/bin:$PATH pytest -m "not e2e"` → 3483 passed, 2 skipped, 23 deselected（102.15s）。
- Reviewer HTTP duplicate differential: **reviewer finding baseline-equivalent**。两边均使用公开
  `POST /im/v1/conversations/{conversation_id}/messages`，headers 为 bearer auth、
  `Content-Type: application/json`、`Idempotency-Key: ref459-reviewer-same-key`，body 为同一
  user sender 与 `ref459 reviewer duplicate baseline` 正文；fresh DB 的 user/conversation id
  仅为运行实例标识，不参与语义差分。

| Observable | `origin/main` (`406234b2`) | unit (`60035122`) | Differential |
|---|---|---|---|
| shadow find-or-create statuses / same id | `201, 200` / true | `201, 200` / true | equal |
| message POST statuses | `201, 201` | `201, 201` | equal |
| message ids | `4c260308edc448d0a83b61285db0a569`, `b8e737d51c3e4bc3941db7f82865138e` | `f867224160f749fd9e9a9d0ef10b606a`, `05d47610155643a4a8e5605fa0f63c5e` | both distinct within branch |
| response delivery states | `sent, sent` | `sent, sent` | equal |
| 8s public history | 2 matching messages; `sent, sent` | 2 matching messages; `sent, sent` | equal |

结论：重复 HTTP `Idempotency-Key` 是 main 既有行为，禁止在本 refactor 修产品行为；reviewer 应针对性更正该项 refactor verdict。

## R1 — 恢复 advertisement 广播顺序

- Context: `GatewayNodePersistence.register()` 将 protocol advertisement 排序后放进 typed result，handler 因而按错误顺序分配 owner status seq；heartbeat/disconnect 的数据库稳定排序不受此问题影响。
- Decision: register result 原样保留 `agent_ids` 输入顺序；未修改 `_agent_ids()` 的 `ORDER BY agent_id`。
- Rationale: 首次 register broadcast 的 compatibility source 是 frame advertisement；后续生命周期 transition 的 source 才是 DB snapshot。
- Evidence:
  - Tests: 红测实际得到 `agent-a, agent-z`；实现后 status broadcast、node persistence、status unit 共 16 passed。
  - Entry: 真实 FastAPI `/im/ws/gateway` register + owner `/im/ws/user` 收到 online agent frames `agent-z, agent-a`，seq 严格递增；断连 offline 仍通过。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/im_service/integration/test_status_broadcast_e2e.py::test_register_broadcasts_agents_in_advertisement_order_via_real_ws`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `03c82281` 恢复旧排序（会重新引入 behavior drift）。
- Commits: C1=`27c2e480`，C2=`03c82281`，C3=本 documentation commit。
- Next: R2 跨 connection dispatch winner。

## R2 — 收口跨 connection dispatch winner

- Context: `_agent_message_lock` 仅保护单个 handler；两个 connection/process 都可能先创建 message，再由同 key `INSERT OR IGNORE` 竞争。`record_dispatch()` 已返回 durable winner，但 handler 忽略返回值，loser 继续 relay 并 ack 自己的 message。
- Decision: message 创建与 dispatch insert 的既有非原子顺序不变；handler 比较 `record_dispatch()` 返回的 winner message id，只有匹配本地 message 才 enqueue/push relay，否则将 conversation/target/message ack 全部切换到 durable winner。
- Rationale: SQLite first-write-wins 是跨 process 唯一共享 authority；不能用 process-local lock 扩展成假想全局互斥，也不能顺手收紧事务边界。
- Evidence:
  - Tests: 两个独立 SQLite connection/handler 在各自 commit 后由 barrier 确定性交汇；红测出现两个 ack message id，修复后两个 ack 均等于 durable winner，且 71 个 handler/persistence/seam 聚焦测试通过。
  - Entry: handler 的公开 `agent.message` frame 返回 canonical winner ack；两个本地 message 仍落盘，证明既有非原子 side-effect boundary 未被收紧；`relay_tasks` 仅一行且 message id 为 winner。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/im_service/unit/test_gateway_dispatch_concurrency.py::test_competing_handlers_relay_and_ack_only_the_durable_winner`；真进程证据在 R3 补齐。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: revert `34342be8` 恢复 loser relay/ack 漏洞。
- Commits: C1=`99f6acf9`，C2=`34342be8`，C3=本 documentation commit。
- Next: R3 真栈与全门禁。

## R3 — 真栈与完整门禁收口

- Status: VERIFY
- Acceptance checklist:
  1. 以持久 tmux 承载 `PATH=.venv/bin:$PATH ./scripts/e2e-up.sh`，健康检查 `$IM_URL/openapi.json` 与 Gateway WS accepted。
  2. 公开 auth + `/im/ws/user`、`/im/ws/gateway` 注册一个已绑定测试 node，发送非字典序 advertisement；在线 broadcast 必须按输入顺序且 seq 递增。
  3. 两个真实 Gateway WS 连接提交同一 `agent.message` dispatch key；两个 ack 必须复用同一 message id，公开/DB relay 只能引用 winner。
  4. 运行聚焦 regression、完整 non-e2e、`scripts/e2e-critical.sh -m "not slow"`、ruff check/format 与 diff check。
