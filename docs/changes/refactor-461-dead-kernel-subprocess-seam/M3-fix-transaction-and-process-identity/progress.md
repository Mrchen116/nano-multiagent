# refactor-461-M3 — Progress

## Baseline

- Context: unit integration head `049867bd` 上执行 post-acceptance fix round 2。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m "not e2e" -q` → `3515 passed, 1 skipped, 23 deselected`；`ruff format --check tests/unit/test_runtime_helpers.py` → 既有 1-file red gate（本 milestone R4 指派项）。

## R1 — 连续 config migration transaction

- Context: deterministic backup 可被 FIFO 卡在 open 前、第三方 hardlink 可共享 backup inode，且 backup durability gate 后到 `write_text` 之间没有 source revision 校验。
- Decision: 每个 resolved config path 使用进程内协调锁；事务起点通过 no-follow fd 读取一次 regular-file snapshot（identity/mode/content），legacy/timestamp backup 都从该 snapshot 派生；existing backup 先 lstat fail-fast 再 nonblocking open，existing/new 文件都要求 `st_nlink == 1`。新内容在同目录临时文件完成 mode/write/fsync 后，对 source 做 identity/content CAS，再用 `os.replace` 原子提交并 fsync 目录。
- Rationale: lock 消除同进程 save 互相踩踏，snapshot/CAS 检测不参与锁的外部 writer；所有备份和最终提交都引用同一 revision，失败路径不会覆盖 source。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_config_migration_transaction.py tests/unit/personal_assistant/test_local_store.py` → 63 passed。
  - Entry: 全部断言通过公共 `load_local_config` / `save_local_config` 驱动；FIFO 在子进程 2s hard timeout 内返回拒绝，barrier 在 backup directory fsync 后注入 external writer 并观察 CAS 拒绝覆盖。
  - Frontend State Matrix: N/A，非前端。
  - Browser QA: N/A，非前端。
  - E2E/Regression: existing/new hardlink、atomic replace failure、source mode 与既有 backup failure/race/alias 套件一并通过；ruff check 通过。
  - Visual/Interaction: N/A，非前端。
  - Prototype Comparison: N/A，design 无前端 prototype/reference。
- Debug note: 首次 green 后两个既有 alias 用例只因错误词变化失败；按 systematic-debugging 从堆栈确认拒绝行为正确，恢复 symlink/source-inode 的 `alias` 诊断优先级，同时保留第三方 hardlink 的 `single-link` 诊断。
- Rollback: 回退 C2 恢复非原子写入；回退 C1 删除 transaction regression gate。
- Commits: `03a27c54` (C1), `316d4386` (C2)

## R2 — 统一 Gateway PID/exit 确认状态机

- Status: TODO

## R3 — e2e Gateway ownership identity 与 fail-atomic teardown

- Status: TODO

## R4 — 格式与全链路收口

- Status: TODO
