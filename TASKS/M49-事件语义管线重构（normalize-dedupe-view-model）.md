# M49 - 事件语义管线重构（normalize/dedupe/view-model）

## Milestone Contract
- Milestone: `M49`
- Title: `事件语义管线重构（normalize/dedupe/view-model）`
- Goal: 在仅 CLI 范围内重构事件处理链路，形成清晰分层（normalize -> dedupe -> view-model），并稳定 `event_id + fallback` 去重窗口，保持现有契约不回归。
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/unit/test_cli_main.py`、`tests/integration/test_cli_http_flow_integration.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: `src/nano_multiagent/core/**`、`src/nano_multiagent/server/**`、`src/nano_multiagent/runs/**`、`src/nano_multiagent/tools/**`、`src/nano_multiagent/hooks/**`、`src/nano_multiagent/agent/**`、`data/dev-tasks.json`
- Prevention Rules:
  - 只改 CLI，不改内核 API / 协议。
  - 保持排队能力（in-flight + queue）不回归。
  - 保持 `run_id` 过滤 + `event_id` 去重。
  - 保持 `send-message` 单 JSON stdout 契约。
  - 严格 C1/C2/C3。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `108 passed, 42 warnings`（2026-03-04）

## Roadpoints

### R1 语义管线分层（normalize -> dedupe -> view-model）
- Acceptance:
  - 事件处理不再由单函数混合完成；normalize、去重判定、视图模型聚合职责分离。
  - 旧入口调用路径保持兼容，不破坏 `run_cli` / REPL 行为。
  - 摘要构建依旧产出 `status_updates/tool_updates`，对外结构不变。
- Tests Plan:
  - unit: 选；锁定分层后输出行为等价。
  - integration: 选；覆盖 REPL HTTP 链路未回归。
  - contract: 选；确保 send-message JSON 契约不受影响。
  - e2e: 不选；在 R3 做 managed 实跑。
- Expected Tests:
  - `tests/unit/test_cli_main.py`（事件消费/摘要相关用例）
  - `tests/integration/test_cli_http_flow_integration.py`（异步事件链路）
  - `tests/contract/test_cli_http_only_contract.py`
- DoD:
  - C1 红测先锁定分层目标，C2 实现后门禁绿，C3 文档补齐。
- Status: `DONE`

### R2 event_id + fallback 去重窗口稳态化
- Acceptance:
  - 当 `event_id` 缺失/变化时，按 `run_id + 语义键` 去重，避免历史回放重复渲染。
  - 去重窗口有界（按 run 分桶 + LRU/容量控制），不会无界增长。
  - 非语义字段变化（如 `ts`）不导致重复关键线；合法不同事件不被误吞。
- Tests Plan:
  - unit: 选；新增/调整去重窗口与边界回归。
  - integration: 选；确认真实链路中重复事件被抑制且文本不丢。
  - contract: 不选；本路标不改 API 契约。
  - e2e: 不选；在 R3 统一验收。
- Expected Tests:
  - `tests/unit/test_cli_main.py::test_run_cli_repl_dedupes_replayed_tool_start_without_event_id`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_dedupes_replayed_tool_start_with_changed_event_id`
  - `tests/unit/test_cli_main.py::test_run_cli_repl_dedupes_replayed_tool_start_with_changed_event_id_and_nonsemantic_metadata`
  - `tests/integration/test_cli_http_flow_integration.py`（相关异步事件用例）
- DoD:
  - 红测失败点明确为去重窗口缺陷；C2 后目标用例与门禁全绿。
- Status: `DONE`

### R3 收口验收（全量门禁 + managed 实跑 + 集成）
- Acceptance:
  - 全量门禁通过。
  - managed CLI 实跑通过，记录重构前后事件展示对比（关注重复抑制与摘要稳定）。
  - 分支 `rebase origin/main` 后 `merge --no-ff` 到 main 并 push。
  - 使用 `dev_tasks.py` 将 M49 标记为 DONE 并写 result。
- Tests Plan:
  - unit: 选；执行门禁。
  - integration: 选；执行门禁。
  - contract: 选；执行门禁。
  - e2e: 选；managed CLI 实跑。
- Expected Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - `PYTHONPATH=src NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000 python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
- DoD:
  - R1/R2 C1/C2/C3 全部完成。
  - main 已 push，`dev_tasks` 状态为 `DONE`。
- Status: `DONE`
