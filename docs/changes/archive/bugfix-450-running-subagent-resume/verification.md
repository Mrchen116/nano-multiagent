# Verification Report: bugfix-450

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks complete; 3/3 requirements implemented |
| Correctness | 5/5 scenarios implemented; 2 warnings |
| Coherence | Mostly followed; terminal cleanup race and test-hardening warnings |

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

## Completeness

- Tasks: 10/10 complete in `docs/changes/bugfix-450-running-subagent-resume/M1-impl/tasks.md`.
- Spec coverage:
  - `running subagent follow-up 真实投递`: covered by live message handle registration in `src/agent/platform/tools/builtins/agent.py:305`, `src/agent/platform/tools/builtins/agent.py:413`, `src/agent/platform/tools/builtins/agent.py:615`, and controller-backed delivery in `src/agent/platform/background_tasks/runtime_runner.py:169`.
  - `不再返回假 queued 状态`: covered by `AgentTool._run_continuation()` only returning `message_queued` after `registry.send_agent_message()` accepts, and raising `agent_message_not_deliverable` otherwise in `src/agent/platform/tools/builtins/agent.py:466`.
  - `既有后台任务体验不退化`: terminal resume remains in `src/agent/platform/tools/builtins/agent.py:499` and `src/agent/platform/tools/builtins/agent.py:555`; `output_file` paths are still returned from launch/resume paths in `src/agent/platform/tools/builtins/agent.py:319`, `src/agent/platform/tools/builtins/agent.py:421`, and `src/agent/platform/tools/builtins/agent.py:629`.

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| running subagent follow-up must be deliverable before acknowledged | `registry.send_agent_message()` gates on running subagent + live handle at `src/agent/core/background_tasks/registry.py:258`; `AgentTool` returns queued only after accepted at `src/agent/platform/tools/builtins/agent.py:466` | `tests/integration/background_tasks/test_agent_continuation.py:105`; `tests/unit/agent/tools/test_agent_tool.py:421` | covered |
| Scenario: follow-up to a running subagent is consumed by that subagent | `_ControllerHandle.send_message()` enqueues `LLMMessage(role="user")` via `RunController` at `src/agent/platform/background_tasks/runtime_runner.py:169`; `AgentLoop` drains pending messages before next LLM request at `src/agent/core/agent/loop.py:316` | Permanent tests consume via runtime/controller at `tests/integration/background_tasks/test_agent_continuation.py:57`; progress records one-time true AgentLoop/LLM-request evidence | covered with WARNING |
| Scenario: follow-up cannot be delivered to the live running subagent | `AgentTool` rechecks terminal status, resumes if terminal, otherwise raises `ToolError(code=agent_message_not_deliverable)` at `src/agent/platform/tools/builtins/agent.py:475` | `tests/unit/agent/tools/test_agent_tool.py:489` | covered |
| Requirement: follow-up is not silently handled by a second concurrent subagent run | Running accepted path returns directly without `_resume_subagent()` or `subagent_runner.start()` at `src/agent/platform/tools/builtins/agent.py:466` | `tests/integration/background_tasks/test_agent_continuation.py:150` asserts one runtime run | covered |
| Requirement: terminal subagent resume/output_file not regressed | Terminal in-memory and JSONL paths still call `_resume_subagent()` with same `agent_id` and `output_file` at `src/agent/platform/tools/builtins/agent.py:499` and `src/agent/platform/tools/builtins/agent.py:555` | `tests/unit/agent/tools/test_agent_tool.py:527`; `tests/integration/background_tasks/test_agent_continuation.py:153`; background/auto output receipts in `tests/integration/background_tasks/test_agent_background.py:80` and `tests/integration/background_tasks/test_auto_background.py:83` | covered |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| running follow-up 复用 `RunController` live 注入 | 是 | `src/agent/platform/background_tasks/runtime_runner.py:162`; `src/agent/platform/tools/builtins/agent.py:850`; `src/agent/core/agent/run_control.py:76` |
| live 投递不可用时显式失败，不静默另起 subagent | 是 | `src/agent/platform/tools/builtins/agent.py:491` |
| explicit background 与 foreground auto-background 都注册 live message handle | 是 | explicit: `src/agent/platform/tools/builtins/agent.py:316`; auto: `src/agent/platform/tools/builtins/agent.py:413` |
| terminal transitions 清理 message/stop handles | 部分 | transition 内清理存在于 `src/agent/core/background_tasks/registry.py:145`, `src/agent/core/background_tasks/registry.py:161`, `src/agent/core/background_tasks/registry.py:191`;但 handle 注册发生在 runner start 返回之后，见 `src/agent/platform/tools/builtins/agent.py:305` 和 `src/agent/platform/tools/builtins/agent.py:615` |
| 不破坏架构边界 | 是 | 变更只在 `agent.core` / `agent.platform` 内，未引入产品包反向依赖；`platform -> core` 方向保持 |

