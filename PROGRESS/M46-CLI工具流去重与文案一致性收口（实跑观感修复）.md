# M46 - CLI工具流去重与文案一致性收口（实跑观感修复）

## Baseline
- Tests:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`
- Result:
  - `103 passed, 42 warnings`（2026-03-04）

### Plan（一次性拆分）
- Context:
  - 问题集中在 CLI REPL 展示层：工具实时预览与摘要重复、文案前缀不一致、队列回放去重不稳。
  - 边界约束：只改 `src/nano_multiagent/cli/**` 与指定测试，不触及内核与 server/runtime。
- Decision:
  - 拆分为 `R1 去重`、`R2 文案与摘要收口`、`R3 集成与实跑验收`。
  - 采用先红后绿：先在 `tests/unit/test_cli_main.py` 与 `tests/integration/test_cli_http_flow_integration.py` 补回归，再最小改动 CLI 实现。
- Rationale:
  - 先锁定三类回归（重复、文案、摘要）可避免“观感修复”主观化，确保每条验收可自动验证。
- Evidence:
  - Tests: 基线门禁已绿（`103 passed, 42 warnings`）。
  - Entry: 代码梳理定位 `repl_events.py`/`repl_render.py` 为主修改面。
- Rollback:
  - 回退到本里程碑计划提交前的 `milestone/M46` 当前 HEAD。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 红测：补“无 event_id 回放 + 队列模式重复关键线”回归断言。

### R1 队列模式工具事件去重（含无 event_id 回放）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R2 Tool 文案一致性与“预览已出则摘要不重播”
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R3 收口（全量门禁 + managed 实跑 + main 集成 + dev_tasks DONE）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
