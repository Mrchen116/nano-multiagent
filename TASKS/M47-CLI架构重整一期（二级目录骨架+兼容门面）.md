# M47 - CLI架构重整一期（二级目录骨架+兼容门面）

## Milestone Contract
- Milestone: `M47`
- Title: `CLI架构重整一期（二级目录骨架+兼容门面）`
- Goal: 在不改变 CLI 外部行为前提下，引入二级目录分层骨架（app/input/events/render/runtime）并建立兼容门面，降低后续并行改造冲突。
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/unit/test_cli_main.py`、`tests/integration/test_cli_http_flow_integration.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`
  - Forbidden: `src/nano_multiagent/server/**`、`src/nano_multiagent/runs/**`、`src/nano_multiagent/tools/**`、`src/nano_multiagent/hooks/**`、`src/nano_multiagent/agent/**`、`src/nano_multiagent/core/**`、`data/dev-tasks.json`
- Prevention Rules:
  - 仅改 CLI，不改内核 API。
  - `send-message` 单 JSON 契约保持。
  - `run_id` 过滤 + `event_id` 去重不回归。
  - 小步重构，先红后绿，严格 C1/C2/C3。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `106 passed, 42 warnings`（2026-03-04，开工基线）

## Roadpoints

### R1 二级目录骨架与兼容导出边界
- Acceptance:
  - 新增 `cli/app`、`cli/input`、`cli/events`、`cli/render`、`cli/runtime` 二级目录与 `__init__.py`。
  - `cli/commands.py` 等旧模块对外导入路径保持可用（兼容门面）。
  - 不改变 `nano_multiagent.cli.main:run_cli` 行为。
- Tests Plan:
  - unit: 选；补边界红测，约束模块导出与路径稳定。
  - integration: 不选；本路标仅做结构层改造，不改运行时行为。
  - contract: 不选；契约在 R2/R3 统一覆盖。
  - e2e: 不选；在 R3 做 managed 验收。
- Expected Tests:
  - `tests/unit/test_cli_refactor_boundaries.py`
- DoD:
  - 红测先失败并锁定兼容门面目标。
  - 完成 C1/C2/C3。
- Status: `DONE`

### R2 按职责迁移并保持行为等价
- Acceptance:
  - 现有 CLI 模块能力迁入对应子目录（app/input/events/render/runtime），旧路径保留 facade 转发。
  - `run_cli`、REPL、`send-message` 行为不变。
  - 边界测试与主门禁通过。
- Tests Plan:
  - unit: 选；验证 facade 指向、命令编排与 REPL 关键路径。
  - integration: 选；验证 HTTP/REPL 入口行为不回归。
  - contract: 选；`send-message` 单 JSON 与错误契约不回归。
  - e2e: 不选；R3 统一执行。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/unit/test_cli_refactor_boundaries.py`
  - `tests/integration/test_cli_http_flow_integration.py`
  - `tests/contract/test_cli_http_only_contract.py`
  - `tests/contract/test_cli_error_contract.py`
- DoD:
  - 全量门禁全绿。
  - 完成 C2。
- Status: `DOING`

### R3 收口验收与集成
- Acceptance:
  - 全量门禁通过。
  - managed CLI 实跑通过（包含 REPL + 工具事件路径）。
  - 分支 rebase/main 合并/push 完成，`dev_tasks` 更新 `M47=DONE`。
- Tests Plan:
  - unit/integration/contract: 选；执行 milestone 门禁。
  - e2e: 选；managed CLI 实跑。
- Expected Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - `PYTHONPATH=src NANO_MULTIAGENT_LLM_BASE_URL=http://127.0.0.1:4000 /Users/czj/miniforge3/bin/python3 -m nano_multiagent.cli.main --mode managed --base-url http://127.0.0.1:8003 --token test-token`
- DoD:
  - main 合并并 push。
  - `data/dev-tasks.json` 更新为 `DONE` 并记录 result。
- Status: `TODO`
