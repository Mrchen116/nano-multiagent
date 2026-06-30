# bugfix-450-M1 — Progress

## R1 — live subagent follow-up delivery

- Context: running subagent continuation 旧实现只写 `BackgroundTaskRegistry` 的 orphan pending-list，然后返回 `message_queued`；生产 `AgentRuntime` / `AgentLoop` 从不消费该 list，导致用户看到成功但 subagent 实际没收到 follow-up。
- Decision: 新增 `BackgroundSubagentMessageHandle` 协议和 registry `_message_handles`；explicit background、terminal resume、foreground auto-background 均注册 controller-backed `_ControllerHandle`；running continuation 改为调用 `registry.send_agent_message()`，只在 live `RunController.enqueue_message()` 接受后返回 `message_queued`。如果 live delivery 不可用且 record 仍 running，则抛 `ToolError(code=agent_message_not_deliverable)`；如果竞态后 record 已 terminal，则走原 terminal resume。
- Rationale: `RunController` / `AgentLoop.drain_pending()` 已经是中途安全点注入的唯一成熟链路，具备 FIFO、terminal window 和不中断工具/LLM stream 的语义。继续保留 registry pending-list 会重新制造无人消费队列；静默新开第二个 subagent 会丢失原 worker 上下文。
- Evidence:
  - Tests:
    - Red: `pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py` 在 C1 后失败，`test_continuation_to_running_agent_without_live_delivery_fails` 未抛 `ToolError`，`test_running_agent_follow_up_enters_live_runtime_controller` 的 result_text 为 `subagent consumed: missing follow-up`。
    - Green: `pytest -xvs tests/unit/agent/background_tasks/test_background_tasks.py tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py` → 61 passed。
    - Regression: `pytest -xvs tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py` → 12 passed。
  - Entry: 临时 live-critical 等价入口验收使用真实 `AgentRuntime` + `RunsRegistry` + `RuntimeRunner` + `AgentTool`，只替换 LLM client 为可控阻塞流式 client。步骤：启动 background subagent → 等第一轮 LLM request 卡住 → `Agent(agent_id, prompt="FOLLOWUP: report visible status")` → 释放第一轮 → 真实 `AgentLoop.try_commit_terminal()` 消费 pending follow-up 并发起第二次 LLM request。输出摘要：`follow_up_status=message_queued`，`terminal_status=completed`，`result_text="VISIBLE FOLLOWUP RECEIVED: report visible status"`，第二次 LLM request 的 user messages 为原 prompt + `FOLLOWUP: report visible status`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: 永久回归在 `tests/integration/background_tasks/test_agent_continuation.py::test_running_agent_follow_up_enters_live_runtime_controller` 覆盖 explicit background runtime 消费链路；`tests/unit/agent/tools/test_agent_tool.py::test_foreground_auto_background_running_follow_up_uses_live_controller` 覆盖 foreground auto-background；`test_continuation_to_running_agent_without_live_delivery_fails` 覆盖 live delivery 不可用显式失败；`test_registry_terminal_transition_disables_live_message_delivery` 覆盖 terminal cleanup。
  - Visual/Interaction: N/A。
- Debugging notes: 临时 live-critical 验收第一次失败于 `model registry not initialized`，根因为脚本直接构造 `AgentRuntime` 而没有 pytest `conftest.py` / `build_kernel` 初始化全局 model registry；补充同测试配置等价的最小 `init_model_registry()` 后同一路径通过。
- Rollback: 回退 C2 `94cb83fa` 会恢复旧假 queued 行为；C1 `df52bc01` 保留复现红测。
- Commits: C1=`df52bc01`, C2=`94cb83fa`, C3=`0e820df9`
- Next: 本 milestone 已完成，已合入并 push 到 `unit/bugfix-450`。

### Fast-lane fix r1 — reviewer/code-review feedback loop

