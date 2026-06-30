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
