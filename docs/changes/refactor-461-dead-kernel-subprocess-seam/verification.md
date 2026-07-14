# Verification Report: refactor-461

## Summary

Mode: full  
Delta range: N/A  
Focus issues: N/A  
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | Tasks 5/5；Requirements 4/4 implemented |
| Correctness | Scenarios 10/10 implemented；3 个场景分支仍缺 durable regression |
| Coherence | D1-D5 均遵守；current 长青契约尚未归并本 unit delta |

实现完整命中 `motivation.md` 的 4 条 Requirement / 10 个 Scenario，未发现缺实现或架构边界违反。存在 4 个 WARNING：1 个 current 长青契约 drift，3 个场景分支的永久回归覆盖缺口。

## Completeness

- Tasks: 5/5 complete；`M1-remove-dead-kernel-seam/tasks.md` 的 5 条退出标准与 R1-R5 均标记完成。
- Requirement 覆盖: 4/4。
  - 用户消息与主动任务：`build_runtime()` 只构建进程内 Kernel，并把同一 `_KernelClientShim` 交给消息、heartbeat 与 cron wiring（`src/personal_assistant/main.py:2729-2792,3420-3430`）。
  - Gateway 后台服务管理：启动确认、PID-only state、stop/restart 与进程组回收位于 `src/personal_assistant/main.py:167-175,2333-2469,3434-3525,3975-3998,4091-4127`。
  - Gateway lifecycle timing 配置所有权与迁移：`GatewayLifecycleConfig`、逐字段 fallback、canonical save 与迁移备份位于 `src/personal_assistant/config/local_store.py:270-318,321-366,501-543,630-639,693-702,968-1018`。
  - 一键真栈只管理 IM + Gateway：`scripts/e2e-up.sh:47-76,127-158,210-255`、`scripts/e2e-down.sh:29-81`，并由 active-scope guard 守卫（`tests/contract/test_no_dead_kernel_subprocess_seam.py:17-88`）。
- Prototype / Reference 覆盖: N/A；本 unit 不改前端，无 prototype/reference contract。
- 长青契约覆盖: unit delta 已存在于 `docs/changes/refactor-461-dead-kernel-subprocess-seam/specs/gateway/service-lifecycle.md`，但尚未归并到 current `docs/specs/gateway/service-lifecycle.md`，见 W1。

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 用户消息与主动任务 / Web IM 或外部通道消息正常回复 | `src/personal_assistant/main.py:2729-2792,3420-3430` | `tests/e2e/critical_paths/test_tool_call_reply_critical_path.py:24`；`progress.md:52-64` live 真栈 | covered |
| 用户消息与主动任务 / Heartbeat 与 Cron 活路径不受清理影响 | `src/personal_assistant/main.py:2472-2587,2777-2792,2827-2845` | `tests/e2e/critical_paths/test_cron_push_critical_path.py:40`；`progress.md:52-64` live cron | covered |
| 后台服务管理 / 默认启动确认 | `src/personal_assistant/main.py:167-175,2333-2397,4091-4111` | `test_gateway_main_command.py:14-93`、`test_gateway_launch.py:46-84`；默认 waiter 仅 live 证据 | covered；W2 |
| 后台服务管理 / stop 与 restart 保持现有结果 | `src/personal_assistant/main.py:2400-2469,3500-3508` | `test_gateway_main_command.py:229-380`、`test_gateway_pid_lifecycle.py:69-350`；强杀分支仅 live 证据 | covered；W3 |
| 后台服务管理 / IM 离线时本地自治不变 | `src/personal_assistant/main.py:1879-1898,2729-2792` | `test_gateway_runtime_lifecycle.py:103-138`；`progress.md:79-82` 真实 Feishu 离线收发 | covered |
| lifecycle timing / 旧自定义 timing 继续生效 | `src/personal_assistant/config/local_store.py:968-1018`；消费者 `src/personal_assistant/main.py:2380-2384,2436-2464,4100-4108` | `test_local_store.py:286-315`、`test_gateway_launch.py:46-84`、`test_gateway_pid_lifecycle.py:100-153` | covered |
| lifecycle timing / 新配置逐字段优先 | `src/personal_assistant/config/local_store.py:990-1018` | `test_local_store.py:318-350` | covered |
| lifecycle timing / 保存后 canonical Gateway schema + migration backup | `src/personal_assistant/config/local_store.py:501-543,630-639,693-702` | `test_local_store.py:1057-1162`；backup 创建 I/O 失败仅由实现兜底，无针对 legacy migration 的 durable test | covered；W4 |
| lifecycle timing / 旧连接与 HTTP 字段不再形成运行时输入 | `src/personal_assistant/config/local_store.py:321-366,968-1018`；`src/personal_assistant/main.py:3420-3430` | `test_local_store.py:251-283`、`test_no_dead_kernel_subprocess_seam.py:17-38,80-88` | covered |
| 一键真栈 / e2e 起停无 Kernel API 产物 | `scripts/e2e-up.sh:47-76,127-158,210-255`；`scripts/e2e-down.sh:29-81` | `test_no_dead_kernel_subprocess_seam.py:41-77`、`test_runtime_helpers.py:82-108,188-232`；`progress.md:52-64` live 起停 | covered |

验证命令：

- related pytest：107 passed。
- `ruff check`、`ruff format --check`、`bash -n scripts/e2e-up.sh scripts/e2e-down.sh`：通过。
- full non-e2e：3496 passed, 1 skipped, 23 deselected。
- 本 verifier 未重跑依赖真实 IM/LLM/飞书的 e2e；已逐条审计 `progress.md` 的 R3/R5 live evidence 与 cleanup 记录。

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| D1 直接删除 `GatewayProcessManager`，不建替代 port | 是 | `GatewayRuntime` 构造面已无 manager（`src/personal_assistant/main.py:1760-1813`）；active-scope guard 禁止旧符号回流（`tests/contract/test_no_dead_kernel_subprocess_seam.py:17-38`） |
| D2 三项 timing 迁到 Gateway 所有权 | 是 | `src/personal_assistant/config/local_store.py:270-318,968-1018` |
| D3 删除 health/readiness 字段，只保留 PID/start confirmation | 是 | `src/personal_assistant/main.py:167-175,254-281,2333-2469,3975-3998,4091-4111` |
| D4 只删 manager 调用，保持真实启动/关闭顺序 | 是 | channel → heartbeat → kernel → cron → IM/resource 的 shutdown 顺序仍在 `src/personal_assistant/main.py:1901-1949`；in-process Kernel wiring 在 `src/personal_assistant/main.py:2729-2792,3420-3430` |
| D5 只清 active 叙事，不改历史 | 是 | allowlist guard `tests/contract/test_no_dead_kernel_subprocess_seam.py:41-77`；实际 diff 未改 `docs/changes/archive/**` |

### Architecture Coherence

- 依赖方向：`src/personal_assistant` 未新增对 `agent.core` / `agent.platform` / `agent.products` 的 import，仍只经 `agent.sdk` 构建进程内 Kernel。
- 跨进程边界：parent 只以 PID file + child liveness 作启动确认；未新增 readiness IPC，也未把 IM HTTP 可达性用于 Gateway stop。
- 复用 vs 平行：保留 Gateway `BackgroundProcessFactory`、PID lock、process-group cleanup 与 `_KernelClientShim`；未新增 Kernel lifecycle adapter/noop manager。
- current 长青契约仍与实现不一致，见 W1；这是文档归并缺口，不是实现架构偏离。

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

#### W1 — current Gateway 长青契约尚未归并 refactor-461 delta

`docs/specs/gateway/service-lifecycle.md:3,18-26` 仍对齐 `feat-447`，并承诺默认启动打印“健康提示”；文件也完全缺少新的 Gateway lifecycle timing ownership / legacy migration Requirement。实际实现已经只输出 PID/log/独立 IM status，且 unit delta 已完整描述新契约（`docs/changes/refactor-461-dead-kernel-subprocess-seam/specs/gateway/service-lifecycle.md:5-74`）。这违反 `docs/SPEC_GUIDE.md` 的 current 单一权威与收尾归并规则，也让实现与 current contract 直接 drift。

修复：按 delta 的 MODIFIED/ADDED 段更新 `docs/specs/gateway/service-lifecycle.md`，把头部 `> 对齐:` bump 为 `refactor-461`；MODIFIED 完整替换“运维者用启停命令…”条目，ADDED 追加“Gateway 生命周期 timing…”条目。归并后重新核对 area Requirement 计数；本次不新增 area，入口索引无需改结构。

#### W2 — 默认启动确认的真实 waiter 只有一次性 live 证据，没有永久回归测试

生产 waiter 在 `src/personal_assistant/main.py:4091-4111` 负责“child 未退出 + PID file 出现”的新契约，但 `tests/unit/personal_assistant/test_gateway_launch.py:46-84` 注入并绕过 `wait_for_start`，只验证参数传递；现有永久测试未证明默认 waiter 在 child 提前退出、PID 缺失超时、PID 出现成功三种条件下的行为。`progress.md` 的真实 CLI 成功记录属于一次性验收证据，按 `docs/TESTING_GUIDE.md` 不能替代 durable regression。

修复：通过公开 `launch_gateway_in_background()`、仅替换 `spawn_process` 与可控时钟/PID 文件，补三条行为测试：child 先退出时报错并清理、PID 始终缺失时报 timeout 并清理、PID 出现且 child 存活时返回成功；不要直接测试私有 waiter。

#### W3 — stop 超时升级 SIGKILL 仅有 R5 live 证据，没有永久回归测试

