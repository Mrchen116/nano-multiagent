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

- Context: default start waiter 只看 PID path 存在，malformed residue、mismatched PID 或 PID 出现后 child 退出都可写入成功 state；stop 两条分支在发出 SIGKILL 后立即删除证据并回报成功。
- Decision: spawn 前删除不可解析 residue；default waiter 要求 PID 可解析、等于 `process.pid`，并在读取前后确认 child 存活。state/PID-only stop 共用 `_stop_owned_gateway`：TERM 后 bounded confirm，必要时按 PID→process-group 顺序 KILL，再次 bounded confirm；SIGKILL ESRCH 直接视作 confirmed exit，仍存活则抛出明确失败并保留文件。
- Rationale: path existence 和 signal delivery 都不是生命周期事实；成功状态必须由同一 launched identity 加可观测存活/退出共同建立。
- Evidence:
  - Tests: `pytest -q tests/unit/personal_assistant/test_gateway_launch.py tests/unit/personal_assistant/test_gateway_forced_stop.py tests/unit/personal_assistant/test_gateway_pid_lifecycle.py` → 25 passed。
  - Entry: 公共 `launch_gateway_in_background` 覆盖 malformed/mismatch/invalid/dead-after-PID；公共 `stop_gateway` 参数化覆盖 state 与 PID-only 的 KILL ESRCH/post-KILL alive。
  - Frontend State Matrix: N/A，非前端。
  - Browser QA: N/A，非前端。
  - E2E/Regression: signal order 与 lifecycle evidence retain/cleanup 均有断言；ruff check/format 窄门禁通过。
  - Visual/Interaction: N/A，非前端。
  - Prototype Comparison: N/A，design 无前端 prototype/reference。
- Debug note: green 阶段旧 force 用例只提供一次 grace 时钟；新 helper 在 KILL 后再次取 deadline 触发 StopIteration。按 systematic-debugging 确认是夹具时钟而非 signal failure 后，将 helper 改为先即时确认 liveness，已退出时无需创建无意义 deadline。
- Rollback: 回退 C2 恢复重复 stop 分支及宽松 start waiter；回退 C1 删除严格 identity/exit 门禁。
- Commits: `550c0705` (C1), `869eb016` (C2)

## R3 — e2e Gateway ownership identity 与 fail-atomic teardown

- Status: TODO

## R4 — 格式与全链路收口

- Status: TODO
