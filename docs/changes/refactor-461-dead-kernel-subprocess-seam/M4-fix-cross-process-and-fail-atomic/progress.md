# refactor-461-M4 — Progress

## Baseline

- Context: unit integration head `4f36f071` 上执行 post-acceptance fix round 3。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m "not e2e" -q` → `3533 passed, 1 skipped, 23 deselected, 16 warnings in 117.11s`，exit 0。
- Boundary: 协作 writer 通过稳定 sidecar inode 串行整个事务；对不持锁外部 writer 只承诺 pre-commit identity/content/mode drift 检测，不声称消除 CAS-return → replace 的 POSIX 窗口。

## R1 — 跨进程 config transaction 与失败回滚

- Context: M3 只有进程内 mutex；deterministic backup 在 directory fsync 后关闭 fd；source CAS 未比较 mode；replace 后 directory fsync 失败会把失败的新 revision 留在 source。
- Decision: `config.yaml.lock` 是不删除的稳定 sidecar inode，进程内 mutex 与 `flock` 联合覆盖 snapshot → backups → commit → directory durability。legacy backup 无论 existing/new 都返回持有的 fd/identity，并在 source CAS 前再次比较 path inode、held inode、regular/single-link；source CAS 同时比较 identity/content/mode。commit 前预制同目录 rollback inode；replace 后 durability 失败时，只有 source 仍精确等于本次 staged identity/content/mode 才恢复旧 revision 并再次 fsync parent。
- Failure outcome: rollback 成功时恢复原 source 后重抛原 directory durability error；rollback replace/fsync/ownership 任一步失败时抛 `ConfigCommitRollbackError`，同时保留 commit error 与 rollback error，调用者不会把“可能已提交”误判成普通 CAS 拒绝。
- Boundary: sidecar 是 advisory cooperation contract；不持锁外部 writer 只在最后一次 pre-replace CAS 前可检测。实现明确不声称消除 CAS-return → `os.replace` 的系统调用窗口，也不防御能任意改写 parent directory 的主体。
- Evidence:
  - Red: transaction file → 6 failed / 5 passed，分别命中 ignored sidecar、existing/new backup inode swap、mode drift、unrestored directory fsync failure、undistinguished rollback failure。
  - Green: `pytest -q tests/unit/personal_assistant/test_config_migration_transaction.py tests/unit/personal_assistant/test_local_store.py` → 69 passed。
  - Gates: affected `ruff check`、`ruff format --check`、`git diff --check` passed。
- Rollback: 回退 C2 恢复 M3 单进程事务；C1/C3 分别是 round-3 行为门禁与边界记录。
- Commits: `e6df65623` (C1), `2043bba2c` (C2)。

## R2 — 公共 Gateway process-instance identity

- Context: M3 只持久化整数 PID，state/PID-only stop 在验证 OS process instance 前就会 `kill(pid, 0)`/TERM/group；grace waiter 固定 sleep poll interval，poll 大于 grace 时两阶段均越界。
- Decision: foreground runtime 先 atomic write + file fsync + replace + parent fsync `gateway.identity.json`，再写 `gateway.pid` readiness marker。schema 固定为 `schema_version/pid/process_start/config_path/entry_module/argv`；cleanup 只在文件仍等于本实例时删除。Stop 将 state/PID 与 identity 静态字段对账，再以无信号 `ps` 读取 start + command；TERM、TERM group、KILL、KILL group 每次之前都重新核对同一 birth/entry/exact argv suffix。malformed identity/mismatch 与 PID-only 缺 identity fail closed；identity 文件尚不存在但 legacy state + PID + resolved config 完整时，只有 live command 精确匹配唯一 `-m personal_assistant.main --config <resolved> [--im-service-url <url>] --foreground [--auto-bind]` 才采纳当前 OS start 并 durable upgrade identity。
- Timing: `_wait_for_pid_exit` 每轮 sleep `min(poll_interval, deadline-now)`；fake clock `grace=1,poll=10` 证明 TERM 与 KILL 阶段各只等待 1 秒。
- Compatibility: 保留 M1 的旧 state forward-read 硬契约：额外 `health_url` 仍忽略，PID/config/log state 可经上述无信号 live-process upgrade 后 stop；伪装 sleeper、argv/config mismatch、state/PID 不一致均零信号保留。PID-only 缺 config 无法安全推断，继续 fail closed。完整 identity 对应的已退出进程作为 STALE 安全清理。
- Evidence:
  - Red: 新 identity suite 7 failed，分别命中 foreground 无 identity、state/PID-only identity absent/reused、PID-only startup acceptance、两阶段 10 秒 oversleep。
  - Green: identity + launch + forced-stop + PID lifecycle + real legacy foreground integration → 34 passed；真实子进程删除新 identity、注入旧 `health_url` 后由 public `stop_gateway` 安全升级并退出，PID/state/identity 全清。
  - Gates: affected `ruff check`、`ruff format --check`、`git diff --check` passed。
- Rollback: 回退 C2 恢复整数 PID ownership；C1/C3 保留为 round-3 safety contract 与证据。
- Debug note: 首版 R2 将 legacy state 与 PID-only 一并拒绝，违背 motivation/design/M1 的 forward-read stop 契约。systematic-debugging 反向追到 state source 后补 public/真实进程红测，只对 legacy state 增加 exact argv adoption；真实测试又证明 `kill(pid, 0)` 会把未 wait 的 zombie 当 live，故公共 liveness 改为无信号 `ps stat`，与 e2e 已有 zombie 语义对齐。
- Commits: `65211e97f`, `6c64208e7` (C1); `13693799b`, `b8ea91fbf` (C2)。

## R3 — e2e evidence state machine 与 spawn rollback

- Status: pending。

## R4 — 全链路验收收口

- Status: pending。