`stop_gateway()` 的强杀分支位于 `src/personal_assistant/main.py:2436-2469`。`tests/unit/personal_assistant/test_gateway_pid_lifecycle.py:100-153,271-350` 只覆盖正常退出；R5 用 `SIGSTOP` 得到 `forced=true` 的证据记录在 `progress.md:89-93`，但它不是每次 CI 运行的永久回归。该分支是 motivation 明示的用户可观察 stop/restart 契约。

修复：在 `test_gateway_pid_lifecycle.py` 通过公开 `stop_gateway()` 补一条可控时钟测试，让 PID 在 grace deadline 内持续存活，断言先 SIGTERM、超时后 SIGKILL、调用 process-group cleanup、返回 `forced=true`，并删除 state/PID 文件。

#### W4 — legacy migration backup 的“创建/落盘失败不覆盖原 config”缺少针对性回归

`_backup_legacy_kernel_config()` 在 `src/personal_assistant/config/local_store.py:501-543` 实现了异常清理并阻断后续 save；现有 migration tests 覆盖成功、同内容复用和冲突校验失败（`tests/unit/personal_assistant/test_local_store.py:1057-1162`），但 `test_save_local_config_backup_failure_raises_and_leaves_dest_unchanged`（同文件 `1249-1279`）测的是默认 timestamp backup，输入没有 legacy `kernel:`，不会进入本 unit 新增的 migration backup 写盘路径。

修复：增加一个含 legacy `kernel:` 的 config，用 monkeypatch 让 deterministic migration backup 的 `os.open`、write 或 `os.fsync` 失败，断言异常上抛、半成品 backup 清理、原 config 原字节不变。

### SUGGESTION（可以修）

无。

No critical issues. 4 warning(s) to consider. Ready for PR (with noted improvements).

# Round 2

## Verification Report: refactor-461

### Summary

Mode: full
Delta range: N/A
Focus issues: Round 1 W2-W4；M2 post-acceptance lifecycle/config/runtime/e2e fixes
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | Tasks 11/11；Requirements 4/4 implemented |
| Correctness | Scenarios 10/10 implemented and durably covered |
| Coherence | D1-D5 followed；M2 fixes preserve the same boundaries |

本轮从 `motivation.md`、`design.md`、M1/M2 tasks/progress、Round 1 verification/acceptance 和 `6882c85a..99fe8495` 实现 diff 重新做 full verification。未发现缺实现、spec/design 偏离或架构边界违反；Round 1 W2-W4 与 M2 返工问题均已闭环。当前仅有 1 个 WARNING：新增 M170 helper 测试未通过仓库 CI 的 `ruff format --check .`。

## Prior Issue Closure

| 既有问题 | Round 2 结论 | 证据 |
|---|---|---|
| Round 1 W1 / acceptance canonical spec 未归并 | deferred as designed；不作为本轮 blocker | `design.md:303-323` 明确 canonical spec 由 orchestrator 在最终验收后归并；README/runbook 的旧输出已修正（`README.md:79-91,116-119`；`docs/operator-runbook.md:86-99,115-118`） |
| W2 默认 start waiter 缺 durable regression | closed | 公共 `launch_gateway_in_background()` 的 early-exit、PID timeout、PID success 三态测试：`tests/unit/personal_assistant/test_gateway_launch.py:184-234` |
| W3 stop 超时强杀缺 durable regression | closed | 公共 `stop_gateway()` 覆盖 SIGTERM→SIGKILL、进程组、`forced=true` 与 PID/state 清理：`tests/unit/personal_assistant/test_gateway_pid_lifecycle.py:354-398` |
| W4 migration backup I/O failure缺 durable regression | closed | open/write/file-fsync/directory-fsync 失败均保持原 config，且覆盖 race loser、symlink/hardlink、mode 与 non-finite：`tests/unit/personal_assistant/test_local_store.py:1193-1366` |
| Round 1 acceptance：用户文档仍承诺 health/readiness | implementation part closed | README/runbook 已改为 PID confirmation + Log + separate IM status，并明确不代表 runtime/channel ready；canonical 归并按上述时序 deferred |
| M2 M170 auth/auto-bind 与 e2e residue | closed | `scripts/acceptance/m170_runtime.py:155-183,365-478,481-530`；`scripts/e2e-down.sh:29-78`；回归见 `tests/unit/test_runtime_helpers.py:282-364`、`tests/integration/test_e2e_down_script.py:46-95` |

## Completeness

- Tasks: 11/11 complete；M1 5/5，M2 6/6，无 unchecked exit criterion。
- Requirement 覆盖: 4/4。
  - 用户消息与主动任务仍走进程内 Kernel：`src/personal_assistant/main.py:2729-2792,3420-3430`。
  - Gateway 后台服务生命周期仍由 PID/process-group 管理：`src/personal_assistant/main.py:2333-2469,4091-4111`。
  - lifecycle timing 与 legacy migration 归 Gateway 所有：`src/personal_assistant/config/local_store.py:272-318,512-625,1048-1089,1153-1159`。
  - e2e 只管理 IM + Gateway，并只按外部 `.gateway.pid` 建立 signal ownership：`scripts/e2e-up.sh:47-76,127-158,210-255`；`scripts/e2e-down.sh:29-99`。
- Prototype / Reference: N/A；本 unit 不改前端且无 prototype/reference contract。

## Correctness

| Requirement / Scenario | 实现证据 | durable test / acceptance evidence | 状态 |
|---|---|---|---|
| 消息 / Web IM 或外部通道回复 | `src/personal_assistant/main.py:2729-2792,3420-3430` | `tests/e2e/critical_paths/test_tool_call_reply_critical_path.py:24`；M1 progress R3/R5 | covered |
| 主动任务 / Heartbeat 与 Cron | `src/personal_assistant/main.py:2472-2587,2777-2792,2827-2845` | `tests/e2e/critical_paths/test_cron_push_critical_path.py:40`；M1 progress R3 | covered |
| 后台服务 / 默认启动确认 | `src/personal_assistant/main.py:167-175,2333-2397,4091-4111` | `test_gateway_launch.py:184-234`；operator live evidence | covered |
| 后台服务 / stop 与 restart | `src/personal_assistant/main.py:2400-2469,3500-3508` | `test_gateway_pid_lifecycle.py:354-398`；M1 progress R2/R5 | covered |
| 后台服务 / IM 离线本地自治 | `src/personal_assistant/main.py:1879-1898,2729-2792` | `test_gateway_runtime_lifecycle.py:103-138`；M1 progress R5 Feishu live | covered |
| timing / 旧自定义值继续生效 | `src/personal_assistant/config/local_store.py:1048-1089`；消费者 `main.py:2380-2384,2436-2464,4100-4108` | `test_local_store.py:286-315`；M1 progress R3 migration live | covered |
| timing / 新值逐字段优先 | `src/personal_assistant/config/local_store.py:1048-1089` | `test_local_store.py:318-350`；M1 progress R3 | covered |
| timing / canonical save + durable migration backup | `src/personal_assistant/config/local_store.py:512-625,778-782` | `test_local_store.py:1057-1366` | covered |
| timing / 旧连接与 HTTP 字段不生效 | parser edge 无旧 runtime schema；`src/personal_assistant/config/local_store.py:321-366,1048-1089` | `test_local_store.py:251-283`；active-scope contract | covered |
| e2e / 无 Kernel API 产物且干净起停 | `scripts/e2e-up.sh`；`scripts/e2e-down.sh:29-99` | `test_e2e_down_script.py:9-95`；`test_no_dead_kernel_subprocess_seam.py:17-98`；M2 progress R4 | covered |

### Test Evidence

- affected suites: `90 passed, 2 warnings in 2.36s`。
- full non-e2e final run: `3515 passed, 1 skipped, 23 deselected, 16 warnings in 168.80s`。
- full non-e2e first run: `1 failed, 3514 passed`；唯一失败 `test_heartbeat_resets_idle_timer_for_silent_long_tool` 在 150ms idle window 下先于首个 80ms heartbeat timeout，随后独立连续 10/10 通过；同一完整套件单独复跑全绿，判定为共享负载时序抖动，不是本 unit 回归。
- `ruff check .`: passed。
- `bash -n scripts/e2e-up.sh scripts/e2e-down.sh`: passed。
- `git diff --check 6882c85a..HEAD`: passed。
- `ruff format --check .`: failed，仅 `tests/unit/test_runtime_helpers.py` 需 reformat；见 W5。

## Coherence

| design 决策 | 遵守? | 证据 |
|---|---|---|
| D1 删除 dead manager，不建替代 seam | 是 | production 已无 `GatewayProcessManager`/`process_manager`；active guard `tests/contract/test_no_dead_kernel_subprocess_seam.py:17-88` |
| D2 三项 timing 归 Gateway，legacy 只在 parser edge 迁移 | 是 | `src/personal_assistant/config/local_store.py:272-318,1048-1089` |
| D3 PID/start confirmation，删除 health/readiness IPC | 是 | `src/personal_assistant/main.py:2333-2469,4091-4111`；README/runbook 已同步真实边界 |
| D4 保持 shutdown 顺序 | 是 | dispatch/heartbeat → channels → Kernel → cron → IM/resource 顺序仍在 `src/personal_assistant/main.py:1901-1949` |
| D5 只清 active scope | 是 | active allowlist guard；未改 archive/历史 change 文档 |

### Architecture Coherence

- 依赖方向：`personal_assistant` / `coding_cli` 未引入 `agent.core` 或 `agent.platform` import，仍只经 `agent.sdk` 构建 Kernel。
- 跨进程边界：parent 只观察 PID file + child liveness；M2 没有新增 readiness IPC，stop 不探测 IM/Kernel HTTP。
- 生命周期所有权：migration cleanup 以 inode identity 为界；e2e signal ownership 只来自外部 `.gateway.pid`，内部 state 中的 PID 不会被信号。
- 复用关系：保留既有 Gateway background launcher、PID lock、process-group cleanup 与 `_KernelClientShim`，未造平行 lifecycle abstraction。

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

