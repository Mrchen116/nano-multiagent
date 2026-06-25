# feat-434-M1 — Progress

> 实现思路与证据。每个 roadpoint 完成后追加一段。

### R1 — 内核 approval 产出链

- Context: approval 标识须从内核 gate 产出，贯穿到 tool_end 事件。deny 侧有现成 reason_code=denied 载体（ToolError.details）；allow 侧无现成载体——registry.execute 成功路径只 return model-facing output dict，无法把 approval 带到 tool_executor 构造的 success ToolResult。这是决策2 点名的「最易漏一环」。
- Decision:
  - `types.ToolResult` 加 `approval: str | None`，与 reason_code 正交（reason_code 分类非成功终态，approval 记用户决策）。
  - `auto_mode_gate._handle_ask`：allow_once/session/always → `{block:False, approval:"user_allow"}`；deny → `{block:True, reason, approval:"user_deny"}`。自动放行/自动 block 路径在此函数之前 return，不带 approval → 保持 None。
  - `runner.py` tool_call 合并分支：新增 `if "approval" in result: 透传`，block=False/True 两侧都保留（block=False 是 allow 链最易漏的）。
  - `registry.execute`：deny 把 approval 塞进 ToolError.details（与 reason_code 同源）；allow 走新增 `out_meta: dict` per-call 旁路 sink（不污染 model-facing output、并发安全），写 `out_meta["approval"]`。
  - `tool_executor`：成功路径从 exec_meta 读 approval 填 ToolResult；错误路径从 details lift（与 reason_code 并列）；finally 重建 ToolResult 时保留 approval。
  - `loop.tool_result` dispatch + `realtime_stream.tool_end` 各加一行携带 approval。
- Rationale: 选 out_meta per-call 旁路而非把 approval 混进 output dict——output 经 `tool.serialize_result` 给模型看（loop.py:669），任何 reserved key 都会泄漏给 LLM。per-call dict 又天然并发安全（StreamingToolExecutor 并发跑工具）。整条链与既有 reason_code 线对称，下游透传零新机制。
- Evidence:
  - Tests: `tests/unit/test_toolcall_approval_chain.py`（8 例）+ `test_auto_mode_gate_hook.py::TestHandleAskApprovalSignal`（4 例）+ realtime_stream tool_end approval。内核+contract 全回归 786 passed。
  - Entry: N/A（内核产出段，端到端真实入口在 R5 live 验收）
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: 内核单测落库（非 e2e）；端到端 live 在 R5
  - Visual/Interaction: N/A
- Rollback: 回退到 R1 C1 commit（红测试）
- Next: R2 — Gateway→IM 透传链