- Context: reviewer/verifier 已 pass，但 code review 确认 4 个需要修复的控制面问题：task_stop/abort 后仍可能 false queued、runner `start()` 契约仍是 stop-only、terminal 后 setter 可重插 stale handle、integration 永久回归仍靠 stub 直接 `controller.drain_pending()`。
- Decision: 走 fast-lane 小修，不新建 milestone 目录，不改 design/incident/delta spec；直接在 M1 原范围内补架构正确位置的契约、生命周期 guard 和永久回归。
- Rationale: 这四项都属于 M1 live follow-up delivery 的同一控制面闭环，修复点落在既有 `RunController` handle、`BackgroundTaskRegistry` 和现有回归测试，不需要扩大设计。
- Evidence:
  - Tests:
    - `pytest -xvs tests/unit/agent/background_tasks/test_background_tasks.py tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py` -> 65 passed。
    - `pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py` -> 35 passed。
    - `pytest -xvs tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py` -> 12 passed。
    - `git diff --check` -> clean。
  - Entry: backend/runtime control-plane only；真实入口等价永久回归已固化到 `tests/integration/background_tasks/test_agent_continuation.py::test_running_agent_follow_up_enters_live_runtime_controller`，使用真实 `AgentRuntime` + `AgentLoop` + `RuntimeRunner` + controlled LLM，断言 follow-up 出现在第二次真实 LLM request 的 user messages：`["Take your time.", "Also check the tests."]`，并且原 subagent result 为 `VISIBLE FOLLOWUP RECEIVED: Also check the tests.`。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression:
    - 问题 1: `test_explicit_background_stopped_agent_rejects_follow_up_without_false_queued` 与 `test_auto_background_stopped_agent_rejects_follow_up_without_false_queued` 覆盖 explicit background/resumed 与 auto-background controller handle 在 `stop()/abort()` 后拒绝 follow-up，AgentTool 抛 `agent_message_not_deliverable`，不返回 `message_queued`。
    - 问题 2: 新增 `BackgroundSubagentHandle` 组合 Protocol，`BackgroundSubagentRunner.start()` 返回 stop+send_message handle；`test_subagent_runner_start_returns_stop_and_message_handle_contract` 固定契约，fake/no-op runner 同步实现 `send_message()`。
    - 问题 3: registry `set_stop_handle()` / `set_message_handle()` 在 missing/terminal record 上返回 False 且 no-op；`test_terminal_record_rejects_late_handle_reinsertion` 证明 terminal 后不能重插 stale stop/message handle。
    - 问题 4: integration 测试删除直接 drain stub，改用真实 runtime loop 观察第二次 LLM request，永久证明 pending follow-up 会被下一轮真实 LLM request 消费。
  - Visual/Interaction: N/A。
- Rollback: 回退 code commit `7f9dadaf` 可恢复到 verifier pass 后状态。
- Commits: fix=`7f9dadaf`, docs=`3a94059e`, merge=`8ce9e54f`
- Next: 已合入并 push 到 `unit/bugfix-450`。

### Fast-lane fix r2 — RunController enqueue/stop linearization

- Context: r1 的 `_ControllerHandle.send_message()` 在 handle 层先检查 `is_aborted/is_cancelled/is_terminal_committed`，再调用 `RunController.enqueue_message()`；该检查与 `stop()->controller.abort()` 不在同一临界区，并发下 stop 已线性化后仍可能 enqueue 成功，导致 AgentTool 返回 false `message_queued`。
- Decision: 在 `RunController` 控制面收敛线性化语义：`abort()` / `cancel()` 与 `enqueue_message()` 共用 `_terminal_lock`；`enqueue_message()` 在同一锁内检查 terminal/aborted/cancelled 后再决定是否入队。两个 `_ControllerHandle.send_message()` 删除重复非原子 guard，只调用 controller 的原子语义。
- Rationale: live follow-up acceptance 的单一真源应在 `RunController`，因为它已经负责 terminal commit 与 enqueue 的互斥。继续在 handle 层贴 guard 会保留 TOCTOU window，并让 explicit background 与 auto-background 两处重复控制面逻辑。
- Evidence:
  - Tests:
    - Red: `pytest -xvs tests/unit/agent/runs/test_run_control_terminal_commit.py tests/unit/agent/tools/test_agent_tool.py::test_auto_background_handle_rejects_message_when_stop_linearizes_during_enqueue tests/unit/agent/tools/test_agent_tool.py::test_explicit_background_handle_rejects_message_when_stop_linearizes_during_enqueue` 在修复前失败于 `test_enqueue_after_abort_is_rejected`：abort 后 enqueue 仍返回 True。
    - Green narrow: `pytest -xvs tests/unit/agent/runs/test_run_control_terminal_commit.py tests/unit/agent/tools/test_agent_tool.py` -> 43 passed。
    - M1 required: `pytest -xvs tests/unit/agent/tools/test_agent_tool.py tests/integration/background_tasks/test_agent_continuation.py` -> 37 passed。
    - M1 required: `pytest -xvs tests/integration/background_tasks/test_agent_background.py tests/integration/background_tasks/test_auto_background.py tests/unit/agent/tools/test_task_stop_tool.py` -> 12 passed。
    - `git diff --check` -> clean。
  - Entry: backend/runtime control-plane only；用户可见入口仍由 `AgentTool` running continuation 返回值体现。`RunController.enqueue_message()` 现在在 stop/cancel 已线性化后返回 False，AgentTool 经 registry 得到 `agent_message_not_deliverable`，不再报告 queued。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression:
    - `test_enqueue_after_abort_is_rejected` / `test_enqueue_after_cancel_is_rejected` 固定 controller 层 active 判断。
    - `test_message_accepted_before_abort_remains_pending` 固定允许的相反线性化方向：enqueue 先发生则保留 True。
    - `test_auto_background_handle_rejects_message_when_stop_linearizes_during_enqueue` 与 `test_explicit_background_handle_rejects_message_when_stop_linearizes_during_enqueue` 覆盖两个 handle 不再因非原子 guard 误 accepted。
  - Visual/Interaction: N/A。
- Rollback: 回退 code commit `0b3e56c2` 会恢复 r1 的非原子 handle guard。
- Commits: fix=`0b3e56c2`
- Next: 已准备 rebase/merge 到 `unit/bugfix-450`。
