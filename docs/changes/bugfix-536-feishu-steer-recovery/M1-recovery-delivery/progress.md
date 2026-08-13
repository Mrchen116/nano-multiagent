# bugfix-536-M1 — Progress

## Baseline

- Context: M1 是父 run liveness、Kernel handoff、Gateway owner 和 delivery context 的单一垂直切片。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/test_loop_compact.py tests/unit/agent/runs/test_run_control_pending_origin.py tests/contract/test_kernel_sdk_behavior_contract.py tests/unit/personal_assistant/test_session_run_coordinator_admission.py tests/unit/personal_assistant/test_session_run_coordinator_terminal.py tests/unit/personal_assistant/test_session_run_coordinator_steer_identity.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/integration/test_session_run_coordinator_real_kernel.py` — 123 passed in 6.01s.
  - Entry: baseline 仅确认现状套件稳定；事故恢复能力尚未实现。

## R1 — 父 run liveness 与 Kernel recovery protocol

- Context: 自动 compaction summarizer 是父 run 的合法静默 await；Registry 是 pending admission、contiguous origin batch 与 successor closure 的唯一事实 owner。
- Decision: 为每条 accepted pending 分配 Kernel-owned opaque id；`RunInfo` 只在 successful steer 暴露该 id；continuation queued status 携带 recovery/predecessor/batch/origin/pending ids，随后发布一次 `recovery_settled`。parent compaction await 复用既有 ticker，source=`compaction`。
- Rationale: Gateway 可从 SDK stream 精确关联 follower，无需按时间、active id 或 origin 猜测；sidechain publisher 保持不变，摘要内容不泄漏。
- Evidence:
  - Tests: focused red 分别因缺少 `liveness_ticker` call site、`PendingMessage.pending_id`、`RunInfo.pending_id` 和 settlement 失败；green 后 `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/test_loop_compact.py tests/unit/agent/runs/test_run_control_pending_origin.py tests/unit/agent/runs/test_run_control_terminal_commit.py tests/unit/agent/runs/test_runs_registry_executor.py tests/contract/test_kernel_sdk_behavior_contract.py tests/contract/test_agent_sdk_surface_contract.py` — 73 passed in 3.77s。
  - Entry: SDK contract 真实 build Kernel，验证 old terminal 在先、三段 user/background/user successor descriptor 顺序和一次 scheduled settlement。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/contract/test_kernel_sdk_behavior_contract.py::test_non_user_terminal_publishes_correlated_recovery_protocol`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Debug note: 首轮测试在 cancel 后误打开 provider gate，使 pending 被同 run 正常消费；事件证据包含 `injection_consumed` 而无 settlement。按 systematic-debugging 反向定位后确认产品实现无异常，修正测试条件为真 cancel-before-consume；没有用 sleep/重试掩盖。
- Rollback: 回退本 R commit。
- Commits: pending。
- Next: R2 Gateway ledger 与 typed adoption。

## R2 — Gateway recovery ledger 与 delivery adoption

- Status: TODO

## R3 — 跨层入口回归与交付门禁

- Status: TODO

## Promotion Candidates

None.
