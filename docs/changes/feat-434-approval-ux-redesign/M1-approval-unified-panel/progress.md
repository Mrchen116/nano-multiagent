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

### R2 — Gateway→IM approval 透传链

- Context: 内核 tool_end 已带 approval（R1）。下半程把它逐字透传到前端可读：照 feat-425 emoji 模板的 5 点 + Gateway 1 点。approval 在内核 tool_end 是顶层字段（同 reason_code），不在 presentation 里。
- Decision:
  - Gateway `main.py` tool_end：`approval = event.get("approval")`（顶层，同 reason_code），拼进 tool_call payload `"approval": approval`（与 reason 并列，None 也带）。
  - IM `domain.ToolCall.approval` 字段；`gateway_handler._parse_tool_call` 解析；`event_types.tool_call_to_dict` WS 序列化（None 省略，同 emoji）；`repositories._tool_call_to_dict`/`_decode_tool_calls` 落库往返；`messages.ToolCallPayload` + `to_message_response` REST 历史序列化。
- Rationale: 与 emoji/reason 同款逐字透传，零新机制；WS/persist 层 None 省略保持 payload 干净，前端读 undefined 兜底（历史行不显闸门）。REST 历史也带 approval → 页面 reload 后「已授权/已拒绝」不丢（与 bugfix-410 reason 同动机）。
- Evidence:
  - Tests: `test_tool_call_detail.py` approval vertical（7 例：parse/to_dict/completed_payload/encode-decode/legacy/persist）+ `test_tool_end_detail_passthrough.py` Gateway approval（2 例）。IM+PA+contract 全回归 837 passed/1 skipped；ruff 全过。
  - Entry: N/A（透传段，端到端真实入口在 R5）
  - Frontend State Matrix / Browser QA / Visual: N/A
  - E2E/Regression: IM 单测 + persist round-trip 落库；端到端 live 在 R5
- Rollback: 回退到 R2 C1 commit
- Next: R3 — 前端数据 + 行内呈现（闸门/结果分区 + denied 去重 + failTag i18n + 分项计数）

### R3 — 前端行内闸门区 + 结果分区 + denied 去重 + failTag i18n + 分项计数

- Context: approval 已到前端 type（R1+R2）。本 R 实现读 approval 的呈现：闸门区/结果区分区、denied 去重、失败文案 i18n、收起态分项计数。决策4 把 denied 从「行尾 reason 徽标」迁到「闸门区 verdict」。
- Decision:
  - `chat-types.ToolCall.approval` + `ToolApproval` 类型。
  - `tool-presentation`: 新 `gateVerdict(call)`（读 approval；历史 denied 行 reason==="denied" 回退 deny）/ `isNotExecuted`（deny → 结果区「未执行」）；`failTag(call, t)` 改 i18n（`toolFailExit`={{code}} / `toolFailGeneric`），denied/非denied-reason 时 suppress；`REASON_BADGE_NAMES` 去掉 "denied"（避免与闸门区双印）。
  - `ToolCallRow`: 名称右侧渲闸门区（`chat-tool-call-gate--allow/deny` → 已授权/已拒绝）；结果区行尾 = 未执行（denied）/ failTag / 非denied reason 徽标 / 耗时；reasonKey 显式排除 "denied"。
  - `ToolCallsPanel`: 收起态后缀 `K 次授权 · X 允许 · Y 拒绝`（绿/红点 `chat-tool-calls-dot--allow/deny`，仅非零分项；空态无后缀），承载 bugfix-367 审计计数。
  - i18n: zh/en 各加 toolGateAllowed/Denied、toolNotExecuted、toolFailExit、toolFailGeneric、toolApprovalCount/Allow/Deny。
- Rationale: gateVerdict 历史行回退保证旧 denied 行不破（无 approval 字段也显已拒绝）；failTag 接 t() 修掉 spec Q6 漏接 i18n 缺口；分项计数代替旧「已决卡墙」保住审计可见性（决策3 风险）。
- Evidence:
  - Tests: tool-calls-panel.test.tsx 新增 13 例（闸门 allow/deny、授权后失败两区并存、denied 去重 + 未执行、历史 denied 回退、非denied reason 留结果区、auto-allow 无闸门、failTag zh/en 退出码与 generic、分项计数 only 非零/空态）+ 改 2 旧 denied 用例为决策4 后行为。前端全套 461 passed（+11）；tsc clean。
  - Entry: N/A（呈现层组件测试；真实浏览器入口在 R5）
  - Frontend State Matrix: default（无闸门）/error（授权后失败两区）/permission denied（闸门已拒绝+未执行）/empty（无后缀）/missing data（历史行回退）已覆盖；loading/mobile 在 R5 浏览器验收
  - Browser QA: R5
  - E2E/Regression: 组件 regression 落库
  - Visual/Interaction: CSS 在 R4，浏览器对照原型在 R5
- Rollback: 回退到 R3 C1 commit
- Next: R4 — 合一气泡（message-pane pending 入气泡、删气泡外卡、permission-card 删 resolved）+ global.css 样式对齐原型
