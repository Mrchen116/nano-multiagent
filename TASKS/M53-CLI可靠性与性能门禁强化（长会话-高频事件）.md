# M53 - CLI可靠性与性能门禁强化（长会话/高频事件）

## Milestone Contract
- Milestone: `M53`
- Title: `CLI可靠性与性能门禁强化（长会话/高频事件）`
- Goal: 建立长会话、高频事件、重绘频率的稳定性护栏与门禁。
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/**cli*`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: 非 CLI 内核/API 目录（`src/nano_multiagent/{agent,server,session,tools,llm,core,hooks,runs}/**`）
- Collaboration Boundary:
  - 优先改动：`src/nano_multiagent/cli/events/**`、`src/nano_multiagent/cli/render/**` 与对应测试。
  - 避免改动：`src/nano_multiagent/cli/app/commands.py`（并行里程碑正在处理）。
- Prevention Rules:
  - 只改 CLI，不改内核 API 与协议。
  - 保持 `run_id` 过滤、`event_id/fallback` 去重、preview/final 阶段机不回归。
  - 保持 `send-message` 单 JSON 契约不回归。
  - 先红后绿，严格 C1/C2/C3。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `112 passed, 44 warnings`（2026-03-04）

## Roadpoints

### R1 长会话/高频事件回归红测集
- Acceptance:
  - 新增“高频事件批处理”回归测试（吞吐与预览发射比例边界）。
  - 新增“长会话多批次”回归测试（去重/过滤计数稳定，不出现退化）。
  - 锁定性能指标结构（可观测字段 + 阈值）红测。
- Tests Plan:
  - unit: 选；核心逻辑位于 `events` 模块，适合快速稳定回归。
  - integration: 不选；R2/R3 统一回归关键链路。
  - contract: 不选；本路标不涉及 API 契约结构调整。
  - e2e: 不选；R3 managed 验收。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_consume_async_run_events_high_frequency_batch_records_perf_baseline`
  - `tests/unit/test_cli_main.py::test_consume_async_run_events_long_session_batches_keep_perf_guardrails_stable`
  - `tests/unit/test_cli_main.py::test_send_message_with_async_events_exposes_perf_metrics_snapshot`
- DoD:
  - 红测失败点明确且仅提交测试（C1）。
- Status: `TODO`

### R2 性能护栏落地（指标观测 + 阈值判定 + 重绘基线）
- Acceptance:
  - 在 `cli/events` 引入可观测性能指标（吞吐、预览/重绘比、去重丢弃原因、采样规模）。
  - 设置阈值并输出 guardrail 判定（sample_ready/throughput_ok/redraw_ratio_ok/stable）。
  - 将指标暴露到 `_repl_view`，不破坏现有渲染与契约。
  - 全量门禁通过。
- Tests Plan:
  - unit: 选；验证指标计数、阈值判定与边界。
  - integration: 选；保证现有异步事件链路行为不回归。
  - contract: 选；保证 CLI 契约测试持续通过。
  - e2e: 不选；R3 执行 managed。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/contract/test_cli_http_only_contract.py`
  - `tests/contract/test_cli_error_contract.py`
- DoD:
  - C2 前执行门禁并全绿；提交实现/重构（C2）。
- Status: `TODO`

### R3 收口（门禁 + managed + main 集成 + dev_tasks DONE）
- Acceptance:
  - 全量门禁通过。
  - managed CLI 实跑通过，包含高频工具事件片段且无重复关键线。
  - 完成 `rebase origin/main`、`merge --no-ff`、`push origin main`。
  - `dev_tasks` 更新 `M53=DONE`，result 含 summary/tests/commits/new_rules。
- Tests Plan:
  - unit: 选；执行门禁。
  - integration: 选；执行门禁。
  - contract: 选；执行门禁。
  - e2e: 选；managed CLI 实跑。
- Expected Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - `PYTHONPATH=src NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000 /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
- DoD:
  - main 合并并 push。
  - `data/dev-tasks.json` 中 `M53` 为 `DONE` 且 result 完整。
- Status: `TODO`
