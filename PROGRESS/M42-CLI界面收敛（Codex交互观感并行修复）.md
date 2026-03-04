# M42 - CLI界面收敛：对齐Codex交互观感（独立并行修复）

## Baseline
- Test command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `92 passed, 38 warnings`

## Notes from LOGBOOK / M39 / M40
- `send-message` 必须保持 stdout 单 JSON，REPL 事件噪声不能污染单命令模式。
- REPL 异步事件必须保留 `event_id` 去重与 `run_id` 过滤，避免串线。
- M40 已有“运行中输入排队”能力，M42 重点是终端渲染稳定性与信息架构收敛，不改内核。
- 当输出链路涉及实时终端渲染时，优先保证“稳定可读”再追求视觉增强。

### R1 终端渲染稳定化（并发输出不串行错位）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R2 输出信息架构收敛（答案优先 + 紧凑摘要）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R3 收口与集成（门禁、文档、合并）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
