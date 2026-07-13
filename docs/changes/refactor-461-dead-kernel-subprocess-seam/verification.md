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
