# Verification Report: bugfix-417

> Round 2 — 2026-06-18
>
> 背景：Round 1 是 reviewer regression 验证（B1 静默长命令被误杀 / C1 超时 reason=null），M4 是其根因修复（bash 引擎统一 + 删死路）。本轮为 verifier Round 2，核对三维完整性。无 prior_verification_path（Round 1 未跑过 verifier）。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 14/14 tasks（进度记录全 DONE；M4 tasks.md 复选框为文档遗漏，见 SUGGESTION） |
| Correctness | 全部 requirement/scenario 有实现且测试覆盖，全测试树 2657 passed |
| Coherence | 决策 1-9 全部遵守；架构边界清洁（contract 126 passed） |

No critical issues. 0 warnings, 1 doc-only suggestion. Ready for PR.

---

## Completeness

### Task 完成检查

- M1 tasks.md：退出标准 3 项全 `[x]`，R1/R2 DONE。
- M2 tasks.md：退出标准 5 项全 `[x]`，R1/R2 DONE（M2 标 superseded by M4，能力已重落 ShellRunner，符合预期）。
- M3 tasks.md：退出标准 7 项全 `[x]`，R1-R4 DONE。
- M4 tasks.md：退出标准 6 项全是 `[ ]`（未勾选），但 progress.md 明确记录 R1/R2/R3/R4/R5 DONE + live 复验 DONE，roadpoints 表全 DONE。实际工作已完成，仅 tasks.md 复选框未更新（见 SUGGESTION）。

**Tasks: 14/14 complete（以 progress.md 记录为准）**

### Spec 覆盖检查

delta-spec 涉及三包：kernel（MODIFIED cancel + ADDED liveness）、gateway（MODIFIED 两条）、im（REMOVED + ADDED + MODIFIED），对应实现均已落地（见 Correctness 节详细核对）。

---

## Correctness

### Kernel delta-spec

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 取消 parked run → 强制终止 + 释放 session 锁 | `registry.py:487` `_force_cancel_owned_task` + `loop.call_soon_threadsafe(task.cancel)` | `test_run_cancel.py::test_cancel_force_releases_session_lock_so_next_run_proceeds` | covered |
| kernel.cancel 连带取消 broker pending | `kernel.py:975` `cancel_all_pending(run_id=run_id)` | `test_kernel_cancel_permission.py::test_kernel_cancel_denies_pending_permission_for_run` | covered |
| 幂等：已终态/无 Task cancel 安全无害 | `registry.py:490-503` 已终态/task.done() 跳过 | `test_run_cancel.py::test_cancel_already_terminal_run_is_idempotent_noop` | covered |
| 取消后同 session 可继续 submit | M1 R1 整体验证场景 | `test_cancel_force_releases_session_lock_so_next_run_proceeds` 0.16s 通过 | covered |
| alive-but-quiet：工具执行期 stream 有 liveness 事件 | `tools/registry.py` 实时 dispatch + `realtime_stream.py:110` `on_tool_execution_update` | `test_bugfix_417_tool_heartbeat_realtime.py`、`test_realtime_stream_heartbeat.py` | covered |
| alive-but-quiet：等 LLM 期 stream 有 liveness 事件 | `loop.py:320` `_with_liveness_heartbeat` wraps LLM stream | `test_bugfix_417_liveness_ticker.py::test_with_liveness_heartbeat_emits_during_wait` | covered |
| alive-but-quiet：等权限期 stream 有 liveness 事件 | `runtime.py:1446-1451` `asyncio.create_task(_emit_liveness_heartbeats(..., source="permission"))` | `test_bugfix_417_liveness_ticker.py` permission-await 系列 | covered |
| build_kernel 真链路 run_heartbeat 到 stream | `tests/integration/test_bugfix_417_bash_engine_e2e.py`（2 passed，连跑 3 次稳定） | 端到端集成测试即为 DONE 硬闸 | covered |

### Gateway delta-spec

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| liveness 心跳判存活（移除 awaiting_permission 特例） | `inbound_pipeline.py:848-869` 注释 + reason="stalled" | `test_inbound_pipeline_permission_watchdog.py` 7 tests | covered |
| 静默长命令不被误杀 | 心跳在 watchdog idle 窗内重置 120s 计时 | `test_inbound_pipeline_permission_watchdog.py::test_heartbeat_resets_idle_timer` | covered |
| 失去 liveness 判 stalled + 强制 cancel | `inbound_pipeline.py:869` `reason="stalled"` | `test_inbound_pipeline_permission_watchdog.py::test_true_stall_triggers_cancel_and_stalled_reason` | covered |
| tool 自身 deadline → reason=tool_timeout → "执行超时" | `bash.py:446` `"reason_code": "tool_timeout"` + 前端映射 | `test_bash_tool.py` 超时带 reason_code=tool_timeout；端到端 e2e 验 `tool_end.reason_code=tool_timeout` | covered |
| watchdog 收尸 → reason=stalled → "已中断" | `inbound_pipeline.py:869` | `test_inbound_pipeline_permission_watchdog.py` stalled 断言 | covered |

