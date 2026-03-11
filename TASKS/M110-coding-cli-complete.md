# M110 Coding CLI 完整态收口

## Milestone 摘要
- Milestone: M110 / Coding CLI 完整态收口
- Goal: 在 M108 之后把 `coding_cli` 收到当前 SPEC 完整态，确保默认使用路径、REPL 生命周期和人工启动体验都符合 `docs/CodingCLI-SPEC.md`
- Gate: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/e2e/test_cli_managed_live_agent_e2e.py`
- Scope: `src/coding_cli/**`、指定 CLI 测试、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、`data/dev-tasks.json`
- Hard guards:
  - 无参数启动必须默认进入 Managed 模式，不能把 remote 保留为隐式默认。
  - 保留 single-command stdout JSON 契约与 `--mode remote --base-url <url>` 行为。
  - 复用现有 `managed_server` 与 REPL runtime/input 流，不重写 CLI 架构。
  - `PROGRESS` 必须记录真实 smoke commands / evidence。

## Roadpoints

### R1 默认启动路径切换到 Managed
- Status: TODO
- Acceptance:
  - 无参数 REPL 启动走 Managed 模式并自动拉起本地 agent。
  - `--mode remote --base-url <url>` 继续可用，缺少 `--base-url` 仍给出 input 层错误。
  - single-command `send-message` stdout 仍保持单个 JSON，不混入 REPL 事件。
  - Managed 模式继续复用本地 `managed_server` 生命周期与退出清理。
- Tests Plan:
  - unit: 选，用来锁定 mode 解析、managed lifecycle、remote 错误分支。
  - contract: 不单开；沿用 unit 中对 JSON error / stdout contract 的断言即可覆盖边界结构。
  - integration: 选，用 HTTP app 串起 create-session/send-message 与 remote 显式模式保活。
  - e2e: 本 Roadpoint 暂不新增 live provider e2e，只保留后续 R2 的真实入口 smoke 作为验收证据。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_without_mode_defaults_repl_to_managed_lifecycle`
  - `tests/unit/test_cli_main.py::test_run_cli_without_mode_defaults_command_path_to_managed_when_base_url_is_local`
  - `tests/unit/test_cli_main.py::test_run_cli_default_mode_can_be_overridden_to_remote`
  - `tests/integration/test_cli_http_flow_integration.py` 中显式 remote/managed 调用回归
- DoD:
  - Gate 全绿
  - R1 完成 C1/C2/C3
  - `PROGRESS/M110-coding-cli-complete.md` 记录决策、证据、提交 hash

### R2 验收口径补齐与真实 smoke 证据固化
- Status: TODO
- Acceptance:
  - `docs/CodingCLI-SPEC.md` §10 的 10 条验收标准有自动化或手工 smoke 对应关系。
  - M108 的多行粘贴与 `/exit` 清队行为纳入本 milestone 正式验收记录。
  - 提供真实 CLI 启动/退出 smoke evidence，能证明 parameterless Managed 启动与清理路径可用。
  - non-TTY / slash command / context budget / error layering / async event 行为覆盖关系可追溯。
- Tests Plan:
  - unit: 选，补缺的默认启动/退出语义和 M108 回归口径。
  - contract: 不单开；复用现有 stdout JSON、error layer+sugestion 断言。
  - integration: 选，验证 HTTP flow、tool-calling、error evidence、remote 显式模式。
  - e2e: 选，补 live managed smoke 的默认入口覆盖；若 live proxy 缺失则保留 skip，但要另跑真实本地 smoke 命令收证。
- Expected Tests:
  - `tests/e2e/test_cli_managed_live_agent_e2e.py::test_cli_managed_mode_can_complete_live_agent_turn`
  - `tests/unit/test_cli_main.py` 既有 `/exit`、history、slash command、non-TTY 覆盖
  - `tests/integration/test_cli_http_flow_integration.py` 既有 tool-calling / timeout evidence / remote flow 覆盖
- DoD:
  - Gate 全绿
  - 真实 smoke 命令与输出片段写入 `PROGRESS/M110-coding-cli-complete.md`
  - 如沉淀出新预防规则，追加 `LOGBOOK.md`
  - R2 完成 C1/C2/C3
