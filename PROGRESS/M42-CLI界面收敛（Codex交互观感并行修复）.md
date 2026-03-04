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
  - M40 的异步队列将后台结果直接写到同一终端流，和 `repl_input.render_interactive_line` 的 ANSI 行编辑并发时会产生错位与菜单残影。
  - `tool_end`/`text_delta` 预览未单行化，遇到多行文本会直接把换行注入 REPL，形成大段缩进噪声。
- Decision:
  - 在 `repl_input` 增加全局渲染锁与活动提示行快照，并新增 `emit_external_text`：外部输出前清理编辑行，输出后自动重绘当前提示行。
  - `commands._run_repl` 的后台队列输出路径改为通过 `emit_external_text` 注入，避免与输入光标竞争。
  - `repl_events._preview_event_value` 统一把 `\\r/\\n` 归一并转义为 `\\n`，确保预览永远单行。
- Rationale:
  - 只改 CLI 显示链路即可消除错位与缩进问题，不触碰内核协议。
  - 后台输出统一走安全注入口，能在保持“运行中可继续输入”前提下稳定终端表现。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_repl_input_external_output_replays_prompt_without_layout_break tests/unit/test_cli_main.py::test_send_message_with_async_events_sanitizes_multiline_tool_preview`（2 failed）
    - 绿测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_repl_input_external_output_replays_prompt_without_layout_break tests/unit/test_cli_main.py::test_send_message_with_async_events_sanitizes_multiline_tool_preview tests/unit/test_cli_main.py::test_run_cli_repl_queues_user_input_while_previous_async_run_is_in_progress`
    - 全绿：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_refactor_boundaries.py tests/unit/test_sdk_client.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_cli_error_contract.py`（94 passed, 38 warnings）
  - Entry:
    - 多行 `tool output` 被渲染成 `line1\\nline2` 单行文本，不再拆成多行污染终端。
    - 队列线程输出结束后，提示行可被重绘，输入排队流程仍可用。
- Rollback:
  - `05f39bc`（R1 红测提交）
- Commits: C1=`05f39bc`, C2=`b2c53ed`, C3=`待提交`
- Next:
  - 进入 R2：重排 REPL 单轮摘要为答案优先、紧凑状态与工具过程。

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
