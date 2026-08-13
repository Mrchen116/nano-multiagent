# bugfix-536-M1 — Progress

## Baseline

- Context: M1 是父 run liveness、Kernel handoff、Gateway owner 和 delivery context 的单一垂直切片。
- Evidence:
  - Tests: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/test_loop_compact.py tests/unit/agent/runs/test_run_control_pending_origin.py tests/contract/test_kernel_sdk_behavior_contract.py tests/unit/personal_assistant/test_session_run_coordinator_admission.py tests/unit/personal_assistant/test_session_run_coordinator_terminal.py tests/unit/personal_assistant/test_session_run_coordinator_steer_identity.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/integration/test_session_run_coordinator_real_kernel.py` — 123 passed in 6.01s.
  - Entry: baseline 仅确认现状套件稳定；事故恢复能力尚未实现。

## R1 — 父 run liveness 与 Kernel recovery protocol

- Status: TODO

## R2 — Gateway recovery ledger 与 delivery adoption

- Status: TODO

## R3 — 跨层入口回归与交付门禁

- Status: TODO

## Promotion Candidates

None.