#### W5 — 新增 M170 helper 测试未通过仓库 CI format gate

仓库 CI 明确执行 `ruff format --check .`（`.github/workflows/ci.yml:30-31`）；当前命令报告 `tests/unit/test_runtime_helpers.py` 需要重排，具体是 `:354-356` 的单行 `_HTTPResponse(...)` 返回被手工拆成三行。功能测试与 lint 均通过，但按当前 head 提 PR 会在 format job 失败。

修复：对 `tests/unit/test_runtime_helpers.py` 执行 `ruff format`（预期只改该返回语句），再重跑 `ruff format --check .`；无需改 production behavior。

### SUGGESTION（可以修）

无。

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvements).

# Round 3

## Verification Report: refactor-461

### Summary

Mode: full
Delta range: N/A
Focus issues: M3 seven confirmed transaction/process findings；Round 2 W5 format gate；`/tmp` path canonicalization follow-up
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | Tasks 17/17 marked complete；Requirements 4/4 implemented |
| Correctness | Scenarios 10/10 covered；M3 hardening has 4 warning-level edge gaps |
| Coherence | D1-D5 followed；M3 transaction/e2e fail-atomic claims only partially hold |

本轮基于 integration head `8cb3a12c`，重新完整核对 motivation 的 4 条 Requirement / 10 个 Scenario、design D1-D5、M1-M3 tasks/progress、历轮 verification 与 `049867bd..8cb3a12c` 实现。主产品行为与架构边界未回归；受影响套件、lint、format 和完整 non-e2e 均通过。M3 已关闭 FIFO、backup hardlink、start PID match、stop ESRCH/post-KILL confirmation 与 Round 2 W5，但 source CAS/commit 和 e2e fail-atomic/canonical path 仍有 4 个可复现 WARNING。

## Prior Issue Closure

| Round 3 focus | 结论 | 证据 |
|---|---|---|
| Legacy backup FIFO fail-fast | closed | existing backup 先 `lstat` 拒绝非 regular，再 nonblocking/no-follow open：`src/personal_assistant/config/local_store.py:579-640`；硬超时公共入口回归 `tests/unit/personal_assistant/test_config_migration_transaction.py:52-76` |
| Existing/new third-party hardlink | closed | open 前后与 durable gate 均要求 `st_nlink == 1`：`local_store.py:600-616,709-729`；回归 `test_config_migration_transaction.py:79-120` |
| Source drift CAS + atomic commit | partially closed | backup-gate 后、CAS 前 drift 可拒绝，但 CAS 与 replace 并非同一原子操作，见 W6；replace 后 durability error 也不满足失败原子性，见 W7 |
| Start PID match + child liveness | closed | waiter 校验 PID parse、`process.pid` equality 与二次 poll：`src/personal_assistant/main.py:4129-4157`；回归 `tests/unit/personal_assistant/test_gateway_launch.py:237-307` |
| Stop SIGKILL ESRCH + post-KILL confirmation | closed | state/PID-only 共用 `_stop_owned_gateway`，ESRCH 清证据，成功 KILL 后 bounded confirm，存活则保留：`main.py:2404-2499`；回归 `test_gateway_forced_stop.py:35-109` |
| e2e PID/argv/start identity | closed for complete evidence | up 记录 external/internal PID、resolved config、process start；down 在 signal 前核对：`scripts/e2e-up.sh:225-275`、`scripts/e2e-down.sh:45-120` |
| Unconfirmed exit fail-atomic teardown | partially closed | identity mismatch、signal failure、KILL 后存活已保留整栈；但 external PID 文件缺失会绕过整个 Gateway gate 并继续 teardown，见 W8 |
| `/tmp` / symlink canonicalization | partially closed | 显式 `--wt` 使用 `pwd -P`，但默认 `$PWD` 不 canonicalize，见 W9 |
| Round 2 W5 formatter gate | closed | `ruff format --check .` → 783 files already formatted；`tests/unit/test_runtime_helpers.py` 已机械格式化 |
| Canonical spec 归并 | deferred as designed | 仍按 orchestrator §7.0 在最终验收后归并，不作为当前 blocker |

## Completeness

- Tasks: 17/17 marked complete（M1 5/5，M2 6/6，M3 6/6）；M3 的 source transaction 与 e2e fail-atomic 两条退出标准存在 W6-W9 所述边缘偏差。
- Requirement 覆盖: 4/4。
  - 消息与主动任务仍由进程内 Kernel 执行：`src/personal_assistant/main.py:2760-2823,3451-3461`。
  - Gateway 后台服务仍以 PID/liveness/process-group 管理：`main.py:2333-2499,4121-4158`。
  - timing ownership、legacy migration 与 canonical save：`src/personal_assistant/config/local_store.py:272-318,468-509,579-760,918-927,1193-1234`。
  - e2e 只管理 IM + Gateway：`scripts/e2e-up.sh`、`scripts/e2e-down.sh`；无独立 Kernel API 产物。
- Prototype / Reference: N/A；本 unit 无前端或 reference contract。

## Correctness

| Requirement / Scenario | 实现与回归证据 | 状态 |
|---|---|---|
| 消息 / Web IM 或外部通道回复 | in-process wiring `main.py:2760-2823,3451-3461`；关键路径与 M1 live evidence | covered |
| 主动任务 / Heartbeat 与 Cron | `_KernelClientShim` 与 heartbeat/cron wiring 保留；critical-path cron 与 M1 live evidence | covered |
| 后台服务 / 默认启动确认 | `main.py:2333-2401,4121-4158`；public launch early-exit/timeout/PID match tests | covered |
| 后台服务 / stop 与 restart | `main.py:2404-2499`；state/PID-only graceful/forced/ESRCH/survivor tests | covered |
| 后台服务 / IM 离线本地自治 | Gateway runtime/channel wiring未改；M1 Feishu offline live evidence | covered |
| timing / 旧自定义值继续生效 | parser fallback 与消费者未回归；local-store regression + M1 migration live | covered |
| timing / 新配置逐字段优先 | `_parse_gateway_lifecycle` 与既有 regression | covered |
| timing / canonical save + migration backup | snapshot、durable backup、atomic replace 已实现；普通/backup-gate drift覆盖，但 W6-W7 表明并发/后提交失败语义仍不完整 | covered with warnings |
| timing / 旧连接与 HTTP 字段不生效 | runtime schema/生产 wiring 未恢复旧字段；active-scope contract passed | covered |
| e2e / 只管理 IM + Gateway 且干净停止 | 正常 identity 完整路径与 mismatch/survivor tests 通过；W8-W9 是异常证据与默认别名入口缺口 | covered with warnings |

### Test Evidence

- affected suites: `103 passed, 2 warnings in 9.31s`。
- full non-e2e: `3533 passed, 1 skipped, 23 deselected, 16 warnings in 183.04s`，exit 0；运行前共享 runner 无其他 pytest。
- `ruff check .`: passed。
- `ruff format --check .`: 783 files already formatted。
- `bash -n scripts/e2e-up.sh scripts/e2e-down.sh`: passed。
- `git diff --check 049867bd..HEAD`: passed。
- verifier diagnostics（临时目录、未改仓库）：CAS 后注入 external writer 会被 replace 静默覆盖；replace 后 parent-dir fsync 失败会抛错但 config 已 canonicalized；缺 `.gateway.pid` 时 down rc=0 并删除 IM/config/env；默认 symlink cwd 复现 identity mismatch。

## Coherence

| design / M3 决策 | 遵守? | 证据 |
|---|---|---|
| D1 删除 dead manager，不建替代 seam | 是 | zero-residue contract 与 production symbols 未回流 |
| D2 timing 归 Gateway、legacy 只在 parser edge | 是 | `local_store.py:272-318,1193-1234` |
| D3 PID/start confirmation 与 PID-only stop | 是 | `main.py:2333-2499,4121-4158` |
| D4 保持真实 runtime shutdown 顺序 | 是 | runtime shutdown wiring未被 M3 diff 修改 |
| D5 只清 active scope | 是 | M3 diff 仅 source/scripts/tests/unit docs，无 archive 改动 |
| M3 config 连续事务 | 部分 | snapshot/backup/stage/CAS/replace 顺序存在，但 W6 的 CAS→replace TOCTOU 与 W7 的 post-replace failure 语义偏离“外部 drift 不覆盖 / 失败保留原 config” |
| M3 e2e ownership + fail-atomic teardown | 部分 | 完整 identity 时遵守；缺 external claim 与默认 logical cwd 时分别触发 W8/W9 |

### Architecture Coherence

- 依赖方向保持：产品包仍只经 `agent.sdk`，没有新增 `agent.core` / `agent.platform` import。
- M3 没有引入 Kernel subprocess/readiness seam；Gateway launcher、PID lock、process-group 与 `_KernelClientShim` 均保留。
- config lock 目前仅为进程内协调；它不能关闭跨进程/不协作 writer 在 CAS 与 replace 之间的窗口，这是 W6 的机制边界。
- e2e identity 将 signal ownership 绑定到 PID + internal PID + argv + start time；但 teardown 必须在任何 lifecycle 证据不完整时 fail closed，W8 表明入口条件尚未统一。

### Prototype / Reference Contract

N/A。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

#### W6 — source CAS 与 `os.replace` 之间仍可静默覆盖外部 revision

