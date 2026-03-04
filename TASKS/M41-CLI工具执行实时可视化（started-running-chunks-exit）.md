# M41 - CLI工具执行实时可视化（started/running/chunks/exit）

## Milestone Contract
- Milestone: `M41`
- Title: `CLI工具执行实时可视化（started/running/chunks/exit）`
- Goal: 在避免代码腐化前提下，为 CLI 增加工具执行实时可视化：bash started、running 心跳、stdout/stderr chunk、exit code。
- Scope:
  - Allowed: `src/nano_multiagent/cli/**`、`tests/unit/test_cli_main.py`、`tests/integration/test_cli_http_flow_integration.py`、`tests/contract/test_cli_http_only_contract.py`、`tests/contract/test_sse_event_contract.py`、`tests/unit/test_sse_encoder.py`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md（仅追加）`
  - Forbidden: `src/nano_multiagent/server/**`、`src/nano_multiagent/runs/**`、`src/nano_multiagent/tools/**`、`src/nano_multiagent/agent/**`、`src/nano_multiagent/core/**`、`data/dev-tasks.json`
- Prevention Rules:
  - 先做可用现有 API 完成的部分；遇到 chunk/exit 实时能力缺口时，停止实现并回传最小内核改动清单。
  - 严禁未确认前改内核。
  - 保持 HTTP-only 边界与非交互 `send-message` 单 JSON 契约。

## Baseline Gate
- Command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_sse_event_contract.py tests/unit/test_sse_encoder.py`
- Result:
  - `76 passed, 42 warnings`

## Roadpoints

### R1 CLI 已有事件可视化能力补齐（started/running/exit）（DONE）
- Acceptance:
  - REPL 可见工具 started，且在工具执行中可见 running 状态进度（含耗时/状态）。
  - 工具结束时可见 exit code（至少对 `bash` 工具）。
  - 输出改动仅在 REPL 路径，不污染 `send-message` 单 JSON。
- Tests Plan:
  - unit: 选；验证 REPL 对 started/running/exit 的文本渲染与去重行为。
  - contract: 选；确保非交互 JSON 契约不变。
  - integration: 选；真实 CLI+HTTP 链路验证 started/running/exit 可见。
  - e2e: 不选；本仓库当前由 integration 覆盖 CLI 入口主链路。
- Expected Tests:
  - `tests/unit/test_cli_main.py`（新增/调整 started/running/exit 断言）
  - `tests/integration/test_cli_http_flow_integration.py`（新增/调整 REPL 可视化断言）
  - `tests/contract/test_cli_http_only_contract.py`
- DoD:
  - 红测先行并通过门禁命令。
  - C1/C2/C3 提交齐全。
  - PROGRESS 写清证据与回滚点。
- Commits:
  - C1: `64dc79b`
  - C2: `463ab8f`
- Status: `DONE`

### R2 chunk/exit 实时能力缺口评估与最小内核改动清单（DONE）
- Acceptance:
  - 明确当前 API 是否存在执行中 stdout/stderr chunk 事件。
  - 若缺失，给出最小内核改动清单：文件、接口、事件 schema、测试影响面。
  - 在主 agent 明确批准前不改任一内核文件。
- Tests Plan:
  - unit: 选；覆盖事件转换/编码与 CLI 消费。
  - contract: 选；覆盖 SSE 事件 schema 新增字段与兼容性。
  - integration: 选；覆盖真实工具执行中 chunk 流与 exit 呈现。
  - e2e: 不选；此里程碑不引入额外 UI 层入口。
- Expected Tests:
  - `tests/contract/test_sse_event_contract.py`
  - `tests/unit/test_sse_encoder.py`
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
- DoD:
  - 产出并回传“最小内核改动清单”。
  - 获得主 agent 批准后再进入实现（已批准并执行）。
  - 保持 `send-message` 单 JSON 契约。
- Status: `DONE`

### R3 回归收口（DONE）
- Acceptance:
  - 目标门禁全绿。
  - HTTP-only 边界与单 JSON 契约无回归。
  - M41 文档记录完整（方案、证据、回滚点、提交哈希）。
- Tests Plan:
  - unit: 选；复跑 M41 相关 unit。
  - contract: 选；复跑 CLI 合同与 SSE 合同。
  - integration: 选；复跑 CLI HTTP 主链路。
  - e2e: 不选；同上。
- Expected Tests:
  - 完整门禁命令（同 Baseline Gate）
- DoD:
  - 门禁全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 回填完整证据。
- Final Gate:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_sse_event_contract.py tests/unit/test_sse_encoder.py`
  - `79 passed, 44 warnings`
- Status: `DONE`