## Issues

### CRITICAL

- None.

### WARNING

- Terminal cleanup is not race-safe if a subagent runner reaches terminal before handle registration. `complete()` / `fail()` / `kill()` clear live handles during the terminal transition (`src/agent/core/background_tasks/registry.py:145`, `src/agent/core/background_tasks/registry.py:161`, `src/agent/core/background_tasks/registry.py:191`), but explicit/resume launch registers handles only after `subagent_runner.start()` returns (`src/agent/platform/tools/builtins/agent.py:305` then `src/agent/platform/tools/builtins/agent.py:316`; `src/agent/platform/tools/builtins/agent.py:615` then `src/agent/platform/tools/builtins/agent.py:626`). A very fast or synchronously failing runner can therefore re-add `_stop_handles` / `_message_handles` after the record is already terminal. This does not recreate fake `message_queued` because `send_agent_message()` still checks `record.status == RUNNING`, but it violates the design/task requirement that terminal transitions clean live handles. Fix by making `set_stop_handle()` / `set_message_handle()` no-op or return `False` when the record is already terminal, and add a unit test with a runner that calls `on_fail` or `on_complete` before returning its handle.

- The permanent regression suite proves live controller delivery, but the strongest "subagent transcript / next LLM request" proof is only recorded as one-time progress evidence. `tests/integration/background_tasks/test_agent_continuation.py:57` uses a runtime stub that drains `controller.drain_pending()` directly, and `tests/unit/agent/tools/test_agent_tool.py:421` does the same for auto-background. That prevents the old registry-only bug, but it would not fail if `AgentLoop` stopped appending drained pending messages to the actual next LLM request at `src/agent/core/agent/loop.py:316`. The progress note says a temporary live-critical check covered real `AgentRuntime` + `AgentLoop` + second LLM request, but `docs/TESTING_GUIDE.md` treats that as one-time evidence, not permanent regression coverage. Add one durable integration test with a controlled LLM client that asserts the follow-up appears in the second request or persisted subagent transcript.

### SUGGESTION

- None.

# Round 2

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks complete; round 1 2/2 warnings closed |
| Correctness | 5/5 scenarios covered; 0 warnings |
| Coherence | Followed |

All checks passed. Ready for PR.

## Scope

本轮复验 round 1 verifier warnings 与 code review fast-lane 修复是否关闭，重点核对：

- `abort` / `task_stop` 后 running follow-up 不能返回 false `message_queued`。
- `BackgroundSubagentRunner.start()` 契约必须是 stop + `send_message` 的组合 handle。
- terminal 后 setter 不能重插 stale stop/message handles。
- 永久回归测试必须通过真实 `AgentLoop` / LLM request 证明 follow-up 被同一 subagent 消费。

## Completeness

