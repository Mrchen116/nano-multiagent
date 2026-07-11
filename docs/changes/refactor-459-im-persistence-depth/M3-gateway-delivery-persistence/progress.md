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

- Context: 待实施。
- Decision: 待实施。
- Rationale: 待实施。
- Evidence:
  - Tests: 待实施。
  - Entry: 待实施。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 待实施。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 待实施。
- Commits: 待实施。
- Next: R1 完成后开始。
