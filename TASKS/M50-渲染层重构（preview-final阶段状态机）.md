# M50 - 渲染层重构（preview/final阶段状态机）

## Milestone Contract
- Milestone: `M50`
- Title: `渲染层重构（preview/final阶段状态机）`
- Goal: 引入 `STREAMING/FINALIZING/FINALIZED` 阶段状态机，分离实时预览与最终摘要渲染，杜绝双写与复读，并统一文案风格。
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/**cli*`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: 非 CLI 内核/API 目录（`src/nano_multiagent/{agent,server,session,tools,llm,core,hooks,runs}/**` 等）
- Prevention Rules:
  - 只改 CLI，不改内核 API。
  - 保持 `send-message` 单 JSON 契约不回归。
  - 保持 `run_id` 过滤 + `event_id/fallback` 去重不回归。
  - 先红后绿，R1/R2/R3 均严格执行 C1/C2/C3。
  - 必做 managed CLI 实跑验收。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `113 passed, 42 warnings`（2026-03-04）

## Roadpoints

### R1 渲染阶段状态机红测（STREAMING/FINALIZING/FINALIZED）
- Acceptance:
  - 增加阶段状态机测试，明确状态转换与非法转换约束。
  - 锁定“进入 FINALIZING 后禁止继续实时 preview 发射”的行为。
  - 锁定“summary 构建只在 FINALIZING/FINALIZED 阶段”的行为边界。
- Tests Plan:
  - unit: 选；阶段机与 preview 发射闸门属于 CLI 事件层纯逻辑。
  - integration: 不选；R2/R3 统一验证链路。
  - contract: 不选；本路标不涉及 API 契约变更。
  - e2e: 不选；R3 做 managed。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_cli_render_phase_machine_transitions_and_guards`
  - `tests/unit/test_cli_main.py::test_consume_async_run_events_stops_preview_after_finalizing`
- DoD:
  - 红测先失败并提交 C1。
- Status: `DONE`

### R2 状态机落地与文案统一（preview/final 分离）
- Acceptance:
  - `send_message_with_async_events` 接入阶段状态机，preview 与 summary 明确分层。
  - 杜绝 preview/final 双写复读（尤其工具关键线），不吞合法不同事件。
  - 错误提示层次与输出风格保持一致（含 `State/Tool/Progress` 语义）。
  - 全量门禁通过。
- Tests Plan:
  - unit: 选；覆盖阶段转换、preview 去重、summary 过滤。
  - integration: 选；覆盖 CLI HTTP 异步事件渲染链路。
  - contract: 选；覆盖 send-message/错误契约不回归。
  - e2e: 不选；R3 执行 managed。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/contract/test_cli_http_only_contract.py`
  - `tests/contract/test_cli_error_contract.py`
- DoD:
  - C2 前执行全量门禁并全绿；提交实现/重构 C2。
- Status: `DONE`

### R3 收口验收（门禁 + managed + main 集成 + dev_tasks DONE）
- Acceptance:
  - 全量门禁通过。
  - managed CLI 实跑通过，输出片段可证明 preview/final 无双写复读。
  - `rebase origin/main` 后合并到 `main` 并 `push origin main`。
  - 用 `dev_tasks.py` 更新 `M50=DONE`（含 summary/tests/commits/new_rules）。
- Tests Plan:
  - unit: 选；执行门禁。
  - integration: 选；执行门禁。
  - contract: 选；执行门禁。
  - e2e: 选；managed CLI 实跑。
- Expected Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - `PYTHONPATH=src NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000 /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
- DoD:
  - main 合并并 push。
  - `data/dev-tasks.json` 的 `M50` 状态为 `DONE` 且 result 完整。
- Status: `DONE`
