# feat-445-M2 — Progress

fix-implementation（reviewer 反馈循环，复用 M1 worker 上下文）。round-1 三道闸的 8 个
CONFIRMED fork 边缘缺陷 + 防御 + W1/W2 + 群聊400。每条配回归红→绿，真栈复跑边缘路径。

### R1 — kernel: flush_async(#1) + drop source_lock(#2) + role 守卫(防御)

- Decision: ① runtime.fork_session up_to 路径 `flush()`→`await flush_async()`；② 去掉 up_to 路径的 `async with source_lock`；③ jsonl_store.load up_to 命中加 `role=='assistant'` 守卫。
- #2 安全性论证（已核实）：up_to 路径数据全部来自 `manager.load`（磁盘 boundary-aware materialize，锁外已完成），`_fork_locked` 只 enqueue 写**新** session 的 JSONL、从不读源内存历史。源 JSONL append-only：并发 run 只会在当前 tail（即 M）之后追加，而 up_to 在 M 处截断、M 之后条目本就丢弃；行写入原子 + 路径首已 `flush_async`，故 as-of-M 切片一致，无需锁。原来在此持源锁 → 源 agent 活跃 run 持同一把锁数分钟 → fork 阻塞 → gateway 10s 超时 → 502（#2 根因）。非 up_to 路径保留锁（复制内存缓存、需防 compact 并发）。
- Evidence:
  - Tests: `tests/unit/test_fork_session.py` 13 passed——`test_fork_up_to_uses_async_flush_not_blocking`(loop 线程上无阻塞 flush)、`test_fork_up_to_does_not_block_on_busy_source_lock`(源持锁时 fork 3s 内完成)、`test_fork_up_to_non_assistant_message_rejected`(防御)。
  - Entry: 内核进程内真实 JSONL。
  - E2E/Regression: `pytest tests/unit/ tests/contract/` 2623 passed/1 skipped。
- Rollback: revert C2；非 up_to 路径不变。
- Commits: C1=test, C2=fix, C3=docs。
- Next: R2 长对话 fork 全量历史读。

### R2 — 长对话 fork 取全量历史（#3）

- Decision: 加 `MessageRepository.list_all_messages(conversation_id)`（复用 `_list_message_timeline` 全量，无 `[-200:]`、无 cursor）；fork_conversation 的 fork_index 定位 + 复制改用它。根因：`list_messages` 是 UI 分页读（`min(limit,200)` + `[-200:]`），fork 误用它 → fork 点在末 200 外找不到(400)、或分支只复制末段(展示<记忆)。
- Evidence:
  - Tests: `test_fork_conversation.py` 9 passed——`test_fork_point_outside_last_200_is_found`(260 条、fork 早期点 → 分支精确 [0..M])、`test_fork_at_end_of_long_conversation_copies_full_history`(fork 末尾 → 分支 260 条全量、含最早 u0)。
  - E2E/Regression: 真栈 >200 复跑见 R6。
- Rollback: revert C2。
- Commits: C1=test, C2=fix, C3=docs。
- Next: R3 fork_conversation 编排重排 + 递归 fork 映射 + 回滚 + 保留状态。

<!-- 每个 roadpoint 完成后实时追加 -->
