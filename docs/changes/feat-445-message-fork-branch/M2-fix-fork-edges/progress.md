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

<!-- 每个 roadpoint 完成后实时追加 -->
