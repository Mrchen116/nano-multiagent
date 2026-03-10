# TASKS (Milestone: M86)

- Title: 多产品架构重构十三期：apps/platform 真实实现物理归位
- Goal: 把 `apps/coding_cli` 与 `platform/llm/providers` 变成真实实现归属地，并把剩余 substantive code 从 `cli/llm/session/hooks/tools` legacy 树迁到 canonical home，仅保留 compatibility shim。
- Exit Criteria:
  - `src/nano_multiagent/apps/coding_cli/**` 持有真实 CLI 实现；legacy `src/nano_multiagent/cli/**` 仅保留 thin compatibility surface。
  - `src/nano_multiagent/platform/llm/providers/**` 持有真实 provider 实现；legacy `src/nano_multiagent/llm/**` 仅保留 thin compatibility surface。
  - `session/hooks/tools` legacy 树不再持有剩余 substantive code；canonical home 明确且测试固化。
  - focused tests、full sweep、相关 live tests 全绿，并把命令/结果与 C1/C2/C3 记录到 `PROGRESS`。
  - 成功 merge `milestone/M86` -> `main`、必要时 push、更新 `data/dev-tasks.json` 为 `DONE`，并移除 M86 worktree。
- Baseline Test Command: `python3 -m pytest -q`
- Baseline Result: 初始 rerun 在 collection 阶段失败，根因是 `platform/hooks/session_usage.py` 误导入不存在的 `platform.hooks.registry`；修复后继续纳入本 milestone scope。
- Branch: `milestone/M86`
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M86`

## R86.1 apps/platform canonical ownership contracts 先红
- Status: DONE
- Acceptance:
  - 新增/更新 location 与 import-guard tests，明确 `apps/coding_cli`、`platform/llm/providers`、`platform/persistence/session`、`platform/hooks`、`platform/tools` 的 canonical ownership。
  - 证明 legacy `cli/llm/session/hooks/tools` 仅作为 compatibility shim 暴露同一对象。
- Tests Plan:
  - unit: `tests/unit/test_apps_coding_cli_location.py`
  - unit: `tests/unit/test_platform_llm_providers_location.py`
  - unit: `tests/unit/test_platform_tools_location.py`
  - unit: `tests/unit/test_platform_hooks_location.py`
  - unit/新增: session canonical location tests
  - contract/新增: M86 import-guard
- DoD:
  - focused tests 先红后绿
  - `PROGRESS` 记录 Context/Decision/Rationale/Evidence/Rollback/Commits/Next
- Evidence:
  - `python3 -m pytest -q tests/unit/test_apps_coding_cli_location.py tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_session_support_location.py tests/contract/test_m86_canonical_homing_imports.py` -> `18 passed in 0.27s`
  - 已新增 session canonical ownership 与 import-guard，锁定 apps/platform canonical home 与 legacy shim 身份一致性。

## R86.2 真实实现迁移与 legacy shim 收口
- Status: DONE
- Acceptance:
  - CLI 真实实现物理迁到 `apps/coding_cli` canonical 目录。
  - provider/translator 与 session/hook/tool 剩余 substantive modules 迁到 platform canonical 目录。
  - active layers 不再内部依赖 legacy `cli/llm/session/hooks/tools` 实现路径。
- Tests Plan:
  - focused unit/contract/integration affected set
  - 必要时补 location + import-guard tests
- DoD:
  - focused red -> green
  - C1/C2/C3 齐全
- Evidence:
  - `python3 -m pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_session_service.py tests/integration/test_cli_http_flow_integration.py` -> `116 passed, 46 warnings in 8.90s`
  - canonical `apps/coding_cli`、`platform/llm/providers`、`platform/persistence/session`、`platform/hooks`、`platform/tools` 已持有真实实现，legacy 树收口为 compatibility alias/shim。

## R86.3 全量门禁、live 验证、集成与清理
- Status: DOING
- Acceptance:
  - `python3 -m pytest -q` 全绿。
  - milestone relevant live tests 全绿或明确记录不支持/阻塞。
  - `milestone/M86` 成功 merge 到 `main` 并 push（如需要）。
  - `data/dev-tasks.json` 更新为 `DONE`，记录结果 JSON。
  - 移除 `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M86`。
- Expected Tests:
  - `python3 -m pytest -q`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py`
- DoD:
  - 所有命令/结果记录进 `PROGRESS`
  - merge / push / board / worktree cleanup 全完成
- Evidence so far:
  - `python3 -m pytest -q` -> `605 passed, 4 skipped, 246 warnings in 23.76s`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py` -> `1 passed in 4.09s`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py` -> `1 passed in 6.20s`
- Remaining:
  - merge `milestone/M86` -> `main`
  - push `main`
  - 更新 `data/dev-tasks.json`
  - 移除 M86 worktree