### IM delta-spec

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| REMOVED: permission 专用豁免（awaiting_permission_at marker） | `relay_watchdog.py:52-54` 注释 + 移除 SQL 豁免子句 | `test_relay_watchdog.py` 17 passed（无 permission 特例分支） | covered |
| ADDED: run_heartbeat 推进 last_evt 不误杀活跃消息 | `ws/gateway_handler.py:1193-1202` kind=run_heartbeat → `event_bridge.on_run_heartbeat` → append conversation_events 行 | `test_relay_watchdog.py::test_fresh_heartbeat_keeps_message_alive`，`test_event_bridge.py on_run_heartbeat` | covered |
| ADDED: 崩溃停心跳后 stale → 被正常回收 | `relay_watchdog.py` 统一 last_evt 判据，无崩溃豁免 | `test_inbound_pipeline_permission_watchdog.py::test_crash_stops_heartbeat_then_reaped` | covered |
| MODIFIED: tool_timeout → 执行超时，stalled → 已中断 | 前端 `tool-calls-panel.tsx:83` + IM reason=stalled（relay_watchdog） | `test_relay_watchdog.py` reason=stalled 断言，M3 前端 vitest 通过 | covered |

### 截断契约（M4 决策 B 验证）

按 design.md Changelog 与 M4 progress.md R3 取证：

- `_run_foreground`（生产路径）硬编码 `truncated:False`、无 `fullOutputPath`；行/字节截断 + fullOutputPath 只在已删死路 `_run_legacy_sync`。
- 生产截断真源 = `registry.py:77` `max_result_size_chars=30000` result-budget，由 `tests/unit/test_tool_result_budget.py` 覆盖。
- 删死路对生产截断语义零影响，符合 design 决策 B（orchestrator 已拍板）。

---

## Coherence

### design 关键决策遵守情况

| 决策 | 遵守 | 代码证据 |
|---|---|---|
| 决策 1 A: registry.cancel 经 call_soon_threadsafe 强制 task.cancel | 是 | `registry.py:487,503` `_force_cancel_owned_task` |
| 决策 1 A: kernel.cancel 连带 cancel_all_pending | 是 | `kernel.py:975` |
| 决策 2/3 B: 心跳由"确实在前进的执行层"发出（非 Task 存在即 tick） | 是 | `liveness.py` await-bound 设计 + loop.py/runtime.py 包住 await 点 |
| 决策 4 B: permission liveness 进 kernel.stream 同一通路，无 permission 专用分支 | 是 | `runtime.py:1446-1451` 同款 `_emit_liveness_heartbeats`，`inbound_pipeline.py` 已删 awaiting_permission 分支 |
| 决策 5 B+C: tool_timeout vs stalled 区分两种失败态 | 是 | `bash.py:446` + `inbound_pipeline.py:869` + `relay_watchdog.py:145` |
| 决策 6 C: start_new_session + killpg + 非阻塞 drain | 是 | `shell_runner.py:90,129,204,208-225` |
| 决策 7: 不引入 run 级硬上限 | 是 | 无 run-level deadline，只有 tool 自身 timeout |
| 决策 8: 删死路 bash_runner.py，ShellRunner 为唯一引擎 | 是 | `bash_runner.py` 已删；`bash.py:236-259` `_require_wiring` 无 wiring 大声报错 |
| 决策 9: 最小侵入 pump 模型，不替换 I/O 架构 | 是 | `shell_runner.py:1-22` docstring 说明 pump→文件模型保留 |
| 决策 8 测试策略: 端到端集成测试为 DONE 硬闸 | 是 | `tests/integration/test_bugfix_417_bash_engine_e2e.py` 2 passed，真实 build_kernel wiring |

### 架构边界

- `liveness.py` 在 `agent/core/` 下，无 platform import（符合 core 不依赖 platform 约束）。publisher 经注入端口（`session_event_publisher(hook_ctx)`），不直接引用 platform 实体。
- `Kernel.cancel` 在 `sdk/kernel.py` 编排 `registry.cancel` + `broker.cancel_all_pending`，符合"只有 sdk 同时持有 registry 与 broker、broker 取消在 sdk 层而非 core 层"约束（design.md 架构约束）。
- contract 测试 126 passed，依赖方向完整无破。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

无。

### SUGGESTION（可以修）

**S1: M4 tasks.md 退出标准 6 项复选框未更新为 `[x]`。**