- Tasks: 10/10 complete in `docs/changes/bugfix-450-running-subagent-resume/M1-impl/tasks.md`.
- Round 1 warning "terminal cleanup race": closed. `BackgroundTaskRegistry.set_stop_handle()` and `set_message_handle()` now return `False` and no-op when the record is missing or terminal (`src/agent/core/background_tasks/registry.py:219`, `src/agent/core/background_tasks/registry.py:253`), with regression coverage at `tests/unit/agent/background_tasks/test_background_tasks.py:307`.
- Round 1 warning "true AgentLoop / LLM request permanent regression": closed. `tests/integration/background_tasks/test_agent_continuation.py:107` now constructs real `AgentRuntime` + `AgentLoop` with a controlled LLM client and asserts the follow-up appears in the second LLM request at `tests/integration/background_tasks/test_agent_continuation.py:161`.

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| running subagent follow-up 真实投递 | `AgentTool` only returns `message_queued` after `registry.send_agent_message()` accepts (`src/agent/platform/tools/builtins/agent.py:466`); live handles enqueue via `RunController` (`src/agent/platform/background_tasks/runtime_runner.py:170`, `src/agent/platform/tools/builtins/agent.py:864`) | `tests/integration/background_tasks/test_agent_continuation.py:107` | covered |
| follow-up 在安全点进入同一 subagent 会话 | `AgentLoop` drains controller pending messages before the next LLM request (`src/agent/core/agent/loop.py:316`) | Test asserts two LLM requests and second user messages equal original prompt + follow-up (`tests/integration/background_tasks/test_agent_continuation.py:161`) | covered |
| live delivery 不可用时不返回假 queued | `AgentTool` raises `ToolError(code=agent_message_not_deliverable)` when a running record cannot confirm live delivery (`src/agent/platform/tools/builtins/agent.py:491`) | `tests/unit/agent/tools/test_agent_tool.py:580` | covered |
| `abort` / `task_stop` 后不 false queued | `_ControllerHandle.send_message()` rejects aborted/cancelled/terminal controllers before enqueue (`src/agent/platform/background_tasks/runtime_runner.py:170`, `src/agent/platform/tools/builtins/agent.py:864`) | explicit: `tests/unit/agent/tools/test_agent_tool.py:542`; auto: `tests/unit/agent/tools/test_agent_tool.py:499`; task_stop integration: `tests/integration/background_tasks/test_task_stop.py:217` | covered |
| terminal 后 setter 不重插 stale handles | terminal transitions clear handles (`src/agent/core/background_tasks/registry.py:145`, `src/agent/core/background_tasks/registry.py:161`, `src/agent/core/background_tasks/registry.py:191`); setters reject terminal records (`src/agent/core/background_tasks/registry.py:229`, `src/agent/core/background_tasks/registry.py:260`) | `tests/unit/agent/background_tasks/test_background_tasks.py:307` | covered |
| terminal resume / output_file / background notification 不退化 | terminal in-memory and JSONL resume paths remain (`src/agent/platform/tools/builtins/agent.py:499`, `src/agent/platform/tools/builtins/agent.py:512`); output_file still returned on launch/resume (`src/agent/platform/tools/builtins/agent.py:319`, `src/agent/platform/tools/builtins/agent.py:629`) | `tests/integration/background_tasks` 19 passed | covered |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| running follow-up 复用 `RunController` live 注入，不重建 registry orphan queue | 是 | `src/agent/platform/background_tasks/runtime_runner.py:170`; `src/agent/core/agent/run_control.py:76`; no production `enqueue_agent_message` / `drain_agent_messages` remains |
| live 投递不可用时显式失败，不静默另起 subagent | 是 | `src/agent/platform/tools/builtins/agent.py:491` |
| `BackgroundSubagentRunner.start()` 返回 stop + message handle | 是 | `src/agent/core/background_tasks/interfaces.py:50`; `src/agent/core/background_tasks/interfaces.py:58`; `tests/unit/agent/tools/test_agent_tool.py:192` |
| terminal transitions 清理并拒绝 stale handle reinsertion | 是 | `src/agent/core/background_tasks/registry.py:294`; `tests/unit/agent/background_tasks/test_background_tasks.py:307` |
| 不破坏架构边界 | 是 | 变更保持在 `agent.core` / `agent.platform` 与 tests 内，未引入产品包反向依赖 |

## Issues

### CRITICAL

- None.

### WARNING

- None.

### SUGGESTION

- None.

## Verification Commands

- `pytest -xvs tests/unit/agent/background_tasks/test_background_tasks.py tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py` -> 65 passed.
- `pytest -xvs tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py` -> 12 passed.
- `pytest -xvs tests/integration/background_tasks` -> 19 passed.
- `git diff --check d92218e7..HEAD` -> clean.

# Round 3

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 10/10 tasks complete; round 3 r2 linearization fix verified |
| Correctness | 5/5 scenarios covered; 0 warnings |
| Coherence | Followed |

All checks passed. Ready for PR.

## Scope

本轮复验 fast-lane r2 的 `RunController` enqueue/stop linearization 修复，重点核对：

- `stop()` / abort / cancel / terminal 与 running follow-up enqueue 是否在同一控制面语义中线性化。
- `task_stop` 或 stop 已线性化后，`Agent(agent_id, prompt=...)` 不再返回 false `message_queued`。
- r1/r2 修复未破坏 running follow-up、terminal resume、`output_file`、`task_stop`、后台完成通知和架构边界。

## Completeness