`_atomic_commit_config()` 在 `src/personal_assistant/config/local_store.py:757-758` 先独立执行 `_assert_snapshot_current()`，随后才 `os.replace()`；二者不是 atomic compare-and-swap。外部 writer 若恰在这两步之间更新 `dest`，replace 会静默覆盖它。当前 drift regression（`tests/unit/personal_assistant/test_config_migration_transaction.py:123-162`）只在 backup directory fsync 后、CAS 前注入 writer，因此没有覆盖这个窗口。verifier 在 public `save_local_config()` 路径让 `os.replace` wrapper 先写 external revision 再调用真实 replace，save 成功且 external revision 被覆盖，migration backup 仍只含旧 snapshot。

修复：先明确跨进程 writer 协议。若只保证本产品 writer，使用同目录 sidecar lock + OS advisory lock，让所有 `save_local_config` 进程共享锁，并保留 CAS；若契约要覆盖任意不协作 writer，则需要平台支持的 conditional/exchange commit 或修订 design，不能把普通 check-then-rename 描述成 CAS。增加一个把 writer 精确放在 compare/replace 边界的跨进程 regression。

#### W7 — replace 后目录 fsync 失败会“抛异常但配置已改变”

`_atomic_commit_config()` 在 `local_store.py:758-760` 先 replace，再 fsync parent directory。若第二步失败，函数抛出 `OSError`，但 `dest` 已是 canonical 新内容；这与 M3 tasks 的“所有失败路径保留原配置”及 transaction failure-atomic 叙事不一致。verifier 让 legacy backup 的 directory fsync 成功、commit 后 directory fsync 失败，观察到 exception 上抛、backup 正确，但 source 已移除 `kernel:`。现有 replace-failure regression（`test_config_migration_transaction.py:165-183`）只覆盖 replace 自身失败。

修复：定义并实现清晰 commit point。可在 design/tasks 中明确 replace 成功后属于“已提交但 durability 未确认”的专用结果，不再承诺 exception 即原文件不变；若仍要求失败回滚，则保留旧 inode/temp 并以带 revision check 的 rollback 恢复。无论选哪种，都补 post-replace directory-fsync failure 的 public regression，断言调用者可判定最终文件状态。

#### W8 — 缺 external `.gateway.pid` 时 e2e-down 绕过 Gateway exit gate并拆除整栈

`scripts/e2e-down.sh:113-176` 仅在 `.gateway.pid` 存在时验证 identity/确认退出；文件缺失时直接落到 `:178-205` 停 IM、删除 config/env 并打印成功。若 `gateway.pid` / `.gateway-identity.json` 仍表明本轮 Gateway 可能存在，这是“unconfirmed exit”而不是“已退出”。verifier 构造 internal PID + identity + IM/config/env、删除 external PID claim 后执行真实 down：rc=0、打印 `e2e stack stopped`，IM/config/env 被删，只留下内部 PID/identity 残片。

修复：在任何 teardown 前对 `.gateway.pid`、`gateway.pid`、`.gateway-identity.json`、state 做一致性 preflight。只要存在 Gateway lifecycle residue 却无法建立 confirmed-exit，就非零退出并保留整栈；补“external PID file missing but internal/identity remain”的 integration regression。

#### W9 — `/tmp`/symlink canonicalization 只覆盖 `--wt`，默认 `$PWD` 入口仍 mismatch

`scripts/e2e-up.sh:30-35` 与 `scripts/e2e-down.sh:19-23` 都仅在显式 `--wt` 分支使用 `pwd -P`；默认入口仍保留 logical `$PWD`。up 写 identity 时又对 config 做 `Path.resolve()`（`e2e-up.sh:247-254`），down 随后在 Python argv 校验前先做 textual equality（`e2e-down.sh:67-72`）。因此从 `/tmp` 或目录 symlink 中直接运行无参数 up/down 时，identity 记录 `/private/tmp/...`，`WT_ROOT` 仍是 `/tmp/...`，正常 down 被误判 identity mismatch。现有 symlink regression（`tests/integration/test_e2e_down_script.py:218-240`）总是传 `--wt`，未覆盖默认入口。

修复：参数解析后无条件将 `WT_ROOT` canonicalize（例如 `WT_ROOT="$(cd "$WT_ROOT" && pwd -P)"`），up/down 共用同一规则；新增从 symlink cwd、不传 `--wt` 的回归，覆盖 macOS `/tmp → /private/tmp` 形态。

### SUGGESTION（可以修）

无。

No critical issues. 4 warning(s) to consider. Ready for PR (with noted improvements).

# Round 4

## Verification Report: refactor-461

### Summary

Mode: full
Delta range: N/A
Focus issues: M4 cross-process transaction；public process-instance identity；legacy state upgrade；bounded stop；e2e fail-closed/cold-start rollback
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | Tasks 25/25 marked complete；Requirements 4/4 implemented；M4 两条 e2e 退出标准有 3 个 warning 级边缘缺口 |
| Correctness | Scenarios 10/10 covered；Round 3 config/public lifecycle findings closed；e2e evidence/rollback 仍部分偏离 |
| Coherence | D1-D5、M4 R1/R2 followed；M4 R3 fail-closed cleanup only partially holds |

本轮基于 integration head `34a9de384`，完整读取 M4 tasks/progress、历轮 verification、motivation 的 4 条 Requirement / 10 个 Scenario、design D1-D5 与 `4f36f071..34a9de384` 实现。M4 已关闭 Round 3 的 sidecar/backup/mode/rollback、public identity、legacy `health_url` forward-read、bounded stop、missing evidence、default symlink 与 reviewer 冷启动 blocker；affected、lint、format、shell syntax 和完整 non-e2e 均通过。新增 3 个可复现 WARNING，均位于 e2e fail-closed 状态机的异常收尾分支。

## Prior Issue Closure

| Round 4 focus | 结论 | 证据 |
|---|---|---|
| Stable sidecar `flock` boundary | closed within documented cooperative-writer boundary | `save_local_config()` 在 resolved `<config>.lock` 的进程内 mutex + stable single-link inode `flock` 内完成 snapshot→backup→commit→durability：`src/personal_assistant/config/local_store.py:493-536,1089-1102`；跨解释器 public save 回归 `tests/unit/personal_assistant/test_config_migration_transaction.py:188-244` |
| Backup held identity | closed | existing/new backup 都返回持有 fd，commit gate 重核 held/path inode、regular 与 `st_nlink==1`：`local_store.py:651-718,735-821,824-846,903-905`；existing/new path-swap 回归 `test_config_migration_transaction.py:247-291` |
| Source mode CAS | closed | transaction snapshot 包含 mode，commit gate 比较 identity/content/mode：`local_store.py:451-457,539-581`；chmod drift 回归 `test_config_migration_transaction.py:294-321` |
| Post-replace fsync rollback / typed outcome | closed | commit durability error 时只对本次 committed revision 回滚并再次 fsync；rollback 失败抛 `ConfigCommitRollbackError` 且保留两层错误：`local_store.py:469-490,866-934`；回归 `test_config_migration_transaction.py:324-380` |
| Public Gateway process identity | closed | foreground 先 durable publish `schema_version/pid/process_start/config/entry/argv` 再写 PID；state/PID-only stop 在 signal 前核对静态字段、OS birth 与 exact argv：`src/personal_assistant/main.py:2347-2365,2437-2547,4085-4333`；`test_gateway_process_identity.py:82-201` |
| Legacy state with extra `health_url` | closed | `_read_gateway_state()` 只 forward-read `pid/config_path/log_path`，缺 identity 的 matching live legacy Gateway 经无信号 observation durable upgrade 后再走公共 stop：`main.py:2485-2495,4253-4305,4336-4364`；真实子进程回归 `tests/integration/test_gateway_legacy_state_upgrade.py:25-124` |
| TERM/KILL bounded stop | closed | `_wait_for_pid_exit()` 每轮 sleep `min(poll_interval, remaining)`，两个阶段各自受 grace deadline 限制：`main.py:2510-2562`；fake-clock `grace=1,poll=10` 回归 `test_gateway_process_identity.py:203-255` |
| e2e missing/nonregular evidence | mostly closed | regular missing + 任一 internal evidence、directory external evidence均在 signal 前 fail closed：`scripts/e2e-down.sh:173-203`；回归 `test_e2e_down_script.py:250-292`。dangling external symlink仍被当作 evidence 全无，见 W11 |
| e2e stale preflight | closed for specified stale-internal case | 无 live external owner 时只删除 internal residue，不 signal 其中 PID：`scripts/e2e-up.sh:54-80`；sentinel 回归 `test_e2e_up_script.py:295-314` |
| Default symlink cwd | closed | up/down 参数解析后无条件 `pwd -P`：`scripts/e2e-up.sh:30-44`、`scripts/e2e-down.sh:18-29`；默认无 `--wt` 回归 `test_e2e_up_script.py:317-336` |
| Startup budget / reviewer cold-start blocker | closed | identity wait ticks 来自 `gateway.startup_timeout_seconds`（legacy/default fallback），延迟 70 ticks 仍成功；identity/readiness failure 的正常可终止进程会自动回滚并保留日志：`scripts/e2e-up.sh:332-403`；`test_e2e_up_script.py:232-292`；M4 progress 记录真实 cold/timeout rollback |
| Owned rollback | partially closed | exact spawned PID 正常响应 TERM/KILL 时 Gateway/IM 均退出并条件清理；Gateway 在 KILL 后仍存活时却继续停 IM，见 W10 |
| Conditional evidence cleanup | partially closed | PID 不同会阻止 teardown，但同 PID 的 process-start/argv/state 漂移仍被删除，见 W12 |
| Canonical spec 归并 | deferred as designed | 仍由 orchestrator 按 §7.0 在最终验收后校正 delta 并归并；不是本轮 blocker |

## Completeness

