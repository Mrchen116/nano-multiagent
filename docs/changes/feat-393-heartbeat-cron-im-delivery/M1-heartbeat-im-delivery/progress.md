# feat-393-M1 Progress

## Status: DONE

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
- Next: 完成，M1 DONE

### R3 — 全套回归验证

- Context: R1+R2 完成后验证全量测试树通过，并核对 worker 退出标准逐条达标。
- Decision: 跑 `pytest -m "not e2e"` 全量 + 逐条核对 [worker] 退出标准。
- Rationale: 防止 R1/R2 改动意外影响普通聊天流式路径或 IM 其他路径。
- Evidence:
  - Tests: `pytest -m "not e2e" -q` — 2351 passed, 4 deselected, 15 warnings
  - Entry: N/A（纯回归验证）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression:
    - `test_heartbeat_with_content_creates_real_message_row_in_fk_enforced_db` ✓ — 真实 FK message 路径
    - `test_heartbeat_no_reply_produces_zero_message_rows` ✓ — 静默 tick 零 message
    - `test_heartbeat_empty_content_produces_zero_message_rows` ✓ — 空内容静默
    - `test_normal_chat_run_context_store_eager_bubble_unchanged` ✓ — 普通聊天 eager bubble 不变
    - `test_heartbeat_scheduler_reuses_stable_heartbeat_session_across_ticks` ✓ — fresh-session 旁路已删
    - `test_turn_start_conversation_id_mode_unchanged_normal_chat_path` ✓ — 普通聊天 turn_start 不变
  - Visual/Interaction: N/A
- Worker 退出标准核对:
  - [worker] 集成测试真实 FK path ✓
  - [worker] 静默 tick 零 message ✓
  - [worker] 普通聊天无回归 ✓
  - [worker] pytest -m "not e2e" 全绿（含 IM_service）✓
  - [worker] fresh-session 旁路已删（`_get_or_create_heartbeat_session` 稳定复用）✓
  - [worker] `origin=heartbeat` 门控唯一开关：`to_user_id` 在 run_context_store 中作为判定字段，仅 heartbeat runner 写入 ✓
- Rollback: 回退到 R2 C3（b092b364）即恢复 heartbeat 正常执行但不投递状态。
- Commits: C1/C2/C3 共用一个 docs commit 记录
- Next: M1 完成，合并到 unit/feat-393

---

## post-acceptance fix (round 1) — 2026-06-02

### Context / 根因

round-1 reviewer 验收：142 次 heartbeat run 全部产生真实内容，但 IM 0 条消息到达，WS 413 次 open/close。

经 debug 定位，实际有三个叠加根因：

**根因 1（blocking — IM WS 关连接）**：`_handle_streaming_delta` 的 `turn_start to_user_id` 分支调用 `_find_or_create_direct_conversation`，当 owner `user_id` 在 IM 中不存在时（e2e ephemeral DB、或主 config user_id 过期），`create_conversation` 因 FK 违约抛 `ValueError`。该异常未捕获，冒泡出 `serve()` 关闭 WS 连接，gateway 立刻重连，循环产生 413 次 flap，heartbeat 的 streaming_delta 从未稳定送达。

**根因 2（blocking — observer 时序）**：`GatewayRuntime._run_until_shutdown` 中 `heartbeat_runner.start()` 在 `im_connection_manager.connect_once()` 之前执行。本地 LLM 响应很快，heartbeat run 在 WS 建立（connected=True）之前即完成，observer 检查 `manager.connected=False` 直接返回 None，每次 tick 的投递全部静默跳过。

**根因 3（e2e 测试基础设施）**：`e2e-up.sh` 未同步 `config.node.user_id` 为 ephemeral IM 的真实用户 id（reviewer 已定位为 side-finding）；以及旧 DB 污染（`_find_or_create_direct_conversation` 在新 e2e 找到旧 conversation，其 `owner_id` 是不存在的旧用户 id，API `list_conversations_for_owner` 过滤掉，消息存入 DB 但 API 看不到）。

### Decision

**Fix 1**：`_handle_streaming_delta` 的 `to_user_id` 分支加 `try/except`，捕获 `_find_or_create_direct_conversation` 所有异常，返回 `skipped='owner_unresolved'` ack，不关 WS 连接。gateway observer 收到 skip ack 时 log warning、不建消息、不重试，run 正常收尾（对齐 design 决策6）。同时 `_find_or_create_direct_conversation` 新增可选 `caller_owner_id` 参数并在 heartbeat 路径传 `to_user_id`，确保新建 conversation 的 `owner_id` 正确。

**Fix 2**：`e2e-up.sh` 在 register/login 后解析 nano 用户在 ephemeral IM 的真实 id 并写入 config `node.user_id`；在启动 IM 前删除旧 `data/im_service.sqlite3`，每次 e2e 从全新 DB 开始。

**Fix 3**：`GatewayRuntime._run_until_shutdown` 将 `heartbeat_runner.start()` 移到 `im_connection_manager.connect_once()` + `post_im_connect` 之后，确保 heartbeat 首次 tick 时 WS 已建立（`connected=True`）。回归测试更新 `test_gateway_runtime_keeps_running_until_shutdown_requested` 断言正确的启动顺序（heartbeat.start 在 im.connect/im.bootstrap 之后）。

### Evidence

- `pytest -m "not e2e" -q` — 2352 passed（+1 新回归测试），4 deselected
- 新增回归测试：
  - `test_turn_start_to_user_id_owner_not_in_db_returns_skipped_ack_not_exception`：FK 强制 DB，断言 owner 不存在时返回 skipped ack 不抛异常
  - 更新 `test_gateway_runtime_keeps_running_until_shutdown_requested`：断言 heartbeat.start 在 im.connect 之后
- e2e 冒烟验证：
  - WS 1 次 open，无 close（不再 flap）
  - `GET /im/v1/conversations` 返回 1 条 direct 直聊（title=default-agent）
  - 直聊里有 agent 汇报消息：`当前时间为 2026-06-01 16:13:05 UTC。` 等多条
  - gateway log 无 exception，无 WS reconnect

### Commits

- `6e4dae4a` — test: IM turn_start owner_unresolved 红测试
- `b6d85937` — fix: Fix1 turn_start owner_unresolved skipped ack；Fix2 e2e node.user_id 同步
- `82d3e4d4` — fix: Fix3 heartbeat_runner.start() 移到 im.connect 之后
- `01c9c6d0` — fix: _find_or_create_direct_conversation 传 caller_owner_id；e2e-up.sh 清旧 DB

---

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
