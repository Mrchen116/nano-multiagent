# TASKS (Milestone: M87)

- Title: 多产品架构重构十四期：legacy shim 截肢与最小兼容面验收
- Goal: 删除低价值 legacy families，收缩 surviving compat surface 到真正有外部价值的最小集合，并重写 acceptance 合同。
- Exit Criteria:
  - 低价值 legacy shim family 被删除：重点包含 `server` 的内部子模块/路由 shim 与 `cli` 的内部 helper/subpackage shim。
  - 仍保留的 compatibility surface 仅限真正具有外部价值的入口，并由 acceptance/architecture doc 明确列出。
  - multi-product architecture acceptance contract 改写为 M87 最小兼容面口径；canonical ownership / location guards 保持一致。
  - focused tests、`python3 -m pytest -q` 全绿，相关 live tests 通过或在 `PROGRESS` 里明确记录不支持/阻塞。
  - 成功 merge `milestone/M87` -> `main`、必要时 push、更新 `data/dev-tasks.json` 为 `DONE`，并移除 M87 worktree。
- Baseline Test Command: `python3 -m pytest -q`
- Baseline Result: 待执行；以当前 `origin/main` 基线（commit `9584577`）为 authoritative base。
- Branch: `milestone/M87`
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M87`

## R87.1 最小 legacy surface contract 先红
- Status: DONE
- Acceptance:
  - 重写 acceptance contract 与 architecture doc，使其显式列出 M87 后仍保留的最小兼容面。
  - 先用红测锁定应删除的低价值 shim：`server` 内部子模块/路由 shim、`cli` 内部 helper/subpackage shim。
- Tests Plan:
  - contract: `tests/contract/test_multi_product_architecture_acceptance.py`
  - unit/location: `tests/unit/test_platform_http_api_location.py`
  - unit/location: `tests/unit/test_apps_coding_cli_location.py`
- DoD:
  - focused tests 先红后绿
  - `PROGRESS` 记录 Context/Decision/Rationale/Evidence/Rollback/Commits/Next

## R87.2 删除低价值 shim family 并切回 canonical imports
- Status: DONE
- Acceptance:
  - 删除 `server` 内部 compat 子模块与 `cli` 内部 helper/subpackage compat 子模块。
  - repo 内部测试/文档/实现改用 canonical `platform/http_api` 与 `apps/coding_cli` 路径。
  - 如仍保留 legacy shim，必须证明其 external value，并保持为极薄 re-export/alias。
- Tests Plan:
  - focused affected unit/integration/contract set
  - 受影响 README / architecture acceptance 回归
- DoD:
  - 删除后的 imports 全部稳定
  - C1/C2/C3 齐全

## R87.3 全量门禁、live 验证、集成与清理
- Status: DOING
- Acceptance:
  - `python3 -m pytest -q` 全绿。
  - milestone relevant live tests 全绿或明确记录不支持/阻塞。
  - `milestone/M87` 成功 merge 到 `main` 并 push（如需要）。
  - `data/dev-tasks.json` 更新为 `DONE`，记录结果 JSON。
  - 移除 `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M87`。
- Expected Tests:
  - `python3 -m pytest -q`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py`
- DoD:
  - 所有命令/结果记录进 `PROGRESS`
  - merge / push / board / worktree cleanup 全完成