- Tasks: 25/25 marked complete（M1 5/5，M2 6/6，M3 6/6，M4 8/8）。M4 line 20 的“只有 Gateway evidence 全无才停 IM”和 line 21 的“回滚确认退出”在 W10-W12 的异常分支只部分成立。
- Requirement 覆盖: 4/4；M4 未恢复 dead Kernel subprocess/HTTP seam，也未改变消息、heartbeat/cron、IM 离线自治或 Gateway timing ownership。
- Scenario 覆盖: 10/10；原产品旅程的实现/回归仍在，M4 增量主要强化配置事务与运维生命周期异常路径。
- Prototype / Reference: N/A；本 unit 无前端或 reference contract。

## Correctness

| Requirement / Scenario group | M4 实现与回归证据 | 状态 |
|---|---|---|
| 消息、Heartbeat/Cron、IM 离线自治 | M4 delta 未改 runtime message/channel/kernel wiring；原 critical-path/live evidence保留，完整 non-e2e 通过 | covered |
| 默认 start / stop / restart | public identity durable publish、PID/identity waiter、legacy state upgrade、两阶段 bounded stop均有 public/真实子进程回归 | covered |
| timing 迁移 / canonical save | cooperative writers sidecar 串行；backup held identity；mode CAS；post-replace fsync rollback与 typed failure均有 public regression | covered |
| 旧连接/HTTP 字段不形成输入 | M4 仅 forward-read legacy state extra field，不恢复 runtime `kernel:` dead fields或 health probe | covered |
| e2e 只管理 IM + Gateway且失败收口 | cold/default path、missing evidence、正常 rollback与 confirmed down均覆盖；W10-W12 表明 survivor、dangling evidence和同-PID cleanup drift尚未完全 fail closed | covered with warnings |

### Test Evidence

- affected suites: `134 passed, 2 warnings in 15.85s`。
- full non-e2e（共享 runner 空闲后唯一单实例）: `3558 passed, 1 skipped, 23 deselected, 16 warnings in 139.13s`，exit 0。
- `ruff check .`: passed。
- `ruff format --check .`: `786 files already formatted`。
- `bash -n scripts/e2e-up.sh scripts/e2e-down.sh`: passed。
- `git diff --check 4f36f071..HEAD`: passed。
- verifier diagnostics（隔离临时目录、未改仓库）：(1) identity timeout + Gateway TERM/KILL no-op 后 rc=1，但 Gateway 仍 live、IM 已退出；(2) 只有 dangling external `.gateway.pid` 时 down rc=0，删除 IM/config 并打印 stopped；(3) TERM 后把 identity 的 `process_start` 改为不同值但保留同 PID，down rc=0 并删除新 identity/全部栈证据。

## Coherence

| design / M4 决策 | 遵守? | 证据 |
|---|---|---|
| D1-D5 原始 seam/timing/lifecycle/active-scope 决策 | 是 | M4 只改 config save、public Gateway lifecycle、e2e scripts与对应测试；无 Kernel subprocess/HTTP接口回流 |
| M4 R1 cooperative config transaction | 是 | stable sidecar lock + snapshot/mode CAS + held backup identity + best-effort durable rollback；诚实声明不协作 writer 的 POSIX CAS→replace窗口 |
| M4 R2 public process-instance identity | 是 | 单一 public identity file/schema；state/PID-only/legacy路径在 signal 前验证；stop deadline bounded |
| M4 R3 e2e fail-closed state machine | 部分 | 正常、missing internal、directory nonregular、stale、symlink cwd与cold timeout路径符合；W10-W12 的 survivor/dangling/same-PID drift分支仍会拆半栈或删新证据 |

### Architecture Coherence

- 依赖方向保持；M4 production delta 只在 `personal_assistant` 与 shell scripts 内，没有产品包新增 `agent.core` / `agent.platform` import。
- config 协作边界在 tasks/progress 中已诚实写明；不再把普通 check-then-replace描述为可防任意外部 writer 的原子 CAS。
- public runtime 与 e2e 使用同一 `gateway.identity.json` schema，但 cleanup 实现仍各自维护；W12 是这处 primitive 未真正共享带来的可观察 drift。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

#### W10 — e2e-up 无法确认 Gateway 退出时仍继续停止 IM

`stop_spawned_pid()` 在 TERM/KILL 后仍观测到 live 会返回 1（`scripts/e2e-up.sh:116-133`），但 EXIT trap 的 Gateway 分支只是跳过 lifecycle 清理，随后无条件进入 IM stop（`:161-175`）。verifier 在现有 fake runtime 上让 identity timeout，并让本轮 Gateway 对 TERM/KILL 保持存活：脚本 rc=1，但结果是 `gateway_alive=True`、`im_alive=False`、external Gateway PID仍在、IM PID已删除。这违反 M4 “确认退出”的 rollback 约束，也把失败现场从完整栈变成半栈；现有 timeout/readiness tests（`tests/integration/test_e2e_up_script.py:248-292`）只覆盖两个进程都会响应 signal 的路径。

修复：rollback 必须先确认 Gateway exit；若 `stop_spawned_pid "$GW_PID"` 失败，明确报告 rollback failure，保留 Gateway/IM PID与其余栈证据，并禁止继续 stop IM。补一个 Gateway survivor regression，断言 IM 未收到 signal、所有 evidence保留且无 success/complete rollback叙事。

#### W11 — dangling external PID symlink 被误判为“Gateway evidence 全无”

e2e-down 的 evidence preflight 用 `[[ -e ... ]]` 判断 external/internal residue（`scripts/e2e-down.sh:173-190`）；Bash 对 dangling symlink 的 `-e` 为 false，因此只存在 dangling `.gateway.pid` 时，nonregular guard与“有 evidence 无 owner”guard都被绕过。verifier 构造 dangling external PID + IM/config：down rc=0、打印 `e2e stack stopped`，删除 IM PID/config，却保留 dangling PID symlink。现有 nonregular regression只用 directory（`tests/integration/test_e2e_down_script.py:276-292`），没有覆盖 symlink。

修复：所有 lifecycle residue 检测使用“entry存在或为 symlink”（例如 `[[ -e "$path" || -L "$path" ]]`），external symlink无论 target 是否存在都按 nonregular evidence fail closed；up 的同类 preflight也使用一致判据。新增 dangling external symlink、dangling internal evidence 两个 shell integration 分支。

#### W12 — e2e-down cleanup 只按 PID 条件删除，无法识别同 PID identity drift

signal 前 `validate_gateway_identity()` 会核对 process start + exact argv，但 confirmed exit 后 `clear_matching_gateway_lifecycle()` 对两个 JSON 只比较 `payload.pid`（`scripts/e2e-down.sh:130-167`），随后调用点宣称“every file still names the externally validated process instance”（`:254-260`）。verifier 在 TERM 后、cleanup 前把 `gateway.identity.json.process_start` 改成不同 birth、PID保持不变：down rc=0，并删除了改变后的 identity、PID/state、IM/config。这样 PID reuse或并发新 lifecycle写入会被旧 teardown误删；现有 mismatch tests只覆盖 signal 前 PID/argv变化（`tests/integration/test_e2e_down_script.py:126-150`）。

修复：在第一次验证时保存完整 expected identity/state snapshot，cleanup先只读核对所有文件仍与该 snapshot一致，再统一删除；任一字段或 inode漂移都零删除、停止 IM teardown并保留证据。优先让 shell入口复用 public runtime 的 conditional-clear primitive，至少不能只比较整数 PID；补 same-PID/different-start 与 cleanup中途漂移回归。

### SUGGESTION（可以修）

无。

No critical issues. 3 warning(s) to consider. Ready for PR (with noted improvements).

# Round 5

## Verification Report: refactor-461

### Summary

Mode: full
Delta range: `d8df1b124..20f301a61`
Focus issues: M5 startup publication transaction；process birth snapshot / quoted path / locale-TZ；legacy state adoption；e2e survivor barrier / fail-atomic cleanup / sidecar zero residue
requires_full_verification: true

| 维度 | 结果 |
|---|---|
| Completeness | Tasks 33/33 marked complete；Requirements 4/4 implemented；M5 8/8 exit criteria implemented |
| Correctness | Round 4 W10-W12 与 code-review startup/publication findings均已闭环；新增真实 quoted-path regression 存在 1 个测试清理 warning |
| Coherence | D1-D5、M5 R1-R3 followed；canonical spec 按 §7.0 延后归并，不是 blocker |

本轮基于 integration head `20f301a61`，完整读取 M5 tasks/progress、历轮 verification、motivation、design 与 `d8df1b124..20f301a61` 实现。实现已关闭 state/publication rollback、cleanup failure 双因保留、foreground publish finally、PID + birth snapshot、space/quote path、locale/TZ、legacy state adoption，以及 Round 4 的 survivor/dangling/drift/sidecar 三类 warning。affected、ruff、format、shell syntax 与 diff whitespace 均通过；完整 non-e2e 的产品断言通过，但新增 quoted-path 测试在 Darwin zombie teardown 竞态中失败，因此本轮保留 1 个 WARNING，不能声称完整门禁已绿。

## Prior Issue Closure

