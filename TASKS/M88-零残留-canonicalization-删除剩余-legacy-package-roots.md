# TASKS (Milestone: M88)

- Title: 零残留 canonicalization：删除剩余 legacy package roots
- Goal: 删除 `src/nano_multiagent` 下剩余 legacy package roots，统一切到 `core/platform/products/apps` canonical imports 与 entrypoints，并让 tests/docs/acceptance contract 同步转向零残留目标态。
- Exit Criteria:
  - `src/nano_multiagent` 下不再存在 legacy package roots。
  - 源码、tests、README/架构文档/相关 SPEC 不再依赖 legacy imports 或 legacy entrypoints。
  - multi-product architecture acceptance contract 改写为 zero-residue 口径，并核对 canonical target tree。
  - focused tests、`python3 -m pytest -q` 全绿；相关 live tests 通过，或在 `PROGRESS` 中明确记录阻塞。
  - 成功 merge `milestone/M88` -> `main`、必要时 push、更新 `data/dev-tasks.json` 为 `DONE`，并移除 M88 worktree。
- Baseline Test Command: `python3 -m pytest -q`
- Baseline Result: `python3 -m pytest -q` 当前红灯（9 failed, 596 passed, 4 skipped）；现有失败集中在 `tests/unit/test_cli_main.py` 与 `tests/integration/test_cli_http_flow_integration.py` 仍引用已移除的 `nano_multiagent.cli.app|events|input` layered legacy paths，属于 M88 scope（authoritative base: `origin/main` @ `d912bb7`）
- Branch: `milestone/M88`
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M88`

## R88.1 zero-residue contract 先红
- Status: TODO
- Acceptance:
  - 改写 acceptance/location/import-guard 测试，明确 zero-residue 目标：legacy root dirs 必须物理消失，canonical home 仅允许 `core/platform/products/apps`。
  - README / architecture doc / 相关 SPEC 文档新增 M88 零残留口径并先触发红测。
- Tests Plan:
  - unit：改写 location tests 与 CLI 边界用例，统一断言 canonical homes 暴露正常且 legacy roots 已不存在。
  - contract：把 architecture/import-guard contract 改写为 zero-residue 口径，并让文档勾稽在红测阶段直接暴露差距。
  - integration：保留一个 CLI history barrier 真实入口用例作为红测证据，确认仓内仍有 layered legacy path 残留引用。
  - e2e：本 Roadpoint 不跑；先完成 contract/location/import guard 口径改写。
- Expected Tests:
  - `python3 -m pytest -q tests/contract/test_multi_product_architecture_acceptance.py tests/contract/test_m85_canonical_wiring_imports.py tests/contract/test_m86_canonical_homing_imports.py tests/unit/test_platform_http_api_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_core_llm_location.py tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_session_support_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_core_skills_location.py`
- DoD:
  - 红测证据记录进 `PROGRESS/M88-*.md`
  - C1 为真实 commit hash

## R88.2 迁移 source/tests/docs 并物理删除 legacy roots
- Status: TODO
- Acceptance:
  - source/test/doc imports 全部改到 canonical home。
  - 剩余真实实现物理搬迁完成，`src/nano_multiagent` 不再保留 legacy roots。
  - focused tests 转绿。
- Tests Plan:
  - unit：迁移 agent/runtime/prompting/sdk/skills 等直接 legacy imports，并同步改写对应 unit tests 到 canonical imports。
  - contract：保留 R88.1 的 zero-residue contract，增加 provider/tool/session 相关 contract 作为回归门禁。
  - integration：覆盖 agent runtime / CLI / tools / hooks / session 主链路，确认迁移后真实入口不再依赖 legacy 包。
  - e2e：本 Roadpoint 仍不跑 live；仅在 focused green 阶段保留离线 e2e/contract/unit 组合。
- Expected Tests:
  - `python3 -m pytest -q tests/contract/test_multi_product_architecture_acceptance.py tests/contract/test_m85_canonical_wiring_imports.py tests/contract/test_m86_canonical_homing_imports.py tests/unit/test_platform_http_api_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_core_llm_location.py tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_session_support_location.py tests/unit/test_platform_sdk_location.py tests/unit/test_core_skills_location.py`
  - `python3 -m pytest -q tests/unit/test_agent_runtime.py tests/unit/test_agent_loop.py tests/unit/test_agent_prompting.py tests/unit/test_sdk_client.py tests/contract/test_llm_provider_contract.py`
- DoD:
  - focused tests 全绿
  - legacy roots 物理删除完成
  - C2 为真实 commit hash

## R88.3 full sweep、live 验证、main 集成与清理
- Status: TODO
- Acceptance:
  - `python3 -m pytest -q` 全绿。
  - milestone-relevant live tests 全绿，或明确记录不支持/阻塞。
  - `milestone/M88` 成功 merge 到 `main` 并 push（如需要）。
  - `data/dev-tasks.json` 更新为 `DONE`，记录结果 JSON。
  - 移除 `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M88`。
- Tests Plan:
  - unit/contract/integration：直接跑 `python3 -m pytest -q` 作为 authoritative 全量门禁。
  - e2e：补跑 milestone relevant live tests，若环境不支持则在 `PROGRESS` 记录阻塞与责任边界。
  - release/integration：main 集成前后各保留一次全绿证据，防止 rebase/merge 引入回归。
- Expected Tests:
  - `python3 -m pytest -q`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py`
- DoD:
  - 全量与 live 命令/结果记录进 `PROGRESS`
  - C3 为真实 commit hash
  - merge / push / board / cleanup 全完成
