# Verification Report: bugfix-417

> Round 6 — 2026-06-19
>
> 背景：Round 5 verdict pass（0 critical / 0 warning / 0 suggestion），但报告 commit 未真推到 origin（orchestrator 发现 `git log origin/unit/bugfix-417` 看不到 c0e2852f）。Round 6 为强制复验：自建 worktree、读代码核对、确认 Round 5 结论在当前代码态仍成立、提交并 push 报告。

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 24/24 tasks |
| Correctness | 全部 requirement/scenario 有实现且测试覆盖，全测试树 2696 passed |
| Coherence | 决策 1-11 全部遵守；架构边界清洁（contract 126 passed） |

No critical issues. 0 warnings, 0 suggestions. Ready for PR.

---

## Completeness

### Task 完成检查

- M1 tasks.md：退出标准 5 项全 `[x]`，R1/R2 DONE。
- M2 tasks.md：退出标准 5 项全 `[x]`，R1/R2 DONE（superseded by M4，符合预期）。
- M3 tasks.md：退出标准 7 项全 `[x]`，R1-R4 DONE。
- M4 tasks.md：退出标准 6 项全 `[x]`，R1-R5 DONE + live 复验 DONE。
- M5 tasks.md：退出标准 8 项全 `[x]`，R1-R7 DONE + 收尾/双产品 live DONE。
- M6 tasks.md：退出标准 8 项全 `[x]`，R1 + DONE 硬闸 + 全树/静态检查 + live DONE。

**Tasks: 24/24 complete**

### Spec 覆盖检查

delta-spec 涉及三包：kernel（MODIFIED cancel + ADDED liveness）、gateway（MODIFIED 两条）、im（REMOVED + ADDED + MODIFIED），对应实现均已落地。fix2 无新增 spec delta——它是 M5 决策 10 的实现细节修复（`/stop` ack 投递 + cancelled 收口），属于 design 决策 10 已声明的「用户主动中断」scenario 的补全。

---

## Correctness

### 全测试树验证

```
pytest -m "not e2e" --tb=short -q
=> 2696 passed, 0 failed, 2 skipped
```

```
pytest tests/contract/ -q --tb=short
=> 126 passed
```

```
ruff check src/ tests/
=> No issues found
```

### Kernel delta-spec

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| 取消 parked run → 强制终止 + 释放 session 锁 | `registry.py:561` `_force_cancel_owned_task` + `loop.call_soon_threadsafe(task.cancel)` | `test_run_cancel.py::test_cancel_force_releases_session_lock_so_next_run_proceeds` | covered |
| kernel.cancel 连带取消 broker pending | `kernel.py:986` `cancel_all_pending(run_id=run_id)` | `test_kernel_cancel_permission.py::test_kernel_cancel_denies_pending_permission_for_run` | covered |
| 幂等：已终态/无 Task cancel 安全无害 | `registry.py:490-503` 已终态/task.done() 跳过 | `test_run_cancel.py::test_cancel_already_terminal_run_is_idempotent_noop` | covered |
| alive-but-quiet：工具执行期 stream 有 liveness 事件 | `tools/registry.py` 实时 dispatch + `realtime_stream.py:127-135` `on_tool_execution_update` → `run_heartbeat` | `test_bugfix_417_tool_heartbeat_realtime.py` | covered |
| alive-but-quiet：等 LLM 期 stream 有 liveness 事件 | `agent/core/agent/liveness.py` `_with_liveness_heartbeat` wraps LLM stream | `test_bugfix_417_liveness_ticker.py::test_with_liveness_heartbeat_emits_during_wait` | covered |
| alive-but-quiet：等权限期 stream 有 liveness 事件 | `runtime.py:1469` `_emit_liveness_heartbeats(..., source="permission")` | `test_bugfix_417_liveness_ticker.py` permission-await 系列 | covered |
| build_kernel 真链路 run_heartbeat 到 stream | `tests/integration/test_bugfix_417_bash_engine_e2e.py`（3 passed） | 端到端集成测试即为 DONE 硬闸 | covered |
| M5 新增：interrupt 杀在飞前台子进程树 + 收口徽标 | `registry.py:489-506` `interrupt` 调 `foreground_stopper` + force-cancel；`bash.py:387-396` `_ForegroundStopper` 即时唤醒 | `test_run_cancel.py` interrupt 系列 + `test_bash_tool.py` 前台 stopper 唤醒 | covered |
| M5 新增：用户中断回填 CC content | `jsonl_store.py` `USER_INTERRUPT_RECOVERY_CONTENT` + `runtime.py` 透传 `is_user_interrupt` | `test_session_manager.py` user vs system 两路 | covered |
| M5 新增：CLI Ctrl-C → interrupt + REPL 存活 | `coding_cli/commands.py` signal handler + in-loop catch | `test_cli_async_repl_sdk.py`（19 passed） | covered |
| M6 新增：非 bash 长工具通用 liveness | `liveness.py:142` `execution_update_ticker` + `tools/registry.py:287` `async with ticker` | `test_bugfix_417_generic_tool_liveness.py`（16 passed） | covered |