| Round 5 focus | 结论 | 证据 |
|---|---|---|
| Background state publication rollback | closed | waiter + state publish 位于同一事务；失败后 TERM/KILL 并确认退出，只有确认退出才条件删除本 launch evidence：`src/personal_assistant/main.py:2472-2499,4613-4621,4754-4770`；异常注入回归 `test_gateway_startup_publication.py:17-89` |
| Cleanup failure causality/evidence | closed | 二次 wait 仍超时抛 typed cleanup error，外层以 `ExceptionGroup` 同时保留 startup + cleanup cause，并保留 PID/identity：`main.py:2476-2492,4754-4770`；回归 `test_gateway_startup_publication.py:52-89` |
| Foreground publication finally | closed | signal handler 安装后的 identity/PID publish 与 runtime 共处同一 `try/finally`；identity/PID 任一 durable publish 失败都恢复 handler并条件清本实例：`main.py:2393-2414`；回归 `test_gateway_startup_publication.py:92-184` |
| Structured PID + birth snapshot | closed | 固定 `LC_ALL=C LANG=C TZ=UTC`，birth-before/status/command/birth-after 形成稳定 snapshot；新 identity 的 signal authority 只认 PID + birth：`main.py:4129-4195,4546-4560` |
| Space/quote path + legacy adoption | closed | legacy 仅以 anchored project foreground command 首次升级，随后 durable structured identity；真实带空格/单引号 config 与跨 TZ stop 回归：`main.py:4501-4543`；`test_gateway_legacy_state_upgrade.py:59-189` |
| W10 e2e-up survivor barrier | closed | Gateway stop 未确认即退出 rollback，禁止触碰 IM并保留全栈 evidence：`scripts/e2e-up.sh:189-214`；真实 signal shim 回归 `test_e2e_up_script.py:296-316` |
| W11 dangling evidence | closed | up/down residue 判据统一为 `-e || -L`，external/internal dangling/nonregular/malformed 在 signal 前 fail closed：`scripts/e2e-down.sh:214-250`；回归 `test_e2e_down_script.py:325-393` |
| W12 two-phase cleanup / same-PID drift | closed | shell 复用 Python full-file snapshot，记录 type/dev/inode/size/mtime/digest/content；signal 前复核，退出后 validate-all 再统一 delete：`main.py:4198-4368`、`scripts/e2e-down.sh:137-181,247-280`；same-birth/inode drift 回归 `test_e2e_down_script.py:396-456` |
| Config sidecar zero residue | closed | 两服务确认退出后才 non-blocking exclusive flock，并复核 held/path inode后删除；survivor/busy lock保留 config + sidecar：`scripts/e2e-down.sh:184-209`；`test_e2e_down_script.py:493-535` |
| Canonical spec 归并 | deferred as designed | orchestrator 按 §7.0 在最终验收后校正 delta 并归并；不是本轮 blocker |

## Completeness

- Tasks: 33/33 marked complete（M1 5/5，M2 6/6，M3 6/6，M4 8/8，M5 8/8）。
- Requirement 覆盖: 4/4；M5 未恢复 dead Kernel subprocess/HTTP seam，也未改变消息、heartbeat/cron、IM 离线自治或 Gateway timing ownership。
- Scenario 覆盖: 10/10；M5 增量全部位于 startup/public lifecycle 与 e2e 异常收口。
- Prototype / Reference: N/A；本 unit 无前端或 reference contract。

## Correctness

| Requirement / Scenario group | M5 实现与回归证据 | 状态 |
|---|---|---|
| 消息、Heartbeat/Cron、IM 离线自治 | M5 delta 未改 runtime message/channel/kernel wiring；完整 non-e2e 除 W13 测试 teardown 外无产品失败 | covered |
| 默认 start / stop / restart | durable identity→PID publish、publication rollback、cleanup failure causality、quoted path与 legacy upgrade均有直接回归 | covered with test warning |
| timing 迁移 / canonical save | M5 未回退 M4 transaction/sidecar边界；static与受影响测试通过 | covered |
| 旧连接/HTTP 字段不形成输入 | legacy `health_url` 只 forward-read；只对 exact project foreground command 做一次结构化 adoption | covered |
| e2e 只管理 IM + Gateway且失败收口 | Gateway survivor 零 IM signal；dangling/malformed/drift 零 signal或零删除；confirmed exit后 config/sidecar清零 | covered |

### Test Evidence

- affected suites: `70 passed, 2 warnings in 84.66s`。
- `ruff check .`: passed。
- `ruff format --check .`: `787 files already formatted`。
- `bash -n scripts/e2e-up.sh scripts/e2e-down.sh`: passed。
- `git diff --check d8df1b124..HEAD`: passed。
- full non-e2e（共享 runner 空闲后唯一单实例）: `1 failed, 3576 passed, 1 skipped, 23 deselected, 16 warnings in 199.92s`；唯一失败见 W13。
- 隔离诊断：目标 test 单跑 `1 passed`；整个 `tests/integration` 为 `131 passed`；`contract + im_service + target` 为 `590 passed, 1 skipped`。完整前缀 `-x --pdb` 稳定复现后，失败 PID 显示为本 pytest 子进程 `Z <defunct>`，`subprocess._active == [(pid, None)]`；对保留的 `Popen` 调用 `poll()` 返回 0 并立即完成回收。

## Coherence

| design / M5 决策 | 遵守? | 证据 |
|---|---|---|
| D1-D5 原始 seam/timing/lifecycle/active-scope 决策 | 是 | M5 只改 public Gateway lifecycle、e2e scripts与对应测试；无 Kernel subprocess/HTTP接口回流 |
| M5 R1 startup publication transaction | 是 | foreground publish/runtime finally完整；background waiter/state publish rollback及 cleanup double-cause完整 |
| M5 R2 structured process identity | 是 | public snapshot固定环境并防 birth read竞态；new identity PID+birth授权；legacy exact command只用于首次 adoption |
| M5 R3 e2e fail-closed state machine | 是 | survivor barrier、dangling判据、full evidence snapshot、validate-all/delete与sidecar lock均闭环 |

### Architecture Coherence

- 依赖方向保持；production delta 只在 `personal_assistant` 与 shell scripts 内，没有产品包新增 `agent.core` / `agent.platform` import。
- e2e-down 已复用 public runtime 的 snapshot/conditional-clear primitive，消除了 Round 4 shell-only PID cleanup drift。
- M5 把 cooperative lock 与 process lifecycle evidence 分开处理：config sidecar 以 flock 证明无 writer，Gateway evidence 以 process exit + immutable revision证明可删。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

#### W13 — quoted-path integration teardown 在 Darwin zombie race 下使完整 non-e2e 门禁失败

`test_background_start_and_stop_support_quoted_config_path()` 的产品断言已成功：`stop_gateway()` 返回 STOPPED，PID/identity/state也全部删除；但 `finally` 无条件 `os.killpg(result.pid, SIGKILL)`，且只捕获 `ProcessLookupError`（`tests/integration/test_gateway_legacy_state_upgrade.py:68-80`）。在完整 runner 的时序下，`read_gateway_process_snapshot()` 正好观察到 child 已变成 zombie 并把它判为 exited（`src/personal_assistant/main.py:4169-4181`），而默认 background `Popen` 仍留在 pytest 的 `subprocess._active`、尚未 wait/reap。Darwin 对这个 zombie process-group 的 `killpg` 返回 `EPERM`，于是 cleanup 自己把已通过的产品场景变成失败。PDB 现场为 PID `54740`、`Z <defunct>`、PPID 为 pytest，`subprocess._active` 中该对象 `returncode=None`；调用其 `poll()` 后返回 0。目标单跑/整个 integration 都通过，完整 suite 与完整前缀则稳定在该行失败，证明是 retained `Popen` 的时序型 test teardown，不是 quoted path、identity或 stop 产品行为失败。

修复：该真实进程测试应通过 `spawn_process` wrapper 保留本次 child 的 `Popen` ownership；正常 stop 后对同一 handle 调用 `wait()` 回收，只有 `poll() is None` 时才对该 owned process group 做兜底 SIGKILL。不要在只剩裸 PID、且 identity evidence 已清除后无条件 signal，也不要用宽泛吞掉 `PermissionError` 掩盖 ownership 不明。修后重跑 single full `pytest -m "not e2e" -q`。

### SUGGESTION（可以修）

无。

No critical issues. 1 warning(s) to consider. Ready for PR (with noted improvement).

# Round 6

## Verification Report: refactor-461

### Summary

Mode: full
Delta range: `a084ce907..7accd44da`
Focus issues: M6 backup content/mode gate；post-publication gate；public/e2e generation locks；expected cleanup；IM preflight；owned descendant PID/PPID/PGID/birth 与 STOP/TERM/CONT/KILL；Round 5 W13
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | Tasks 63/63 marked complete；Requirements 4/4 implemented；M6 8/8 exit criteria有 2 个 warning 级收尾缺口 |
| Correctness | Scenarios 10/10 covered；backup/publication/generation/IM/descendant主路径闭环；冻结失败恢复与完整门禁稳定性有 2 个 warning |
| Coherence | D1-D5 与 M6 R1-R4 主决策 followed；无 dead Kernel seam、平行生命周期或依赖反转回流 |

本轮基于 unit integration head `7accd44da`，完整读取 motivation、design、delta-spec、M1-M6 tasks/progress、历轮 verification，以及项目架构、测试、注释与长青 Gateway 契约。M6 的 backup held-fd gate、state 后复核、per-config/worktree generation lock、expected cleanup、IM preflight 与结构化 descendant ownership 均有真实实现和直接回归；Round 5 W13 已由 owned `Popen.wait()` 修复。独立 affected 验证全部通过，但仓库规定的 xdist full 命令在本轮正常结束为 `6 failed, 3592 passed`，且多组冻结失败路径仍可能只恢复 leader，因此保留 2 个 WARNING。

## Prior Issue / M6 Closure

