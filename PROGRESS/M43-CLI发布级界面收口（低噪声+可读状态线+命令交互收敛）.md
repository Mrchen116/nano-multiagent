# M43 - CLI发布级界面收口（低噪声+可读状态线+命令交互收敛）

## Baseline
- Test command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `98 passed, 40 warnings`

## Constraints / Notes
- 仅改 CLI 层与相关测试，禁止触碰内核与 server/runtime/tool/hook/agent/core 模块。
- `send-message` stdout 单 JSON 契约必须保持。
- REPL 异步消费必须保留 `event_id` 去重与 `run_id` 过滤。
- 目标是“发布级默认阅读体验”：答案优先、低噪声状态线、工具过程可读且不过载。

### R1 默认 REPL 输出降噪（状态线+工具摘要发布化）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next:

### R2 `/` 命令提示交互收敛（不刷屏、不污染输入行）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=TODO, C2=TODO, C3=TODO
- Next:

### R3 收口与验收（真实 managed 交互 + 集成）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=N/A, C2=TODO, C3=TODO
- Next:
