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
  - 拆分为 `R1 去重`、`R2 文案统一`、`R3 摘要去重与收口`。
  - 采用先红后绿：先在 `tests/unit/test_cli_main.py` 与 `tests/integration/test_cli_http_flow_integration.py` 补回归，再最小改动 CLI 实现。
- Rationale:
  - 先锁定三类回归（重复、文案、摘要）可避免“观感修复”主观化，确保每条验收可自动验证。
- Evidence:
  - Tests: 基线门禁已绿（`103 passed, 42 warnings`）。
  - Entry: 代码梳理定位 `repl_events.py`/`repl_render.py` 为主修改面。
- Rollback:
  - 回退到计划提交前稳定点。
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
  - 执行 R1 红测：补“无 event_id 回放”去重断言。

### R1 队列模式工具事件去重（含无 event_id 回放）
- Context:
  - 当前去重只依赖 `event_id`；当事件回放缺 `event_id` 时，同一工具 `start` 线会被重复消费。
- Decision:
  - 新增 `_AsyncNoEventIdReplayStubClient` 红测，复现“同批无 `event_id` 事件回放两轮”。
  - 在 `consume_async_run_events` 增加 fallback 指纹去重，仅覆盖 `run_status/tool_*` 事件，避免影响文本增量。
- Rationale:
  - 用 `event_name + canonical_data` 去重可稳定识别历史回放，不改变已有 `event_id` 去重和 `run_id` 过滤主路径。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "dedupes_replayed"`（失败：`bash start args=` 出现 2 次）。
    - 绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "uses_async_events_with_run_filter_and_dedup or dedupes_replayed_tool_start_without_event_id or streams_started_running_chunk_and_exit_for_tool_execution"` -> `3 passed`。
    - 门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `104 passed, 42 warnings`。
  - Entry:
    - 回放缺 `event_id` 时，`bash start args=` 从重复输出降为 1 次。
- Rollback:
  - `1047442`（R1 红测提交）
- Commits: C1=`1047442`, C2=`6e6cb2d`, C3=`本提交`
- Next:
  - 进入 R2：统一实时预览与摘要 `Tool: ` 文案风格。

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