| Focus | 结论 | 证据 |
|---|---|---|
| W13 Darwin zombie teardown | closed | quoted-path test 持有本次 `Popen`，正常 stop 后 `wait()` 回收，兜底只对仍 live 的 owned handle 发信号：`tests/integration/test_gateway_legacy_state_upgrade.py:59-95` |
| Backup content/mode commit gate | closed | existing/new backup guard 持有 fd，并在 replace 前以 `pread` 重读完整 content、复核 mode/inode/link/size/mtime revision：`src/personal_assistant/config/local_store.py:737-864`；public save drift regression `tests/unit/personal_assistant/test_config_migration_backup_guard.py:41-97` |
| Post-state publication / group-only rollback | closed | durable state 后重验 child poll、PID、完整 identity 与 PID+birth，再次 poll 后才返回；失败 rollback 每阶段只 group signal 一次：`src/personal_assistant/main.py:2571-2603,2606-2635,5167-5190` |
| Public lifecycle generation / expected cleanup | closed | resolved config hash 对应稳定 external flock；start 持锁到 publication commit，stop 持锁覆盖 snapshot→signal→expected state/PID/identity cleanup：`src/personal_assistant/main.py:2448-2491,2494-2769`；public concurrent regression `tests/unit/personal_assistant/test_gateway_lifecycle_generation.py:24-130` |
| e2e generation / IM preflight | closed | up/down 全程持 external FD 9 lock，长驻 child 关闭 fd；down 在任何 Gateway signal 前 snapshot IM evidence并在 Step 2 复核 revision：`scripts/e2e-lifecycle-lock.sh:4-63`、`scripts/e2e-down.sh:216-309,432-463`；8 generation/preflight regressions通过 |
| PID==PGID / same-group + detached ownership | mostly closed | up 以 `setsid()+exec` 建 exclusive leader；Python snapshot冻结 PID/PPID/PGID/birth，down/rollback 的成功路径 detached-first、leader-last，确认全 set退出后才清 evidence/停 IM：`src/personal_assistant/main.py:4386-4608`、`scripts/e2e-up.sh:395-404`、`scripts/e2e-down.sh:351-430`；冻结失败恢复见 W14 |
| Final full / residue | not closed | affected 94 tests与静态门禁通过；本轮 full正常 exit 1，5 个 M6 shell-related tests在 xdist负载下失败，见 W15。失败留下的本 verifier 专属 PID/PGID 已按命令与临时目录 ownership 精确清理，最终无 process/port/worktree residue |
| Canonical spec 归并 | deferred as designed | delta-spec 与实现一致；按 orchestrator 收尾契约，在最终验收/修复后归并 `docs/specs/gateway/service-lifecycle.md`，本轮不提前修改 canonical |

## Completeness

- Tasks: 63/63 marked complete（M1 5，M2 6，M3 6，M4 19，M5 19，M6 8）；无未勾选项。
- Requirement 覆盖: 4/4。消息与主动任务仍由进程内 Kernel 执行；Gateway operator lifecycle 保留；三项 timing 单向迁移并安全 canonical save；e2e 只管理 IM + Gateway。
- Scenario 覆盖: 10/10。M6 未改消息、heartbeat/cron、IM offline autonomy；其增量集中在 lifecycle transaction 的异常边界。
- Prototype / Reference: N/A；本 unit 无前端原型或 reference contract。

## Correctness

| Requirement / Scenario group | 实现与测试证据 | 状态 |
|---|---|---|
| 消息、Heartbeat/Cron、IM 离线自治 | M6 delta 未改 runtime message/channel/kernel wiring；zero-seam contract与完整套件绝大多数行为断言通过 | covered |
| 默认 start / stop / restart | state 后 liveness+identity commit gate、group-only rollback、per-config generation lock与 expected cleanup 均有 public 回归 | covered |
| timing 迁移 / canonical save | held backup fd 在 commit gate 重读 content并复核 mode/revision；existing/new in-place drift均保留 source | covered |
| 旧连接/HTTP 字段不形成输入 | zero-residue contract通过；生产接口未恢复 `KernelConfig`、process manager、health endpoint或 `.api.pid` | covered |
| e2e 只管理 IM + Gateway且失败收口 | external generation lock、IM preflight、exclusive leader、same/detached成功回收与 birth mismatch零 TERM/KILL均覆盖；W14 是冻结中途失败恢复缺口 | covered with warning |

### Test Evidence

- focused Python lifecycle/config/legacy/contract: `53 passed, 2 warnings in 15.32s`。
- e2e generation/IM preflight: `8 passed in 18.69s`；owned descendant real processes: `4 passed, 2 warnings in 29.44s`；e2e-up: `6 passed in 24.06s`；e2e-down: `23 passed in 147.20s`。合计 affected 94 tests全部通过。
- full mandated command：`pytest -m "not e2e" -n 4 --dist worksteal --durations=20 --durations-min=0.5 -q` 正常结束，`6 failed, 3592 passed, 1 skipped, 22 warnings in 227.31s`。一个 `test_liveness_ticker` 是全仓负载抖动；其余 5 个与 M6 shell lifecycle 测试的 timeout/固定 sleep有关，见 W15。
- 将 liveness ticker 对照 + 4 个 M6 shell失败单独重跑：`5 passed, 2 warnings in 67.23s`；但 yq wrapper 独立重跑仍因 down 超过20秒而 `1 failed in 24.92s`。产品断言主路径通过，测试门禁仍有一个可稳定复现的 cleanup timeout。
- `ruff check`、affected `ruff format --check`、`bash -n`、`git diff --check` 均通过。
- full/独立 timeout 遗留的 verifier-owned PGID `67014/73716/73719/88241` 已按 exact pytest-609/611 path/command核对后 CONT/TERM/KILL；端口 `50785/51299/52501`、process scan与 verify worktree均无残留。

## Coherence

| design / M6 决策 | 遵守? | 证据 |
|---|---|---|
| D1 删除 dead manager且无替代 port | 是 | `GatewayProcessManager`/runtime `KernelConfig` 已删除；Gateway background factory与 `_KernelClientShim` 保留 |
| D2 timing 归 Gateway且迁移事务安全 | 是 | `GatewayLifecycleConfig`、stable config sidecar、held backup revision与 atomic replace/rollback沿用同一机制 |
| D3 PID/start confirmation，不制造 readiness | 是 | parent只确认 durable PID/identity/state和 child liveness；无 health/readiness field或IPC |
| D4 生产关闭顺序不变 | 是 | M6只强化 operator/e2e process ownership；GatewayRuntime producer/channel/kernel/cron/IM顺序未重排 |
| M6 generation boundaries | 是 | public按 config hash、e2e按 physical worktree hash各自使用不可 unlink的 stable inode；没有平行的可变锁文件 |
| M6 owned descendant freeze | 部分 | 成功路径满足 PID/PPID/PGID/birth + detached-first信号与全员exit commit；W14 的 partial STOP失败恢复不完整 |

### Architecture Coherence

- 依赖方向保持：production delta仅在 `personal_assistant`与 scripts 内；`personal_assistant`未新增 `agent.core` / `agent.platform` import，IM未反向访问 Gateway workspace。
- 没有把 Kernel subprocess seam换名重建；进程树 helper管理的是 Gateway自己拥有的 e2e descendants，与进程内 Kernel拓扑一致。
- generation lock、config transaction lock与 lifecycle evidence各有不同一致性职责，未出现重复竞争的平行状态源。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

#### W14 — 多组 freeze 中途失败只恢复 leader，detached 后代可能永久停在 STOP 状态

`e2e_freeze_gateway_owned_processes()` 先 STOP leader group，再通过 `e2e_signal_gateway_owned_groups ... STOP` 逐组停止 detached groups（`scripts/e2e-owned-processes.sh:145-179`）。如果第二个或后续 group signal/复核失败，函数重试；三次仍失败时只执行 `kill -CONT -- "-$leader_pid"`（`:180-188`），没有记录并 CONT 已成功 STOP 的 detached PGID。并且 group列表先由独立 Python进程整体验证并输出，shell随后才逐条 `kill`（`:148-164`），每个 signal前不再复核该 group的 birth/membership。这样 descendant drift、权限失败或高负载 timeout可让 down/rollback报失败并保留证据，却把部分 owned detached进程永久暂停；这与 M6“descendant drift在破坏性动作前 fail closed、失败保留完整可诊断栈”的目标不完全一致。现有 birth-drift test只覆盖 Python `signal_gateway_owned_process_set()` 的零信号（`tests/integration/test_gateway_owned_process_set.py:139-177`），成功 rollback test也不覆盖第二组 STOP失败（`:180-196`）。

修复：把“逐组即时验证 + signal + 已成功 STOP PGID ledger”收敛进同一 Python helper；每个 group在 `killpg` 前重验 frozen PID/birth/PGID/membership。任何阶段失败时，仅对 ledger 中仍匹配原 birth的所有 group逐组 CONT，确认没有 owned process留在 `T` 后再 fail closed。新增 second-group STOP failure / capture-confirm drift 两个 shell integration regression，断言零 TERM/KILL、所有 leader/detached均非 STOP、IM与lifecycle evidence完整保留。

#### W15 — M6 lifecycle 测试在规定 xdist full 门禁下依赖过短 wall timeout和固定 sleep，完整门禁不可重复全绿

M6 progress记录规定 full为 `3598 passed`（`M6-fix-generation-and-descendant-ownership/progress.md:42-44`），但本轮相同 xdist命令正常结束为 `6 failed, 3592 passed`。其中与本 unit相关的 5 个失败里，4 个和 liveness负载对照单独重跑通过；yq wrapper独立重跑仍稳定失败：`_run_up()`统一硬编码 15 秒（`tests/integration/test_e2e_up_script.py:207-215`），导致 readiness rollback、survivor和detached rollback在并发负载下 timeout；existing yq wrapper的 down cleanup固定 20 秒并在独立运行中也超时（`tests/unit/personal_assistant/test_gateway_im_resilience_e2e_wrapper.py:212-224`）；busy-sidecar regression让 holder固定 `sleep(30)`（`tests/integration/test_e2e_down_script.py:525-562`），而本轮该 down在负载下耗时39.45秒，锁先自然释放，测试反而误报成功。完整门禁因此无法证明M6“最终唯一 full全绿”，且 timeout会留下测试子进程，需要人工 ownership cleanup。

