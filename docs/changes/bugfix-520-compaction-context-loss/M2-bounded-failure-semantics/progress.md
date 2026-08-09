# bugfix-520-M2 — Progress

## Baseline

- Context: 从 `origin/unit/bugfix-520` 创建独立 milestone worktree，并完成 Full worker 的上下文读取和基线门禁。
- Evidence:
  - Tests: `PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/pytest -q tests/unit/test_core_errors.py tests/unit/test_loop_compact.py tests/unit/agent/session/test_conversation_session.py tests/unit/agent/runs/test_runs_registry_executor.py tests/unit/agent/test_kernel_manual_compact.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/integration/test_conversation_compaction_integration.py` → `52 passed`。

## Promotion Candidates

None.
