# TASKS (Milestone: M84)

- Title: 多产品架构重构十一期：live anthropic 链路修复与真实 CLI 验收
- Goal: 修复 live anthropic provider 请求与 managed coding_cli 实链路在本地代理下的失败问题，使真实 send-message、live proxy e2e、live managed CLI e2e 一致恢复，并把实跑证据落盘。
- Exit Criteria:
  - `tests/e2e/test_anthropic_generate_e2e.py` 与 `tests/e2e/test_cli_managed_live_agent_e2e.py` 在启用 live 环境变量后通过。
  - 真实 `coding_cli` managed 模式 smoke 可完成至少一轮简单消息。
  - `TASKS/PROGRESS` 记录根因、修复、回滚点与 live 命令证据。
- Test command: `python3 -m pytest -q`
- Branch: `milestone/M84`

## R84.1 修复 anthropic live model 选择与代理兼容
- Status: DONE
- Acceptance:
  - anthropic provider 在本地代理 `/v1/messages` 下默认/显式模型可用。
  - `tests/e2e/test_anthropic_generate_e2e.py::test_anthropic_non_stream_generate_against_local_proxy` 先红后绿。
  - model registry / factory / live e2e 的模型选择语义一致。
  - 不破坏现有 openai_compat 路径与 anthropic 契约测试。
- Tests Plan:
  - unit: 是；锁定 anthropic default model 与 metadata 解析。
  - contract: 是；保住 provider/model registry 契约与 provider client 基本接线。
  - integration: 是；验证 anthropic factory request 仍命中 `/v1/messages`。
  - e2e: 是；直接跑 live proxy red/green。
- Expected Tests:
  - `tests/unit/test_llm_model_registry.py`
  - `tests/integration/test_anthropic_generation_integration.py`
  - `tests/e2e/test_anthropic_generate_e2e.py::test_anthropic_non_stream_generate_against_local_proxy`
- DoD:
  - `python3 -m pytest -q` 全绿
  - R84.1 的 C1/C2/C3 齐全
  - `PROGRESS/M84-live-anthropic-cli.md` 写清根因/证据/回滚点/提交哈希

## R84.2 收口 managed coding_cli live 验收到真实单命令链路
- Status: DONE
- Acceptance:
  - live managed CLI e2e 通过真实 managed API + local proxy anthropic provider。
  - 验收入口遵守既有 `create-session/send-message` 单 JSON stdout 契约，不回流破坏 REPL 文本契约。
  - 至少覆盖 create-session 与 send-message 一轮真实消息闭环。
  - 明确记录为何不改 REPL 为 JSON 输出。
- Tests Plan:
  - unit: 视需要；仅当新增 CLI 输出/参数分支时补最小回归。
  - contract: 是；不破坏单命令 JSON 契约与 REPL 文本契约。
  - integration: 是；必要时补 managed command-path 回归。
  - e2e: 是；跑 `tests/e2e/test_cli_managed_live_agent_e2e.py` red/green。
- Expected Tests:
  - `tests/e2e/test_cli_managed_live_agent_e2e.py::test_cli_managed_mode_can_complete_live_agent_turn`
  - 若有新增回归：`tests/unit/test_cli_main.py` / `tests/integration/test_cli_http_flow_integration.py`
- DoD:
  - `python3 -m pytest -q` 全绿
  - R84.2 的 C1/C2/C3 齐全
  - `PROGRESS/M84-live-anthropic-cli.md` 写清契约取舍、实跑命令与结果

## R84.3 全量 live sweep、实跑证据、main 集成与清理
- Status: DONE
- Acceptance:
  - 运行 milestone gate 与 full sweep，包含默认 skip 的 live tests。
  - 运行真实 managed CLI smoke，并记录精确命令/结果。
  - 合并 `milestone/M84` 到 `main`，push，更新共享 `data/dev-tasks.json` 为 DONE。
  - 清理 `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M84` worktree。
- Tests Plan:
  - unit/contract/integration/e2e: 全量 sweep；重点包含 live e2e。
- Expected Tests:
  - `python3 -m pytest -q`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 python3 -m pytest -q tests/e2e/test_anthropic_generate_e2e.py`
  - `NANO_MULTIAGENT_RUN_LIVE_PROXY_E2E=1 NANO_MULTIAGENT_RUN_LIVE_CLI_E2E=1 python3 -m pytest -q tests/e2e/test_cli_managed_live_agent_e2e.py`
- DoD:
  - 全量测试与 live sweep 结果已写入 `PROGRESS/M84-live-anthropic-cli.md`
  - main 合并/push/dev-tasks DONE/worktree remove 完成
