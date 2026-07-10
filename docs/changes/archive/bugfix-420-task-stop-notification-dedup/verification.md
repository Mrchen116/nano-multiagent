# Verification Report: bugfix-420

> Round 1 — 2026-06-22

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 3/3 tasks; 2/2 requirements |
| Correctness | 4/4 scenarios covered |
| Coherence | 4/4 design 决策落地；1 个 WARNING（auto-background 回归）；1 个 SUGGESTION（tool description 失实） |

1 critical issue found. Fix before PR.

---

## Completeness

**Tasks: 3/3 complete**

- [x] C1 红测：`570baaf5`，7 红测全覆盖三层（registry / task_stop / RuntimeRunner）。
- [x] C2 实现：`936bb66b`，红测转绿，design 4 条决策全落地。
- [x] C3 文档：`17be6d09`，tasks 勾选 + design changelog。

**Spec 覆盖**

| Requirement | 实现位置 | 状态 |
|---|---|---|
| 停后台 bash 不再多发冗余通知 | `task_stop.py:88-89`（bash 同步 kill notified=True）+ `wiring.py` _NotifyingStore 抑制 | 有实现 |
| 停后台 subagent 通知携带半成品产出 | `task_stop.py:80-89`（不同步 kill）+ `runtime_runner.py:83-91`（on_kill + result_text）+ `agent.py:671-690`（_make_on_kill → registry.kill result_text）| 有实现 |

---

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 停后台 bash 不再发重复通知 | `task_stop.py:88-89`：`registry.kill(notified=True)` | 单测 `test_stop_running_bash_task_kills_synchronously_and_suppresses_notification`（record.notified is True）+ 整合 `test_task_stop_kills_running_bash_task`（runs.submissions==[], runs.injections==[]） | covered |
| 停后台 subagent 通知携带部分结果 | `runtime_runner.py:83-91`（is_aborted → on_kill with result_text）+ `agent.py:671-690`（_make_on_kill → registry.kill result_text） | 单测 `test_runtime_runner_aborted_run_invokes_on_kill_with_result`（result_text="partial findings here"）+ 整合 `test_task_stop_kills_running_agent_task`（injected 含 `<result>subagent done</result>`） | covered |
| 子 agent 无产出时通知省略 result | `runtime_runner.py:71`（_extract_assistant_text 返回 None 时）+ `registry.kill` result_text=None + notifications.py 只在 result_text 非空输出 `<result>` | 单测 `test_runtime_runner_aborted_run_with_no_output_omits_result`（result_text=None）+ `test_kill_result_text_defaults_none` | covered |
| 停止后任务进 killed 终态且可续跑 | 整合 `test_task_stop_kills_running_agent_task`（record.status==KILLED after worker unwind）；resume 对 killed-in-memory record 可走 `_resume_subagent`（agent.py:324）| 整合测试覆盖 KILLED 终态；resume 路径现有回归未被本 unit 破坏 | covered |

**附加覆盖**

- 自然完成不被误标 killed（design 风险 3）：`test_runtime_runner_natural_completion_not_misflagged_as_kill`（abort_during_run=False → on_complete）— covered。
- kill 幂等（二次终态 no-op）：`test_kill_is_idempotent_after_terminal`（二次 kill 不覆盖 result_text/error/notified）— covered。

---

## Coherence

| design 决策 | 遵守? | 代码证据（file:line） |
|---|---|---|
| 决策 1：bash → 同步 `registry.kill(notified=True)` 抑制通知 | 是 | `task_stop.py:88-89`：`if record.task_type != BackgroundTaskType.SUBAGENT: registry.kill(task_id, reason="stopped by user", notified=True)` |
| 决策 2：subagent → 只 `request_stop`，终态由 worker abort-unwind 承载 | 是（显式后台路径）| `task_stop.py:80-89` SUBAGENT 分支不调 kill；`runtime_runner.py:83-91` is_aborted → on_kill | 见下方 WARNING |
| 决策 3：新增 `TaskKillCallback` + `on_kill` 回调，区分 killed-with-result | 是 | `interfaces.py:103-120`（TaskKillCallback 协议）+ `agent.py:671-690`（_make_on_kill）；两处 callsite（agent.py:188, 433）均加 on_kill=；`_NoOpSubagentRunner`（wiring.py:225）同步加 on_kill 形参 | 
| 决策 4：`registry.kill()` 扩参 `notified=False` / `result_text=None`，镜像 `complete()` | 是 | `registry.py:158-185`，签名 `kill(task_id, *, reason, notified=False, result_text=None)`，`_guard_terminal` 在最前，`replace(... notified=notified, result_text=result_text)` |

