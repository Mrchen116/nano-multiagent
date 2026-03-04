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
  - M42 仍保留 `[status]/[progress]/[tool]/[usage]` 标签式摘要和 `[tool xxx]` 事件预览，默认观感接近调试日志。
  - M43 目标是在不改内核协议前提下，把默认 REPL 改为发布态可读状态线，且保持异步 run 过滤/去重行为。
- Decision:
  - `repl_render` 输出改为 `State/Progress/Tool/Usage` 文案行，移除默认裸标签前缀。
  - `repl_events` 事件预览改为 `Tool <name> ...` / `Run <id>: ...` 文案，保留原始事件语义和字段信息。
  - `_normalize_tool_update` 兼容 `Tool ...` 与旧 `[tool ...]` 格式，避免聚合路径回归。
- Rationale:
  - 仅改 CLI 渲染层即可达成“低噪声+可读状态线”，不会影响 HTTP 契约、run_id 过滤与 event_id 去重核心行为。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_run_cli_repl_prints_turn_llm_usage_when_available tests/unit/test_cli_main.py::test_run_cli_repl_prints_compact_answer_first_summary_for_async_flow tests/unit/test_cli_main.py::test_run_cli_repl_prints_compact_error_summary_for_failed_run tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_async_run_tool_and_text_events tests/integration/test_cli_http_flow_integration.py::test_cli_repl_prints_compact_sections_in_async_turn_output tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_started_running_chunk_and_exit_for_bash_tool`（6 failed）
    - 绿测（全量门禁）：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（98 passed, 40 warnings）
  - Entry:
    - 成功流：`Assistant -> State -> Tool -> Usage`，不再出现 `[status]/[tool]/[usage]` 裸日志。
    - 失败流：`Assistant: (empty)` + `State: failed | layer=...` + `Error:` + `Hint:` + `Usage: unavailable`。
- Rollback:
  - `ca4ec09`（R1 红测提交）
- Commits: C1=ca4ec09, C2=189acff, C3=本提交（docs R1.1）
- Next:
  - 进入 R2：收敛 `/` 命令菜单交互，消除菜单刷屏和输入行污染。

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
