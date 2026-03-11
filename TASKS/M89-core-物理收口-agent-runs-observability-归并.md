# TASKS (Milestone: M89)

- Title: core 物理收口：agent/runs/observability 归并
- Goal: 将 `src/nano_multiagent` 顶层剩余的 `agent`、`runs`、`observability` 物理归并到 `core/` 下，并让源码、tests、docs、contracts 全面切到 `core/agent`、`core/runs`、`core/observability` canonical homes。
- Exit Criteria:
  - `src/nano_multiagent` 顶层仅剩 `core/`、`platform/`、`products/`、`apps/`。
  - `core/agent/`、`core/runs/`、`core/observability/` 的实现全部迁入 `core/agent/`、`core/runs/`、`core/observability/`。
  - source / tests / docs / contracts 不再依赖 legacy `nano_multiagent.agent|runs|observability` 根包。
  - architecture acceptance / import guards / location tests 更新到 M89 口径并通过。
  - focused tests、`python3 -m pytest -q` 全绿；milestone-relevant live tests 通过，或在 `PROGRESS` 中明确记录阻塞。
  - 成功 merge `milestone/M89` -> `main`、必要时 push、更新 `data/dev-tasks.json` 为 `DONE`，并移除 M89 worktree。
- Baseline Test Command: `python3 -m pytest -q`
- Baseline Result: `606 passed, 4 skipped, 246 warnings`
- Branch: `milestone/M89`
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M89`

## R89.1 core target-state contract 先红
- Status: DONE
- Acceptance:
  - 将 architecture acceptance / import guards / location tests 改写为 M89 目标态：顶层只能剩 `core/platform/products/apps`，canonical home 需包含 `core/agent`、`core/runs`、`core/observability`。
  - 新增或改写 focused tests，明确 legacy `nano_multiagent.agent|runs|observability` 必须物理移除且不可 import。
  - 建立 M89 的 TASKS/PROGRESS 证据链并记录红测结果。
- Tests Plan:
  - contract：改写 `tests/contract/test_multi_product_architecture_acceptance.py`、`tests/contract/test_m85_canonical_wiring_imports.py`、`tests/contract/test_m86_canonical_homing_imports.py`。
  - unit：补齐/改写 core location tests，覆盖 `core.agent`、`core.runs`、`core.observability` canonical ownership。
  - integration/e2e：本 Roadpoint 不跑，先稳定暴露目录/导入层差距。
- Expected Tests:
  - `python3 -m pytest -q tests/contract/test_multi_product_architecture_acceptance.py tests/contract/test_m85_canonical_wiring_imports.py tests/contract/test_m86_canonical_homing_imports.py tests/contract/test_core_no_platform_imports.py tests/unit/test_core_agent_location.py tests/unit/test_core_runs_location.py tests/unit/test_core_observability_location.py`
- DoD:
  - 红测证据写入 `PROGRESS/M89-*.md`
  - C1 为真实 commit hash

## R89.2 迁移实现并收口 canonical imports
- Status: DONE
- Acceptance:
  - 物理迁移 `core/agent/`、`core/runs/`、`core/observability/` 到 `core/` 下。
  - source / tests / docs / contracts 全量改到 canonical core paths。
  - 移除 core 内对 platform 的越层依赖，使 `tests/contract/test_core_no_platform_imports.py` 保持成立。
- Tests Plan:
  - unit/contract：回归 core location、prompt/runtime/runs/observability 相关门禁。
  - integration/e2e：覆盖 runtime、runs、observability、HTTP API 关键链路，确认迁移后真实功能仍工作。
- Expected Tests:
  - `python3 -m pytest -q tests/unit/test_agent_state.py tests/unit/test_agent_policies.py tests/unit/test_agent_prompting.py tests/unit/test_agent_loop.py tests/unit/test_agent_runtime.py tests/unit/test_agent_runtime_hooks.py tests/unit/test_agent_runtime_compaction_guardrails.py tests/unit/test_compaction_planner.py tests/unit/test_runs_registry.py tests/unit/test_run_cancel.py tests/unit/test_observability_fields.py tests/contract/test_agent_state_contract.py tests/contract/test_agent_runtime_contract.py tests/contract/test_compaction_contract.py tests/contract/test_observability_contract.py tests/contract/test_runs_async_contract.py tests/contract/test_skill_commands_contract.py tests/contract/test_system_prompt_contract.py tests/integration/test_agent_runtime_integration.py tests/integration/test_runs_store_integration.py tests/integration/test_trace_log_correlation_integration.py tests/integration/test_prompt_runtime_fill_integration.py tests/e2e/test_agent_runtime_e2e.py tests/e2e/test_observability_chain_e2e.py tests/e2e/test_system_prompt_render_e2e.py`
- DoD:
  - focused tests 全绿
  - `src/nano_multiagent` 顶层只剩目标目录
  - C2 为真实 commit hash

## R89.3 full sweep、live 验证、main 集成与清理
- Status: DONE
- Acceptance:
  - `python3 -m pytest -q` 全绿。
  - milestone-relevant live tests 全绿，或明确记录不支持/阻塞。
  - `milestone/M89` 成功 merge 到 `main` 并 push（如需要）。
  - `data/dev-tasks.json` 更新为 `DONE`，记录 result JSON。
  - 移除 `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M89`。
- Tests Plan:
  - authoritative：`python3 -m pytest -q`
  - live：优先跑现有 Anthropic live e2e，如环境支持则保留实跑证据。
  - release：main 集成前后核对状态，避免 merge 漂移。
- Expected Tests:
  - `python3 -m pytest -q`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py`
- DoD:
  - 全量与 live 命令/结果记录进 `PROGRESS`
  - C3 为真实 commit hash
  - merge / push / board / cleanup 全完成
