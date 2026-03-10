# PROGRESS (Milestone: M86)

- Milestone: M86
- Title: 多产品架构重构十三期：apps/platform 真实实现物理归位
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M86`
- Branch: `milestone/M86`
- Baseline:
  - Tests: `python3 -m pytest -q`
  - Result: 初始 rerun 在 collection 阶段失败，根因是 `src/nano_multiagent/platform/hooks/session_usage.py` 误导入不存在的 `nano_multiagent.platform.hooks.registry`；修复后纳入本 milestone scope 并继续推进。
- Notes:
  - 本次 rerun 以 `origin/main` commit `9c00283` 为 authoritative base，已包含 M85。
  - 目标是让 canonical home 真正持有实现，而不是继续由 legacy 路径反向承载 substantive code。

## Roadpoints

### R86.1 apps/platform canonical ownership contracts 先红
- Context:
  - `apps/coding_cli` 仍通过 `cli/*` 承载真实 CLI 逻辑；`platform/llm/providers` 仍反向 re-export `llm/providers`。
  - `session.service`、`session.serializers`、`hooks.session_events`、`hooks.session_usage`、`tools.base/constants/registry` 仍有剩余 substantive code 落在 legacy 树。
- Decision:
  - 先补 location/import-guard tests，锁定 canonical home 与 legacy shim 关系，再做物理迁移。
- Rationale:
  - milestone 的关键不是“还能 import”，而是“真实实现归属地”要与 architecture intent 一致，并由测试防回流。
- Evidence:
  - Tests: `python3 -m pytest -q tests/unit/test_apps_coding_cli_location.py tests/unit/test_platform_llm_providers_location.py tests/unit/test_platform_tools_location.py tests/unit/test_platform_hooks_location.py tests/unit/test_platform_session_support_location.py tests/contract/test_m86_canonical_homing_imports.py` -> `18 passed in 0.27s`
  - Entry: ownership/import-guard 已锁定 apps/platform canonical home；legacy `cli/llm/session/hooks/tools` 只允许作为 compatibility shim 暴露同一对象。
- Rollback:
  - 最近稳定点：`9c00283`
- Commits: C1=`347fb55138e9`, C2=`pending`, C3=`pending`
- Next:
  - 执行 R86.2，把真实实现迁入 canonical 目录并收口 legacy facade。

### R86.2 真实实现迁移与 legacy shim 收口
- Context:
  - canonical path 已存在，但多个模块仍只是 facade/shim，真正实现还在 legacy 路径。
- Decision:
  - 把 CLI/provider/session/hooks/tools 的剩余 substantive code 迁到 apps/platform canonical 目录，并把 legacy 文件统一改成 thin shim；对仍需保持 monkeypatch/identity 兼容的 facade，一律使用 `sys.modules[__name__] = canonical_module` 级模块 alias。
- Rationale:
  - 只有物理归位后，后续新增功能才不会继续沿 legacy 树生长；模块 alias 还能同时保住旧路径上的 `is` 身份断言与 patch 语义。
- Evidence:
  - Tests: `python3 -m pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_session_service.py tests/integration/test_cli_http_flow_integration.py` -> `116 passed, 46 warnings in 8.90s`
  - Entry: canonical `apps/coding_cli`、`platform/llm/providers`、`platform/persistence/session`、`platform/hooks`、`platform/tools` 已承载真实实现；legacy `cli/llm/session/hooks/tools` 收口为 compatibility alias/shim，active wiring 不再回流依赖 legacy 实现路径。
- Rollback:
  - 最近稳定点：`347fb55138e9`
- Commits: C1=`347fb55138e9`, C2=`240207fd64de`, C3=`pending`
- Next:
  - 执行 R86.3，补全 full sweep、live 与集成收尾证据。

### R86.3 全量门禁、live 验证、集成与清理
- Context:
  - milestone DONE 前必须补 full sweep、live 证据、main 集成、board 更新与 worktree 清理。
- Decision:
  - 先以 authoritative rerun 基线补齐 focused/broader/full/live 证据，再执行 main 集成、board 更新与 worktree 清理。
- Rationale:
  - milestone 文档必须能回放“从 authoritative rerun 到最终 DONE”的完整链路；先固定全绿证据能降低后续 rebase/merge 排障成本。
- Evidence:
  - Tests: `python3 -m pytest -q` -> `601 passed, 4 skipped, 246 warnings in 20.35s`
  - Entry: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py` -> `1 passed in 4.09s`
  - Entry: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py` -> `1 passed in 6.20s`
- Rollback:
  - 最近稳定点：`240207fd64de`
- Commits: C1=`347fb55138e9`, C2=`240207fd64de`, C3=`pending`
- Next:
  - merge `milestone/M86` -> `main`，push `main`，更新 `data/dev-tasks.json`，随后移除 M86 worktree。
