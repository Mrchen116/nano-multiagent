# TASKS (Milestone: M20)

- Test command: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_sdk_client.py tests/unit/test_cli_managed_server.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py`
- Branch: `milestone/M20`

## [TODO] R20.1 单命令输出契约与 llm-config 路径先收口
- Acceptance:
  - `send-message` 单命令模式输出保持“仅单个 JSON”，stdout 不混入事件行。
  - CLI HTTP client 对 `/v1/llm-config` 使用与 server 一致的路径契约。
  - 新增/更新 unit+contract 覆盖单命令 JSON 与 llm-config 路径契约。
  - 本 Roadpoint 完成后，门禁测试保持全绿。
- Tests Plan:
  - `unit`: 选。覆盖 `run_cli` 单命令输出纯 JSON、`http_client` llm-config 调用路径与 payload。
  - `contract`: 选。补充 CLI 层最小契约断言，防止路径回归。
  - `integration`: 不选。本点先收口客户端契约，不引入事件流编排复杂度。
  - `e2e`: 不选。与当前 Milestone 目标重叠低，避免扩大范围。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/unit/test_sdk_client.py`
  - `tests/contract/test_cli_http_only_contract.py`
- DoD:
  - Red->Green，且 test command 全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录证据、回滚点、提交哈希。
- Status: TODO

## [TODO] R20.2 REPL 默认 async events 实时展示（含去重与 run_id 过滤）
- Acceptance:
  - REPL 发送消息改为默认走 async 提交，并实时展示 `run/tool/text` 事件。
  - 工具调用展示包含工具名与输出预览（长度受控，避免刷屏）。
  - 事件处理具备 `event_id` 去重与 `run_id` 过滤，避免历史事件串线。
  - 单命令模式不受影响，仍保持原有纯 JSON 输出行为。
- Tests Plan:
  - `unit`: 选。覆盖 REPL 事件渲染、去重/过滤、历史写入行为。
  - `contract`: 不选。本点侧重交互体验与事件消费逻辑。
  - `integration`: 选。在 ASGI integration 中验证 async 事件链路与展示关键字。
  - `e2e`: 不选。已有 integration 可覆盖入口行为。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
- DoD:
  - Red->Green，且 test command 全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录证据、回滚点、提交哈希。
- Status: TODO

## [TODO] R20.3 CLI 事件消费容错与回归加固
- Acceptance:
  - REPL 在 run 失败/超时场景可给出可操作错误且不破坏交互循环。
  - 事件展示与最终消息聚合在关键失败路径可预期，不污染单命令输出。
  - unit+integration 回归覆盖“失败场景 + 输出契约”组合，防止体验修复破坏契约。
  - 本 Roadpoint 完成后，test command 全绿。
- Tests Plan:
  - `unit`: 选。覆盖失败 run 的建议文案与 REPL 连续交互稳定性。
  - `contract`: 不选。契约边界已在 R20.1 固化。
  - `integration`: 选。覆盖 HTTP 链路下失败 run 的展示/错误行为。
  - `e2e`: 不选。维持 Milestone 范围仅 CLI 层。
- Expected Tests:
  - `tests/unit/test_cli_main.py`
  - `tests/integration/test_cli_http_flow_integration.py`
- DoD:
  - Red->Green，且 test command 全绿。
  - C1/C2/C3 提交齐全。
  - PROGRESS 记录证据、回滚点、提交哈希。
- Status: TODO
