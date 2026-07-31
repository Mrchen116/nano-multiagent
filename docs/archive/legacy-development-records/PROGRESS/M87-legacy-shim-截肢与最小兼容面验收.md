# PROGRESS (Milestone: M87)

- Milestone: M87
- Title: 多产品架构重构十四期：legacy shim 截肢与最小兼容面验收
- Worktree: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M87`
- Branch: `milestone/M87`
- Baseline:
  - Tests: `python3 -m pytest -q`
  - Result: 待执行；当前 authoritative base 为 `origin/main` commit `9584577`，已包含 M85 与 M86。
- Notes:
  - 目标不是伪造“零 shim”，而是把兼容面削到真正有外部价值的最小集合。
  - 初步盘点显示，`server` 的 `auth/deps/sse/routes/*` 与 `cli` 的 `app/events/input/render/runtime` 及一组 helper facade 更像历史内部路径，优先作为删除候选；`server.app`、`cli.main`、`cli.commands`、`cli.http_client`、`sdk.client` 等更接近外部入口。

## Roadpoints

### R87.1 最小 legacy surface contract 先红
- Context:
  - M83/M86 后 canonical ownership 已基本完成，但 acceptance contract 仍以“保留大量 legacy shim”口径编写，未能区分真正 external compat 与低价值历史内部 shim。
  - 当前仓内仍保留 `server.auth`、`server.deps`、`server.sse`、`server.routes.*` 以及 `cli` 的 layered helper compat 文件/子包；这些多数只服务历史测试/内部导入习惯，而非真正稳定 external surface。
- Decision:
  - 先把 acceptance contract 改写成 M87 最小兼容面口径，并让红测明确要求删除低价值 `server/*` 与 `cli/*` helper shim。
- Rationale:
  - 先锁定“哪些必须活、哪些必须死”，才能避免继续把低价值 shim 当作默认兼容面永久保留下来。
- Evidence:
  - 红测：`python3 -m pytest -q tests/contract/test_multi_product_architecture_acceptance.py tests/unit/test_platform_http_api_location.py tests/unit/test_apps_coding_cli_location.py` -> `4 failed, 5 passed`；失败点符合预期：architecture doc 尚未有 M87 段落、`session.service` 等最小保留面未入文档、`server/auth.py` 等待删 shim 仍存在、HTTP API location test 仍按旧 route shims 口径断言。
  - 绿测：`python3 -m pytest -q tests/contract/test_multi_product_architecture_acceptance.py tests/unit/test_platform_http_api_location.py tests/unit/test_apps_coding_cli_location.py tests/unit/test_cli_refactor_boundaries.py tests/contract/test_cli_http_only_contract.py tests/unit/test_cli_managed_server.py tests/unit/test_server_auth.py tests/unit/test_server_global_routes.py tests/unit/test_server_message_route.py tests/unit/test_hook_query_models.py tests/unit/test_cli_context_budget.py tests/unit/test_cli_turn_usage.py` -> `52 passed in 0.97s`
  - Entry: M87 acceptance contract 已改写为“最小保留 compatibility surface + 已删除低价值 shim family”；`server` surviving compat 收缩到 package root + `server.app`，`cli` surviving compat 收缩到 `commands/main/http_client/release_*`。
- Rollback:
  - 最近稳定点：`9584577`
- Commits: C1=`75a7781`, C2=`6881ff7`, C3=`62ba336`
- Next:
  - R87.1/R87.2 已合流，进入最终集成。

### R87.2 删除低价值 shim family 并切回 canonical imports
- Context:
  - `server/auth/deps/sse/routes/*` 与 `cli/app|events|input|render|runtime` 等 helper shim 继续保留会误导后续开发，把历史内部导入习惯固化成“官方兼容面”。
- Decision:
  - 删除上述 low-value shim 文件；仓内测试与实现全部切到 canonical `platform.http_api.*` 与 `apps.coding_cli.*`。
  - 对仍有外部价值的 CLI 兼容入口，仅保留 `cli.commands`、`cli.main`、`cli.http_client`、`cli.release_playbook`、`cli.release_observability`；其中 `release_*` 再收薄为 direct compat shim。
- Rationale:
  - M87 的关键是把兼容面从“目录级历史镜像”缩成“少数用户可见入口”；否则 canonical ownership 虽然在概念上成立，仓内与文档仍会不断把 legacy helper 当真源使用。
- Evidence:
  - 删除项：`src/nano_multiagent/server/auth.py`、`src/nano_multiagent/server/deps.py`、`src/nano_multiagent/server/sse.py`、`src/nano_multiagent/server/routes/*`、`src/nano_multiagent/cli/app/*`、`src/nano_multiagent/cli/events/*`、`src/nano_multiagent/cli/input/*`、`src/nano_multiagent/cli/render/*`、`src/nano_multiagent/cli/runtime/*` 及 `cli/context_budget.py`、`cli/error_presenter.py`、`cli/managed_server.py`、`cli/repl_*`、`cli/turn_usage.py`。
  - 仓内回线：`tests/unit/test_server_*` 与 `tests/unit/test_hook_query_models.py` 已改用 `platform.http_api.*`；`tests/unit/test_cli_*` 与 `tests/integration/test_cli_http_flow_integration.py` 已改用 `apps.coding_cli.*` canonical 分层。
  - `src/nano_multiagent/cli/release_playbook.py` 与 `src/nano_multiagent/cli/release_observability.py` 已改为极薄 compat shim，canonical home 分别是 `apps/coding_cli/release_playbook.py` 与 `apps/coding_cli/release_observability.py`。
- Rollback:
  - 最近稳定点：`9584577`
- Commits: C1=`75a7781`, C2=`6881ff7`, C3=`62ba336`
- Next:
  - 已完成删减与回线，进入 R87.3 集成收尾。

### R87.3 全量门禁、live 验证、集成与清理
- Context:
  - milestone DONE 前必须证明删减 shim 后全量与 live 仍稳定，并完成 main 集成与 board/worktree 清理。
- Decision:
  - 先跑 full sweep 与两条 live，随后提交、merge main、更新 `data/dev-tasks.json`、删除 worktree。
- Rationale:
  - shim 删除类改动最怕“focused 绿、全量炸”；必须用全量与 live 证明 external compat 面缩窄没有破坏产品主线行为。
- Evidence:
  - Tests: `python3 -m pytest -q` -> `605 passed, 4 skipped, 246 warnings in 20.75s`
  - Live: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py` -> `1 passed in 4.56s`
  - Live: `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py` -> `1 passed in 6.11s`
  - Merge: `git merge --no-ff milestone/M87 && git push origin main` -> `main` at `c46133e`
  - Board/Cleanup: `data/dev-tasks.json` 已更新为 `DONE`，随后移除 M87 worktree 并删除本地 `milestone/M87` 分支。
- Rollback:
  - 最近稳定点：`62ba336`
- Commits: C1=`75a7781`, C2=`6881ff7`, C3=`62ba336`
- Next:
  - DONE.