**架构自洽性（§4.3）**

改动均为 `platform → core` 方向（task_stop/runtime_runner/agent.py/wiring.py 改 platform 层；registry/interfaces 改 core 层，仅添加参数/协议，不引入 platform 依赖）。`coding_cli` / `personal_assistant` 只 import `agent.sdk`，未被改动。依赖方向合规。

---

## Issues

### CRITICAL（提 PR 前必须修）

**C1: auto-background subagent 被 task_stop 后 record 留 RUNNING，最终以 COMPLETED 而非 KILLED 终态关闭**

- **根因**：`_run_foreground` 路径下 foreground 超时自动转 background 后，用 `submit_foreground` 启动了裸 coroutine（非 `start`+callback 路径），由 `_start_registry_watcher`（`agent.py:622-640`）监听 future 结果，该 watcher 只有 `complete` / `fail` 路径，**没有 on_kill 回调**。bugfix-420 前，task_stop 对所有 SUBAGENT 都同步调 `registry.kill`，auto-background subagent 也能正常进 KILLED 终态。bugfix-420 后，task_stop 对 SUBAGENT 只 `request_stop` 不同步 kill，但 auto-background 路径没有 stop_handle（`set_stop_handle` 未被调用），所以 `request_stop` 返回 True（非终态记录存在，handle 为 None，照样 return True）但实际上没有 abort 信号发出。future 继续运行完成后，`_start_registry_watcher._watch` 调 `registry.complete`，任务以 COMPLETED 而非 KILLED 关闭。
- **影响**：仅影响前台 agent 超时自动转后台（auto-background）的 subagent（`run_in_background=False` + 超时路径）。显式 `run_in_background=True` 的后台 subagent 路径不受影响。
- **可执行修复方向**：在 `_start_registry_watcher` 中也处理 abort 情况，或在 auto-background 的 watcher 中检测 controller 是否已 abort。更彻底的方案是让 auto-background 路径也走 `start(on_kill=...)` 而非 `submit_foreground`（但需重构，超出本 unit 范围）。
  - **最小修复**：在 `_start_registry_watcher._watch` 里捕捉到 `concurrent.futures.CancelledError` 或在 `future.result()` 后检测 controller abort，走 `registry.kill` 而非 `registry.complete`。然而 auto-background 路径的 controller 在 future 提交后没有被保存，无法在 watcher 里访问。
  - **实际可行修复**：在 auto-background 路径（`_run_foreground` 超时分支，`agent.py:251-275`）：注册一个 `_StopHandle`（调 `future.cancel()`），让 `request_stop` 能真正 cancel future；同时在 `_start_registry_watcher` 检查 `future` 是否被 cancelled，走 `registry.kill(notified=False, result_text=...)`（SUBAGENT 路径）。
  - 相关文件：`src/agent/platform/tools/builtins/agent.py:251-275`（auto-background 注册段）、`agent.py:622-640`（`_start_registry_watcher`）。

### WARNING（应该修）

无额外 WARNING。

### SUGGESTION（可以修）

**S1: `task_stop` tool description 对 bash 任务失实**

- `task_stop.py:27`：description 写 `"...a notification will be sent to the parent session."`，但 bugfix-420 后停 bash 任务时 model-facing 通知被抑制，LLM 只看到 tool_result，不再收到 `<task-notification>`。该 description 是 tool 对 LLM 的提示文本，失实可能导致 LLM 对停止结果有误判。
- 建议：改为 `"...The task is marked as killed. For bash tasks, no additional notification is sent (the tool_result is the stop confirmation). For subagent tasks, a notification carrying the partial result will be delivered."` 或更简洁的类似表达。
- 相关文件：`src/agent/platform/tools/builtins/agent.py` → 实为 `src/agent/platform/tools/builtins/task_stop.py:26-28`。