### Gateway delta-spec

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| liveness 心跳判存活（移除 awaiting_permission 特例） | `inbound_pipeline.py:961` 注释 + `reason="stalled"` | `test_inbound_pipeline_permission_watchdog.py` 10 passed | covered |
| 静默长命令不被误杀 | 心跳在 watchdog idle 窗内重置 120s 计时 | `test_inbound_pipeline_permission_watchdog.py::test_heartbeat_resets_idle_timer` | covered |
| 失去 liveness 判 stalled + 强制 cancel | `inbound_pipeline.py:980` `reason="stalled"` | `test_inbound_pipeline_permission_watchdog.py::test_true_stall_triggers_cancel_and_stalled_reason` | covered |
| tool 自身 deadline → reason=tool_timeout → "执行超时" | `bash.py:493` `"reason_code": "tool_timeout"` + 前端映射 | `test_bash_tool.py` 超时带 reason_code=tool_timeout；端到端 e2e 验 `tool_end.reason_code=tool_timeout` | covered |
| watchdog 收尸 → reason=stalled → "已中断" | `inbound_pipeline.py:980` | `test_inbound_pipeline_permission_watchdog.py` stalled 断言 | covered |
| M5 新增：/stop 中断正在执行的运行 | `inbound_pipeline.py:657-726` `_handle_stop_command` + `_deliver_stop_ack` | `test_gateway_stop_command.py` 12 passed | covered |
| M5 新增：无运行时 /stop 返回友好提示 | `inbound_pipeline.py:673-688` | `test_gateway_stop_command.py::test_stop_command_with_no_active_run_returns_friendly_message` | covered |
| fix2 增量：/stop ack 真投递到 IM | `inbound_pipeline.py:728-769` `_deliver_stop_ack` | `test_stop_ack_delivered_via_bg_reply_sender_when_wired` | covered |

### IM delta-spec

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| REMOVED: permission 专用豁免 | `relay_watchdog.py:52-54` 注释 + 移除 SQL 豁免子句 | `test_relay_watchdog.py`（通过全树间接覆盖） | covered |
| ADDED: run_heartbeat 推进 last_evt 不误杀活跃消息 | `ws/gateway_handler.py` kind=run_heartbeat → `event_bridge.on_run_heartbeat` | `test_relay_watchdog.py::test_fresh_heartbeat_keeps_message_alive` | covered |
| ADDED: 崩溃停心跳后 stale → 被正常回收 | `relay_watchdog.py` 统一 last_evt 判据 | `test_inbound_pipeline_permission_watchdog.py::test_crash_stops_heartbeat_then_reaped` | covered |
| MODIFIED: tool_timeout → 执行超时，stalled → 已中断 | 前端 `tool-calls-panel.tsx:83` + IM reason=stalled | `test_relay_watchdog.py` reason=stalled 断言 | covered |
| fix2 增量：用户 /stop 后工具卡显示 CC content | `main.py:3708-3709` reconcile_output 投影到 tool_call.output | `test_inbound_pipeline_streaming.py::test_user_stop_reconcile_finalizes_bubble_and_closes_badge` | covered |
| fix2 增量：用户 /stop 后气泡正常关闭 | `main.py:3723-3744` `finalize_bubble` → `message_completed` | `test_inbound_pipeline_streaming.py::test_user_stop_reconcile_finalizes_bubble_and_closes_badge` | covered |

---

## Coherence

### design 关键决策遵守情况