修复：将 busy holder改成 stdin/event控制、由 test finally显式释放（复用 `test_e2e_lifecycle_generation.py` 的 holder模式），不要用固定 sleep当锁契约；给 up/down harness使用与脚本内部 budget一致、可按场景覆盖的 timeout，并确保 `TimeoutExpired` 时按本次 `Popen`/process-set ownership立即回收。修后必须重跑规定 xdist full命令，并在同一次 run后断言无 pytest temp Gateway/IM/STOPped descendant residue。

### SUGGESTION（可以修）

无。

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

# Round 7

## Verification Report: refactor-461

### Summary

Mode: full
Delta range: `14cd8af19..fe5f7eb71`
Focus issues: Round 6 W14 partial-freeze recovery; W15 external lifecycle-test deadlines; stale whole-config writes; public and e2e process-instance ownership
requires_full_verification: false

| Dimension | Result |
|---|---|
| Completeness | 70/70 tasks complete; all four requirements implemented |
| Correctness | 10/10 scenarios covered; Round 6 W14 and W15 closed |
| Coherence | D1-D5 followed; no dependency reversal or parallel lifecycle seam |

This full verification read the unit motivation, design, gateway delta-spec, all M1--M7 task/progress records, prior verification rounds, the current Gateway lifecycle contract, and the project testing/architecture/commenting rules. It verified unit integration head `fe5f7eb71`.

## Prior Issue / M7 Closure

| Prior focus | Result | Evidence |
|---|---|---|
| W14: a partial descendant freeze could leave a detached group stopped | closed | Shell freeze delegates to `freeze_gateway_owned_process_set()` (`scripts/e2e-owned-processes.sh:167-182`). The Python transaction captures, stops, confirms, and resumes every captured original PID on every failed attempt (`src/personal_assistant/main.py:4731-4776`); its regression covers shell delegation and real same-group/detached descendants (`tests/integration/test_gateway_owned_process_set.py:118-297`). |
| W15: test harness applied independent 15/20/30-second deadlines | closed | Lifecycle helpers no longer impose a second subprocess deadline (`tests/integration/test_e2e_up_script.py:175-230`; `tests/unit/personal_assistant/test_gateway_im_resilience_e2e_wrapper.py:185-235`). M7 records a clean required full run: `3608 passed, 1 skipped, 30 warnings in 292.14s`. |
| Stale token or IM sync could overwrite another writer's fields | closed | Both writers call the locked narrow mutation API (`src/personal_assistant/main.py:980-986,4008-4048`), whose latest-revision read, mutation and atomic commit remain inside one transaction lock (`src/personal_assistant/config/local_store.py:1145-1184`); reverse-order regressions are in `tests/unit/personal_assistant/test_gateway_config_mutation_ownership.py:31-115`. |
| Public/e2e teardown could signal an unproven process or incompletely clean its descendants | closed | Public stop freezes the full PID/PPID/PGID/birth set, TERM/CONT/KILLs it, and clears evidence only after every original birth exits (`src/personal_assistant/main.py:2780-2813,4461-4779`). E2E startup publishes IM identity before PID (`scripts/e2e-up.sh:486-528`); teardown snapshots and validates the PID/identity pair before Gateway signals and again before IM teardown/cleanup (`scripts/e2e-down.sh:216-430,560-635`). |

## Completeness

- Tasks: 70/70 marked complete: M1 5/5, M2 6/6, M3 6/6, M4 19/19, M5 19/19, M6 8/8, and M7 7/7. No unchecked task remains.
- Requirements: all four requirements from `motivation.md` have a production mapping and durable regression coverage.
- Prototype / reference: N/A. This is a lifecycle/configuration refactor with no frontend prototype contract.

## Correctness

| Requirement / Scenario group | Implementation evidence | Durable test evidence | Status |
|---|---|---|---|
| Messages plus heartbeat/cron remain on the in-process Kernel | `build_runtime()` imports the SDK and creates `build_pa_kernel()` in the Gateway process (`src/personal_assistant/main.py:3103-3166`); no `agent.core`/`agent.platform` import or subprocess manager remains. | `tests/unit/personal_assistant/test_gateway_runtime_lifecycle.py` and `test_gateway_shutdown_order.py`; active-scope seam guard `tests/contract/test_no_dead_kernel_subprocess_seam.py:17-95`. | covered |
| Default start is PID/liveness confirmation; stop/restart preserve graceful, forced, single-instance lifecycle results | Launcher waits for a durable PID/identity and confirms it after state publication (`src/personal_assistant/main.py:2554-2695`); `run_gateway()` takes the runtime instance claim (`src/personal_assistant/main.py:2400-2420`), and public stop clears evidence only after the frozen owned set exits (`src/personal_assistant/main.py:2720-2844`). | `tests/unit/personal_assistant/test_gateway_launch.py`, `test_gateway_pid_lifecycle.py`, `test_gateway_lifecycle_generation.py`, and `test_gateway_process_ownership_closure.py`. | covered |
| IM-offline autonomy is not coupled to a removed Kernel HTTP service | Gateway continues to build its local SDK kernel before IM connection management (`src/personal_assistant/main.py:3103-3185`); no standalone Kernel endpoint is introduced. | Existing gateway runtime and heartbeat pipeline regressions, including `tests/im_service/integration/test_heartbeat_config_sync_pipeline.py`. | covered |
| Legacy timing migrates field-by-field; canonical writes own only Gateway timing and protect the original file | Loader selects `gateway` first and only falls back to the three legacy fields (`src/personal_assistant/config/local_store.py:325-367,1448-1498`); write/mutation transactions retain backup/CAS/atomic-commit behavior (`src/personal_assistant/config/local_store.py:1109-1184`). | `tests/unit/personal_assistant/test_local_store.py`, `test_config_migration_backup_guard.py`, `test_config_migration_transaction.py`, and M7 mutation-ownership tests. | covered |
| Dead command/HTTP fields have no runtime authority | The active-scope contract rejects the manager, health URL, API PID, old app and legacy config object (`tests/contract/test_no_dead_kernel_subprocess_seam.py:17-95`). | Same contract test passed in this verification. | covered |
| One-command true stack owns only IM and Gateway and fails closed on incomplete, reused, or changed ownership evidence | E2E Gateway runs as its own session leader and must publish the matching public identity (`scripts/e2e-up.sh:600-665`); IM PID + identity files are immutable-snapshotted and bound to birth/argv/cwd before any destructive action (`scripts/e2e-down.sh:216-430,560-618`). | `tests/integration/test_e2e_up_process_ownership.py`, `test_e2e_lifecycle_generation.py`, `test_gateway_owned_process_set.py`, and selected `test_e2e_down_script.py` negative cases. | covered |

### Test Evidence

- This verification passed `90` focused config/lifecycle/runtime/heartbeat tests in `2.90s`.
- The independent M7 contract/ownership/e2e-generation selection and seven fail-closed e2e-down cases passed; they cover PID/birth mismatch, missing owner evidence, freeze delegation, survivor retention, and busy sidecar retention.
- `ruff check` and `ruff format --check` passed for the affected Python sources/tests; `bash -n` passed for `scripts/e2e-up.sh`, `scripts/e2e-down.sh`, and `scripts/e2e-owned-processes.sh`; `git diff --check 14cd8af19..fe5f7eb71` passed.
- M7's recorded final gates additionally show the mandated full non-e2e run (`3608 passed, 1 skipped`) and a real isolated `e2e-up.sh`/`e2e-down.sh` lifecycle with matched identities and no residue (`M7-fix-process-and-config-ownership/progress.md:39-46`).

## Coherence

| Design decision | Followed? | Evidence |
|---|---|---|
| D1: remove the dead manager rather than create a replacement port | yes | Only Gateway's own background `Popen` factory remains (`src/personal_assistant/main.py:2554-2663,5284-5293`); the active-scope contract forbids reintroducing the old manager/API surface. |
| D2: move live timing to Gateway with a safe one-way migration | yes | `GatewayLifecycleConfig` is the typed runtime field, with per-field legacy fallback and transactional migration backup (`src/personal_assistant/config/local_store.py:275-322,1109-1184,1448-1498`). |
| D3: distinguish child-start confirmation from readiness and bind stop to process identity | yes | The launcher explicitly promises only PID/liveness confirmation (`src/personal_assistant/main.py:2554-2574,5296-5341`); identity/birth evidence gates stop and cleanup. |
| D4: retain the real Gateway shutdown sequence | yes | Kernel remains an in-process runtime resource; the regression suite preserves heartbeat/channel/kernel/cron/IM shutdown ordering (`tests/unit/personal_assistant/test_gateway_shutdown_order.py:124-246`). |
| D5: clean active entrypoints without rewriting history | yes | The narrow contract checks active docs/scripts/configs but deliberately excludes archived/change history (`tests/contract/test_no_dead_kernel_subprocess_seam.py:41-95`). |

### Architecture Coherence

- `personal_assistant` still uses only `agent.sdk`; no forbidden `agent.core` or `agent.platform` import was found.
- The process-set helpers extend Gateway's existing lifecycle ownership boundary. They do not create a Kernel subprocess, a second lifecycle authority, or an IM-to-Gateway filesystem dependency.
- Configuration locking, runtime instance claiming, and e2e generation locking retain distinct scopes and commit points; the M7 mutations reuse the existing atomic config transaction rather than creating a parallel writer path.

## Issues

### CRITICAL (must fix before PR)

None.

### WARNING (should fix)

None.

### SUGGESTION (optional)

None.

All checks passed. Ready for PR.
