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

- Context: `.gateway.pid` 只保存可复用数字，down 未核对 Gateway 自写 PID、config argv 或进程启动实例；KILL 后仍存活也会继续停 IM、删 config/env 并打印 stopped。
- Decision: up 等待 `gateway.pid == $!`，记录 `.gateway-identity.json`（external/internal PID、resolved config path、`ps lstart`）。down 在任何 kill 前核对 JSON、内部 PID、process start，并以 shlex 精确确认 `-m personal_assistant.main`、唯一 `--config <WT_CFG>`、`--foreground`、`--auto-bind`；`ps stat` 区分 exited/zombie 与仍存活，signal failure + live stat 视作 unmanageable。只有确认退出才删 lifecycle identity 并继续 IM teardown，否则立即非零退出保留整栈。
- Rationale: PID、argv 与 OS start identity 共同把 signal ownership 绑定到本次 up；read-only identity check 先于 signal，teardown 以 confirmed exit 为原子门槛。
- Evidence:
  - Tests: `pytest -q tests/integration/test_e2e_down_script.py` → 7 passed；额外覆盖 zombie、signal permission failure 与 worktree symlink alias。
  - Entry: shell 集成覆盖内部 PID mismatch、argv mismatch、TERM→KILL 后持续存活、正常确认退出；mismatch 无 TERM/KILL，失败路径保留 Gateway/IM/config/env/identity 且无 stopped 文案。
  - Frontend State Matrix: N/A，非前端。
  - Browser QA: N/A，非前端。
  - E2E/Regression: tmux 持久真实栈 up 成功；篡改内部 PID 后 down rc=1 且 Gateway/IM 都保持存活，恢复后 down rc=0 且 lifecycle/config/env residue 全清。`bash -n` 与测试文件 ruff 通过。
  - Visual/Interaction: N/A，非前端。
  - Prototype Comparison: N/A，design 无前端 prototype/reference。
- Debug note: 首次 green 发现 status 在 identity 前调用 `kill -0`，且正常退出夹具用 `${VAR:-S}` 覆盖显式空状态；按 systematic-debugging 将 existence/zombie 检查改为纯 `ps stat`，identity 严格先于 kill，并修正夹具空状态语义。
- Debug note: 真实栈以 `/tmp` 起时，JSON 的 `Path.resolve()` 记录 `/private/tmp`，而 argv 保留 `/tmp`，正常 down 被误判 mismatch。新增 symlink-worktree 红测后，up/down 统一 `pwd -P`，argv config 以 resolved path identity 比较；保留现场验证恢复成功。
- Rollback: 先以 down 确认无 live stack，再回退 C2；C1 是新安全语义门禁。
- Commits: `f7bf8cfd`, `8ea12662` (C1); `d5260895`, `c0209393` (C2); `ed80a412` (coverage)

## R4 — 格式与全链路收口

- Context: 基线 `ruff format --check tests/unit/test_runtime_helpers.py` 明确报告该文件需要格式化；M3 同时需要两个统一机制的全链路 signoff。
- Decision: 只对指派测试文件执行 formatter；先跑 103 项 selective affected，再跑全仓 ruff/format 与唯一 full non-e2e。真实生命周期使用隔离临时 config；真实 e2e 使用 tmux 持久承载，避免宿主回收普通后台进程。
- Rationale: formatter 变更保持纯机械；full suite 只在共享 runner 空闲时单实例运行，真实服务则以可追踪持久进程完成 identity 负路径与正常清理闭环。
- Evidence:
  - Tests: affected → 103 passed；full non-e2e → `3532 passed, 1 skipped, 23 deselected, 16 warnings in 180.83s`，明确 exit 0。
  - Entry: 隔离 config 的默认 start/stop/restart 全部完成且无 `gateway.pid` / `.gateway-state.json` residue；R1 public save barrier 证明真实文件 drift 保留 external revision 与 original backup。
  - Frontend State Matrix: N/A，非前端。
  - Browser QA: N/A，非前端。
  - E2E/Regression: `ruff check .` → passed；`ruff format --check .` → 783 files formatted；真实 e2e up/mismatch/down 证据见 R3。
  - Visual/Interaction: N/A，非前端。
  - Prototype Comparison: N/A，design 无前端 prototype/reference。
- Runner note: 首轮 M3 full 与另外两个 worktree full 重叠；按 PID cwd ownership 只停止自有 49436，未触碰他人。疑似失败区间窄跑 55 passed；等待共享 runner 空闲后，以新日志单实例重跑得到最终 exit 0。
- Rollback: formatter commit 可独立回退；功能回退按 R1-R3 各自三提交边界执行。
- Commits: `951941f9` (C1), `bb0aa714` (C2)

## Milestone validation

- Affected suites: 103 passed（config transaction/local store、Gateway launch/forced stop/PID lifecycle、e2e-down、runtime helper）。
- Lint/format: `ruff check .` passed；`ruff format --check .` → 783 files already formatted；shell `bash -n` passed。
- Full non-e2e: 3532 passed, 1 skipped, 23 deselected, 16 warnings，exit 0。
- Real entries: 隔离 default start/stop/restart 无 residue；tmux e2e up 后 identity mismatch fail-atomic、恢复 identity 正常 down 并全清通过。