| 决策 | 遵守 | 代码证据 |
|---|---|---|
| 决策 1 A: registry.cancel 强制 task.cancel | 是 | `registry.py:561` `_force_cancel_owned_task` |
| 决策 1 A: kernel.cancel 连带 cancel_all_pending | 是 | `kernel.py:986` |
| 决策 2/3 B: 心跳由"确实在前进的执行层"发出 | 是 | `liveness.py` await-bound 设计 + `loop.py/runtime.py` 包住 await 点 |
| 决策 4 B: permission liveness 进 kernel.stream 同一通路 | 是 | `runtime.py:1469` 同款 `_emit_liveness_heartbeats`，`inbound_pipeline.py:961` 已删 awaiting_permission 分支 |
| 决策 5 B+C: tool_timeout vs stalled 区分 | 是 | `bash.py:493` + `inbound_pipeline.py:980` |
| 决策 6 C: start_new_session + killpg + 非阻塞 drain | 是 | `shell_runner.py` killpg + drain + `_stopped` 标记 |
| 决策 7: 不引入 run 级硬上限 | 是 | 无 run-level deadline |
| 决策 8: 删死路 bash_runner.py，ShellRunner 唯一引擎 | 是 | `bash_runner.py` 已删；`bash.py` `_require_wiring` 无 wiring 大声报错 |
| 决策 9: 最小侵入 pump 模型 | 是 | `shell_runner.py` docstring 说明 pump→文件模型保留 |
| 决策 10 M5: interrupt 触发 stopper 杀子进程树 + 收口 | 是 | `registry.py:489-506` + `bash.py:387-396` `_ForegroundStopper` + `jsonl_store.py` content 解耦 |
| 决策 10 M5: 用户中断回填 CC 原串 | 是 | `jsonl_store.py` `USER_INTERRUPT_RECOVERY_CONTENT` + `sdk/__init__.py` 再导出 |
| 决策 11 M6: liveness 上提 executor 通用层 | 是 | `liveness.py:142` `execution_update_ticker` + `tools/registry.py:287` |
| fix2: _deliver_stop_ack 走真 WS 路径 | 是 | `inbound_pipeline.py:728-769`，`_bg_reply_sender` 与 background task 共用同一路由 |
| fix2: user-stopped vs 非 user cancelled 区分 | 是 | `inbound_pipeline.py:1021-1045` + `main.py:3723-3744` finalize_bubble 只给 user stop |

### 架构边界

- `liveness.py` 在 `agent/core/agent/` 下，无 platform import（符合 core 不依赖 platform 约束）。publisher 经注入端口，不直接引用 platform 实体。
- `Kernel.cancel` 在 `sdk/kernel.py` 编排 `registry.cancel` + `broker.cancel_all_pending`，符合"只有 sdk 同时持有 registry 与 broker"约束。
- `_deliver_stop_ack` 的 `from_session_id` 格式与 BACKGROUND_TASK relay 格式镜像，复用 IM 既有解析逻辑，不新增协议。
- contract 测试 126 passed，依赖方向完整无破。

---

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

无。

### SUGGESTION（可以修）

无。

---

All checks passed. Ready for PR.

---

# Round 2 — 2026-06-18

> 见 commit a80544f2。轻量复验，结论 pass。

---

# Round 3 — 2026-06-18

> 见 commit 9f120d67。fix diff 增量验证，结论 pass。

---

# Round 4 / 4b — reviewer regression（继承，不覆盖）

> 见 commit a6a544cb / 7ddc77fe。Round 4 reviewer verdict fail（`/stop` 不被处理），Round 4b 确认 issue 为 cancelled 未收口 + ack 不投递。已派 fix2 worker 修复。

---

# Round 5 — 2026-06-19

> 见 commit c0e2852f。fix2 增量验证 + 全量复验 M5/M6，结论 pass。但报告 commit 未真推到 origin（本 Round 6 强制修复）。

---

# Round 6 — 2026-06-19

> 强制复验：自建 worktree、读代码核对、运行全测试树 2696 passed + contract 126 passed + ruff 无问题。
>
> Round 5 之后无代码变更（HEAD = c0e2852f），所有关键实现位置与测试覆盖与 Round 5 报告一致。结论继承 Round 5：无 critical、无 warning、无 suggestion，Ready for PR。