`docs/changes/bugfix-417-timeout-tool-wedges-session/M4-unify-bash-engine/tasks.md` 的退出标准行全是 `- [ ]`，但 progress.md 记录 R1-R5 DONE + live 复验 DONE，roadpoints 表也全是 DONE。收尾前勾选退出标准复选框（`[ ]` → `[x]`），与 progress.md 状态一致，避免对后续读者产生"M4 未完成"的误导。

修法：在 tasks.md 把 6 行 `- [ ]` 改为 `- [x]`。

---

All checks passed. Ready for PR (with noted doc-only suggestion).

---

# Round 3 — 2026-06-18

> 轻量复验：核对 9a87cfe3..99784e19 的 fix diff（ShellRunner `_stopped` 标记 + liveness cleanup）。基于 Round 2 上下文增量核对 Coherence + Correctness。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 继承 Round 2（无新 task 引入） |
| Correctness | fix diff 的两处变更均有对应测试；红测 ecb93e09 → 绿测 b0cddf83；全树 2658 passed |
| Coherence | 决策 6 stop 语义遵守；决策 2/3/4 liveness 不变量保持；无新 divergence |

No critical issues. 0 warnings, 0 suggestions. Round 2 三维结论在此 fix 后仍成立。

## Coherence — fix diff 核对

### _stopped 标记（ShellRunner，决策 6 killpg/stop 语义）

`shell_runner.py` 新增 `self._stopped: set[str]`：`_stop_task` 在 killpg **前**置位（`shell_runner.py:206`），`_monitor` 非零退出前查标记（`shell_runner.py:154-159`）——stop 导致的退出静默返回，让 `TaskStopTool` 的 `registry.kill` 独占 KILLED 终态；timeout 路径（`_monitor` 内同步等宽限）不经 `_stop_task`，`_stopped` 不被置位，`on_fail` 正常触发 tool_timeout，**与决策 6 的 killpg/超时语义完全一致，timeout 路径不变**。

先置位后 killpg 的顺序保证 monitor 线程见到进程退出时标记已在，消除微秒级竞窗。flag 在 lock 内读取再 discard（`shell_runner.py:151-155`），线程安全。

busy-poll 改 `process.wait(timeout=_PROCESS_GROUP_TERM_GRACE_S)`（`shell_runner.py:250-254`）：OS 调度等待代替 50ms 轮询，等价语义（宽限到期后 SIGKILL），CPU 利用率更低。无逻辑变更。

### liveness cleanup（决策 2/3/4 不变量）

三处 cleanup 均不改行为语义：

1. `_emit_liveness_heartbeats` 删 park 分支（`liveness.py`）：原 `publish is None or not run_id` 时 park-forever，现在由调用方 guard（`liveness_ticker` 的 `if publish is None or not run_id: yield; return` 路径，以及 `runtime.py` 的 `if _perm_publish is not None and run_id_for_broker` guard）。结果相同：无 publisher 时不发心跳，ticker 不创建或立即 no-op。
2. `_broker_publish_adapter` + `session_event_publisher` 合并为共用 `_wrap_publisher` 内核（`liveness.py:127-157`）：纯重构，两个公开函数签名不变，行为不变。
3. `runtime.py` permission ticker None-guard：`_perm_heartbeat` 改为 `Task | None`，`finally` 里加 `if _perm_heartbeat is not None` guard（`runtime.py:1563-1567`）。CLI 下 publish=None 时不再产生 park-forever Task，符合决策 2 "心跳由真前进的执行层发出"不变量（CLI 无 event hub，产生 Task 只是空转，不应存在）。PA 场景 publish 非 None，行为与 Round 2 完全相同。

**三处 cleanup 无任何决策 divergence。**

## Correctness — 测试覆盖

| 变更 | 红测（ecb93e09） | 绿测（b0cddf83） | 状态 |
|---|---|---|---|
| `_stopped` 标记：stop 不触发 on_fail | `test_shell_runner_stop_does_not_fire_on_fail` 红（pre-fix monitor 调 on_fail） | 同测试绿（`shell_runner.py:154-159` 静默返回） | covered |
| liveness cleanup（park 分支删除 / None-guard） | `test_liveness_ticker_noop_when_missing` 更新（改测 liveness_ticker 层 no-op，非 _emit_liveness_heartbeats 层） | 通过 | covered |
| killpg busy-poll → process.wait | 既有 `test_shell_runner_timeout_kills_grandchild` 等回归 | 18 passed（含 killpg 整树回收测试）| covered |

全测试树 2658 passed（较 Round 2 多 1 个，即新增的 stop-does-not-fire-on_fail 测试）。端到端集成测试 `test_bugfix_417_bash_engine_e2e.py` 2 passed 不变。

## Issues

### CRITICAL / WARNING / SUGGESTION

无。Round 2 的 S1（M4 tasks.md 复选框）已在 commit 99784e19 修复（docs 勾选 6 行 `[x]`）。

All checks passed. Ready for PR.