- Tasks: 10/10 complete in `docs/changes/bugfix-450-running-subagent-resume/M1-impl/tasks.md`.
- Round 3 focus covered. `RunController.abort()` and `cancel()` now acquire the same `_terminal_lock` used by `enqueue_message()` (`src/agent/core/agent/run_control.py:61`, `src/agent/core/agent/run_control.py:66`, `src/agent/core/agent/run_control.py:79`), so message acceptance is decided after checking terminal/aborted/cancelled state inside the same critical section.
- The two subagent delivery handles no longer carry stale non-atomic prechecks; both delegate acceptance to `RunController.enqueue_message()` (`src/agent/platform/background_tasks/runtime_runner.py:170`, `src/agent/platform/tools/builtins/agent.py:864`).

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| running subagent follow-up 真实投递 | `AgentTool` returns `message_queued` only after `registry.send_agent_message()` accepts (`src/agent/platform/tools/builtins/agent.py:467`); `registry.send_agent_message()` requires a running subagent record and live handle (`src/agent/core/background_tasks/registry.py:266`) | `tests/integration/background_tasks/test_agent_continuation.py:107` asserts the follow-up appears in the second real LLM request for the same subagent run | covered |
| follow-up 在安全点处理 | `RunController.enqueue_message()` queues accepted messages for round-boundary injection (`src/agent/core/agent/run_control.py:79`); terminal-window handling remains guarded by `_terminal_lock` in `try_commit_terminal()` (`src/agent/core/agent/run_control.py:103`) | `tests/integration/background_tasks/test_agent_continuation.py:161` asserts no second concurrent subagent run and the second request user messages are original prompt + follow-up | covered |
| stop/abort/cancel already linearized rejects follow-up, no false queued | `RunController.enqueue_message()` rejects when `_terminal_committed`, `abort_event`, or `cancel_event` is set under `_terminal_lock` (`src/agent/core/agent/run_control.py:93`); `AgentTool` raises `agent_message_not_deliverable` when accepted is false and record remains running (`src/agent/platform/tools/builtins/agent.py:491`) | `tests/unit/agent/runs/test_run_control_terminal_commit.py:67`, `tests/unit/agent/runs/test_run_control_terminal_commit.py:79`, `tests/unit/agent/tools/test_agent_tool.py:537`, `tests/unit/agent/tools/test_agent_tool.py:597` | covered |
| allowed opposite ordering remains explicit | If enqueue linearizes before abort, the message remains pending; this is intentionally fixed as the opposite ordering, not a false queued-after-stop case | `tests/unit/agent/runs/test_run_control_terminal_commit.py:91` | covered |
| terminal resume / output_file / task_stop not regressed | Terminal in-memory and JSONL resume paths still call `_resume_subagent()` with the same `agent_id` and `output_file` (`src/agent/platform/tools/builtins/agent.py:499`, `src/agent/platform/tools/builtins/agent.py:512`); `task_stop` still routes subagent stop through `registry.request_stop()` and lets worker unwind own terminal (`src/agent/platform/tools/builtins/task_stop.py:134`) | `tests/unit/agent/tools/test_agent_tool.py:614`; `tests/integration/background_tasks/test_agent_continuation.py:170`; `tests/integration/background_tasks/test_task_stop.py:105`; `tests/integration/background_tasks/test_task_stop.py:179` | covered |

## Coherence

| design / architecture decision | 遵守? | 代码证据 |
|---|---|---|
| live follow-up acceptance has one source of truth in `RunController` | 是 | r2 removes duplicated handle guards and delegates to controller enqueue (`src/agent/platform/background_tasks/runtime_runner.py:170`, `src/agent/platform/tools/builtins/agent.py:864`) |
| stop/cancel/terminal and enqueue are linearizable in one control plane | 是 | abort/cancel/enqueue/terminal commit share `_terminal_lock` (`src/agent/core/agent/run_control.py:61`, `src/agent/core/agent/run_control.py:66`, `src/agent/core/agent/run_control.py:93`, `src/agent/core/agent/run_control.py:117`) |
| live delivery unavailable fails explicitly, no second concurrent subagent | 是 | running continuation raises `agent_message_not_deliverable` rather than calling `_resume_subagent()` while record is still running (`src/agent/platform/tools/builtins/agent.py:475`, `src/agent/platform/tools/builtins/agent.py:491`) |
| terminal transitions clean and reject stale handles | 是 | setters reject missing/terminal records (`src/agent/core/background_tasks/registry.py:219`, `src/agent/core/background_tasks/registry.py:253`), terminal transitions clear handles (`src/agent/core/background_tasks/registry.py:145`, `src/agent/core/background_tasks/registry.py:161`, `src/agent/core/background_tasks/registry.py:191`) |
| 不破坏架构边界 | 是 | 变更保持在 `agent.core` / `agent.platform` / tests；contract tests for product/core import boundaries pass |

## Issues

### CRITICAL

- None.

### WARNING

- None.

### SUGGESTION

- None.

## Verification Commands

- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -xvs tests/unit/agent/runs/test_run_control_terminal_commit.py tests/unit/agent/tools/test_agent_tool.py` -> 43 passed.
- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -xvs tests/integration/background_tasks/test_agent_continuation.py tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py tests/integration/background_tasks/test_task_stop.py` -> 20 passed.
- `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -q tests/contract/test_cli_http_only_contract.py tests/contract/test_core_no_platform_imports.py` -> 9 passed.
- `git diff --check 1f489de2..HEAD` -> clean.
