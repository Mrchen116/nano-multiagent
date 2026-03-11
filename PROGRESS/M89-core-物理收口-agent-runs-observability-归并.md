# PROGRESS (Milestone: M89)

- Milestone: M89
- Title: core 物理收口：agent/runs/observability 归并
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M89`
- Branch: `milestone/M89`
- Baseline:
  - Tests: `python3 -m pytest -q`
  - Result: `606 passed, 4 skipped, 246 warnings`
- Notes:
  - authoritative base: `origin/main` commit `028eeed`
  - 目标是将 `src/nano_multiagent` 顶层剩余 `agent/`、`runs/`、`observability/` 彻底物理归并到 `core/`，并同步收口 source/tests/docs/contracts。
  - 迁移后顶层目录只允许 `core/`、`platform/`、`products/`、`apps/`。

## Roadpoints

### R89.1 core target-state contract 先红
- Context:
  - 当前仓库仍保留 `src/nano_multiagent/agent`、`runs`、`observability` 三个真实实现根目录，与《多产品架构调整建议.md》最终目标树不一致。
- Decision:
  - 先把 acceptance / import guard / location tests 改成 M89 口径，再用 focused red batch 暴露物理归并与越层依赖缺口。
- Rationale:
  - 只有先把 contract 改红，才能避免在旧顶层 root 假设上继续修补，确保后续实现严格对齐最终目录树。
- Evidence:
  - Tests: `/Users/czj/miniforge3/bin/python3 -m pytest -q tests/contract/test_multi_product_architecture_acceptance.py tests/contract/test_m85_canonical_wiring_imports.py tests/contract/test_m86_canonical_homing_imports.py tests/contract/test_core_no_platform_imports.py tests/unit/test_core_agent_location.py tests/unit/test_core_runs_location.py tests/unit/test_core_observability_location.py` → `3 errors during collection`（`nano_multiagent.core.agent|runs|observability` 尚未实现）
  - Entry: focused red batch 成功暴露 M89 缺口，证明 contract 已先于实现收口到目标态。
- Rollback:
  - 最近稳定点：`91d61d6`
- Commits: C1=`a2a5c12`, C2=`c13b6d1`, C3=`4d31cb9`
- Next:
  - 已完成。继续推进 Milestone 级 main 集成与派工板更新。

### R89.2 迁移实现并收口 canonical imports
- Context:
  - 待 R89.1 红测固定后，需要物理搬迁代码并移除对旧根包的所有 source/tests/docs 引用。
- Decision:
  - 将顶层 `agent/`、`runs/`、`observability/` 移入 `core/`；同时通过依赖注入/协议抽象消除 core 对 platform 的越层 import。
- Rationale:
  - 仅做路径迁移不足以满足 `core` layering guard；实现与依赖边界需要一次性收口。
- Evidence:
  - Tests: `/Users/czj/miniforge3/bin/python3 -m pytest -q tests/unit/test_agent_state.py tests/unit/test_agent_policies.py tests/unit/test_agent_prompting.py tests/unit/test_agent_loop.py tests/unit/test_agent_runtime.py tests/unit/test_agent_runtime_hooks.py tests/unit/test_agent_runtime_compaction_guardrails.py tests/unit/test_compaction_planner.py tests/unit/test_runs_registry.py tests/unit/test_run_cancel.py tests/unit/test_observability_fields.py tests/contract/test_agent_state_contract.py tests/contract/test_agent_runtime_contract.py tests/contract/test_compaction_contract.py tests/contract/test_observability_contract.py tests/contract/test_runs_async_contract.py tests/contract/test_skill_commands_contract.py tests/contract/test_system_prompt_contract.py tests/integration/test_agent_runtime_integration.py tests/integration/test_runs_store_integration.py tests/integration/test_trace_log_correlation_integration.py tests/integration/test_prompt_runtime_fill_integration.py tests/e2e/test_agent_runtime_e2e.py tests/e2e/test_observability_chain_e2e.py tests/e2e/test_system_prompt_render_e2e.py` → `72 passed, 1 skipped`
  - Entry: `ls src/nano_multiagent` 仅剩 `__init__.py/__pycache__/apps/core/platform/products`，focused M89 contract/location tests `14 passed`。
- Rollback:
  - 最近稳定点：`a2a5c12`
- Commits: C1=`a2a5c12`, C2=`c13b6d1`, C3=`4d31cb9`
- Next:
  - 已完成。等待 Milestone 级全量验证与 main 集成。

### R89.3 full sweep、live 验证、main 集成与清理
- Context:
  - 待 focused green 后，需要补全全量/ live 证据并完成 main 集成、board 更新与 worktree 清理。
- Decision:
  - 先回写最终证据链，再做 main merge/push、`data/dev-tasks.json` 更新与 worktree 清理。
- Rationale:
  - 先固化证据与回滚点，避免 main 集成后再补文档导致哈希、命令和结论漂移。
- Evidence:
  - Tests: `python3 -m pytest -q` → `606 passed, 4 skipped, 246 warnings`
  - Entry: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py` → `1 passed`；`NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py` → `1 passed`。
- Rollback:
  - 最近稳定点：`c13b6d1`
- Commits: C1=`a2a5c12`, C2=`c13b6d1`, C3=`4d31cb9`
- Next:
  - 执行 main 集成、board 更新与 worktree 清理。
