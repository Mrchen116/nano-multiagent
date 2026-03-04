# M44 - CLI发布级二次收敛（会话文案化+工具过程折叠）

## Baseline
- Test command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `101 passed, 40 warnings`
  - Verified at `2026-03-04`

## Handover
- Context: 上一位 worker 中断；当前 `milestone/M44` 未产生 M44 功能提交，仅存在文档草稿与工作区运行态文件。
- Decision: 在不回滚他人改动前提下复用已有草稿，先完成“计划提交”，随后按 R1->R2->R3 执行。
- Rationale: 先固化接手上下文与基线证据，避免后续提交链条缺失。
- Evidence:
  - Tests: `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
  - Entry: 基线已复跑全绿，可进入 Red 阶段。
- Rollback: `5cc9da2`（接手前稳定点）
- Commits: C1=<N/A>, C2=<N/A>, C3=<N/A>
- Next: 提交 TASKS/PROGRESS 计划变更，然后开始 R1 红测。

## Constraints / Notes
- 仅改 CLI 层与相关测试，禁止触碰 server/runtime/tools/hooks/agent/core。
- `send-message` stdout 单 JSON 契约必须保持。
- REPL 异步消费必须保留 `event_id` 去重与 `run_id` 过滤。
- 输出遵循 `event -> semantic -> render`，默认以会话主内容优先可读。

### R1 会话创建文案化（去 JSON 直出）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: 
  - Entry:
- Rollback:
- Commits: C1=<TBD>, C2=<TBD>, C3=<TBD>
- Next: 先修改 unit/integration 断言使其体现“会话文案化、去 JSON”。

### R2 工具过程折叠（关键节点摘要优先）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: 
  - Entry:
- Rollback:
- Commits: C1=<TBD>, C2=<TBD>, C3=<TBD>
- Next:

### R3 收口验收与集成（managed 真机验收 + main 集成）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: 
  - Entry:
- Rollback:
- Commits: C1=<N/A>, C2=<N/A>, C3=<TBD>
- Next:
