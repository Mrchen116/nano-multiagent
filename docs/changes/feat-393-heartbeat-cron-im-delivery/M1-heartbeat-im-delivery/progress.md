# feat-393-M1 Progress

## Status: DOING

##澄清记录

（开工前无疑问，设计意图清晰）

---

## Roadpoints

### R1 — IM turn_start to_user_id 分支

- Context: IM `_handle_streaming_delta` 的 `turn_start` 只支持 `conversation_id` 模式（必须非空），heartbeat 发 `to_user_id` 时直接抛 ValueError。
- Decision: 在 `turn_start` 块前增加 `to_user_id` 互斥分支；复用现有 `self._find_or_create_direct_conversation` 解析 canonical 直聊；ack 同时返回 `conversation_id` 和 `message_id`。
- Rationale: 复用服务端既有 canonical 解析逻辑，gateway 不预解析、不加额外 round-trip；与普通聊天 `conversation_id` 模式互斥，零风险交叉。
- Evidence:
  - Tests: `pytest tests/im_service/ -q` — 268 passed
  - Entry: N/A（纯后端协议扩展，由 R2 的 gateway 侧测试证明端到端可用）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（R3 跑全量）
  - Visual/Interaction: N/A
- Rollback: C1=b4211ed5, C2=66a3815b
- Commits: C1=b4211ed5, C2=66a3815b, C3=（本条记录）
- Next: R3 — 全套回归验证 + 文档更新

### R2 — heartbeat observer 惰性 turn_start + 稳定 :heartbeat session

- Context: `_build_kernel_event_observer` 对所有 run_context_store 条目都走 eager turn_start；HeartbeatScheduler._submit_run 每 tick 创建 fresh session；PollingHeartbeatRunner 不等终态不驱动 observer。
- Decision:
  1. `run_context_store` 新增可选 `to_user_id` 字段标识 heartbeat 变体；
  2. observer `run_status=running` 时：有 `to_user_id` → 跳过 eager turn_start（静默门控）；无则走原路径；
  3. observer `assistant_message` 时：heartbeat 且未有 bubble → 检查 NO_REPLY/空 → 有真实内容才发 `turn_start{to_user_id}` + 存回 conv_id/msg_id + 发 delta；
  4. `HeartbeatScheduler._heartbeat_sessions` dict 缓存稳定 session，`_get_or_create_heartbeat_session` 仅首次建；
  5. `PollingHeartbeatRunner` 新增 kernel/run_context_store/owner_user_id/kernel_event_observer 参数；tick 后对每个 HeartbeatRunRecord 调 `_consume_heartbeat_run`（seed store → stream until terminal → pop store）；
  6. `build_runtime`：heartbeat_runner 早建（因为 `_build_im_connection_manager` 需要它）；observer 构建后通过属性注入。
- Rationale: 惰性建泡 = NO_REPLY/空时零 IM 痕迹；稳定 session = standing-task 上下文连续性（设计决策 4）；共享 observer = 真实 message 行（FK 满足，设计决策 1/3）。
- Evidence:
  - Tests: `pytest -m "not e2e" -q` — 2351 passed, 4 deselected
  - Entry: FK 强制 DB 集成测试证明有内容建真实 message 行、NO_REPLY/空零 message
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（R3 跑全量）
  - Visual/Interaction: N/A
- Rollback: C1=6dd4a35f, C2=d5a90726
- Commits: C1=6dd4a35f, C2=d5a90726, C3=（本条记录）
- Next: R3 — 全套回归验证
