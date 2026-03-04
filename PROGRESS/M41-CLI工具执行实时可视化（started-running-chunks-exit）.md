# M41 - CLI工具执行实时可视化（started/running/chunks/exit）

## Baseline
- Test command:
  - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_sse_event_contract.py tests/unit/test_sse_encoder.py`
- Result:
  - `76 passed, 42 warnings`

### R0 可行性检查（DONE）
- Context:
  - 里程碑要求 REPL 展示工具 started/running 心跳、stdout/stderr 实时 chunk、exit code。
  - 当前 CLI 仅消费 SSE 事件 `run_status/tool_start/tool_end/text_delta/turn_end`，不改内核前只能使用这些输入。
  - 禁止在未确认前修改 `server/runs/tools/agent/core` 内核目录。
- Decision:
  - 先停止实现并回传最小内核改动清单；在主 agent 批准后再进入实现。
  - 审批后采用最小侵入路径：`tools -> hooks -> SSE -> CLI`，保持 `send-message` 单 JSON 契约不变。
- Rationale:
  - `tool_end` 事件只在工具结束后提供聚合 output，不能反映执行中增量输出。
  - `run_status` 只有 queued/running/completed 等状态快照，无法表达工具流输出片段。
- Evidence:
  - Tests:
    - `PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_sse_event_contract.py tests/unit/test_sse_encoder.py`（全绿，作为基线）
  - Entry:
    - `src/nano_multiagent/runs/registry.py` 仅发布 `tool_start/tool_end/text_delta/turn_end`。
    - `src/nano_multiagent/hooks/builtins/realtime_stream.py` 未发布 `tool_execution_update` 级别事件。
    - `src/nano_multiagent/tools/safety.py` 的 `run_command` 为一次性 `subprocess.run(..., capture_output=True)`，无 chunk 回调接口。
- Rollback:
  - 当前无代码实现提交，回滚点为 `milestone/M41` 初始基线。
- Commits:
  - C1=`N/A`, C2=`N/A`, C3=`N/A`
- Next:
  - 进入 R1.1：红测先行后打通实时事件链路。

### R1.1 started/running/chunk/exit 实时链路落地
- Context:
  - 目标是 REPL 在工具执行期间可见 started/running 心跳、stdout/stderr chunk、exit code。
  - 需要在不破坏 M40 的结构化输出与 `send-message` 单 JSON 合同前提下完成。
- Decision:
  - 在 `ToolSafety` 新增 `run_command_stream`，以回调方式发出 `phase=started|running|chunk|exit`。
  - `BashTool` 改为使用流式执行并通过 `ToolContext.emit_execution_event` 上报增量事件。
  - `ToolRegistry` 为每次工具调用注入执行事件回调，并补齐 `run_id/turn_id/call_id` 元数据。
  - `realtime_stream` 内置 hook 新增 `tool_execution_update` 映射，发布 SSE 事件：
    - `tool_exec_started`
    - `tool_exec_running`
    - `tool_exec_chunk`
    - `tool_exec_exit`
  - CLI `repl_events` 增加上述事件渲染；实时预览仅开启在 `tool_exec_*` 事件，避免把旧事件预览噪声重新打开。
- Rationale:
  - 该方案遵循既有分层，不把执行细节塞进 CLI 或 runs 聚合层，侵入面最小且可测试。
  - 实时事件与最终结构化汇总并存，兼顾执行中可见性与回合收口可读性。
- Evidence:
  - Tests:
    - 红测：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py::test_run_cli_repl_streams_started_running_chunk_and_exit_for_tool_execution tests/integration/test_cli_http_flow_integration.py::test_cli_repl_streams_started_running_chunk_and_exit_for_bash_tool tests/contract/test_sse_event_contract.py::test_global_sse_contract_returns_event_stream_frames tests/unit/test_sse_encoder.py::test_encode_sse_event_preserves_tool_exec_chunk_payload`（3 failed, 1 passed）
    - 绿测：同上（4 passed）
    - 全量门禁：`PYTHONPATH=src pytest -q tests/unit/test_cli_main.py tests/integration/test_cli_http_flow_integration.py tests/contract/test_cli_http_only_contract.py tests/contract/test_sse_event_contract.py tests/unit/test_sse_encoder.py`（79 passed, 44 warnings）
  - Entry:
    - REPL 输出可见 `[tool bash] started ...`、`running ...`、`chunk stdout/stderr ...`、`exit code=...`，且首条实时行出现在 `Status:` 汇总段前。
    - 非交互 `send-message` 仍为 stdout 单行 JSON（合同测试全绿）。
- Rollback:
  - `64dc79b`（R1.1 红测提交）
- Commits: C1=`64dc79b`, C2=`463ab8f`, C3=`TBD`
- Next:
  - 提交文档 C3，完成 Milestone 回传。
