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
- Commits: C1=`1047442`, C2=`6e6cb2d`, C3=`6345556`
- Next:
  - 进入 R2：统一实时预览与摘要 `Tool: ` 文案风格。

### R2 Tool 文案一致性与“预览已出则摘要不重播”
- Context:
  - 现状实时预览使用 `Tool <name> ...`，最终摘要使用 `Tool: ...`，同一轮内风格割裂。
  - 风格不一致会放大“重复打印”的观感噪音。
- Decision:
  - 先在 unit+integration 调整断言为统一 `Tool: ` 前缀，形成红测。
  - 统一 `repl_events._event_preview_line` 的所有工具事件文案为 `Tool: ...`。
  - 扩展 `repl_render._normalize_tool_update` 支持 `Tool:` 归一化，避免摘要出现双前缀。
- Rationale:
  - 保持预览与摘要同一视觉语法，后续做摘要去重时可直接按统一模式比对。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py -k "uses_async_events_with_run_filter_and_dedup or groups_same_tool_name_events_by_call_id or compact_answer_first_summary_for_async_flow or streams_started_running_chunk_and_exit_for_tool_execution or streams_async_run_tool_and_text_events or streams_started_running_chunk_and_exit_for_bash_tool"` -> `6 failed`（均为 `Tool:` 断言不满足）。
    - 绿测：同命令 -> `6 passed`。
    - 门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `104 passed, 42 warnings`。
  - Entry:
    - 预览链路 `echo/bash` 关键线统一为 `Tool: ...`，不再混用无冒号风格。
- Rollback:
  - `b82005f`（R2 红测提交）
- Commits: C1=`b82005f`, C2=`84d966e`, C3=`6bd4f9d`
- Next:
  - 进入 R3：补“预览已输出则摘要不复读”的红测并实现队列摘要去重。

### R3 收口（全量门禁 + managed 实跑 + main 集成 + dev_tasks DONE）
- Context:
  - 文案统一后，队列模式仍会出现“实时预览已输出 exit，摘要再次输出 exit”的复读。
  - 里程碑要求队列模式下关键工具线层次稳定，可读且不重复。
- Decision:
  - 先在 unit+integration 把 `bash exit` 断言改为“仅出现 1 次”形成红测。
  - 在 `send_message_with_async_events` 路径记录实时已输出的工具关键线，并在 `_build_repl_view` 后过滤同一标识的摘要项。
  - 过滤时统一归一化 `Tool:`/`Tool ` 前缀，按“工具线语义”去重，不影响 `Assistant/State/Usage` 主摘要。
- Rationale:
  - 只过滤“已实时展示”的工具线，能精确消除复读，同时保留进度聚合（如 chunks）等未预览信息。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py -k "dedupes_replayed_tool_start_without_event_id or streams_started_running_chunk_and_exit_for_tool_execution or streams_started_running_chunk_and_exit_for_bash_tool"` -> `3 failed`（`Tool: ... exit` 均出现 2 次）。
    - 绿测：同命令 -> `3 passed`。
    - Follow-up 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py -k "changed_event_id"` -> `1 failed`（同内容但不同 `event_id` 回放导致 `Tool: ... start` 出现 2 次）。
    - Follow-up 绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py -k "changed_event_id or dedupes_replayed_tool_start_without_event_id or streams_started_running_chunk_and_exit_for_tool_execution or streams_started_running_chunk_and_exit_for_bash_tool or uses_async_events_with_run_filter_and_dedup"` -> `5 passed`。
    - 门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py` -> `105 passed, 42 warnings`。
  - Entry:
    - 队列 REPL 下 `Tool: ... exit` 仅输出一次；摘要不再复读实时已输出关键线。
- Rollback:
  - `54c2000`（R3 红测提交）
- Commits:
  - R3.1: C1=`54c2000`, C2=`a16f009`, C3=`78300d2`
  - R3.2: C1=`1fe36fc`, C2=`6d0a7b3`, C3=`本提交`
- Next:
  - 执行 managed CLI 实跑留证，随后 rebase/merge/push 与 dev_tasks DONE 更新。
