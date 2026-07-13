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
