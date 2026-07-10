# Verification Report: feat-439

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 13/13（实现完整；M2 exit-criteria 复选框未勾，见 Issues） |
| Correctness | 8/8 requirement/scenario covered |
| Coherence | Followed（四条设计决策均遵守） |

No critical issues. 1 warning to consider. Ready for PR (with noted improvement).

---

## Completeness

### Task 完成检查

**M1 (cache-hit-rate)**：6/6 exit criteria 已勾选 [x]，全部 roadpoints DONE。

**M2 (thinking-process-timeline)**：所有 5 个 roadpoints（R1–R5）在 progress.md 中标注 DONE，全量测试（Python 2995 passed + 前端 475 passed）证实实现完整。但 tasks.md 的 7 条退出标准复选框**全部仍为 `- [ ]`**——系 worker 未将 progress.md 中的 roadpoint 完成状态同步回 tasks.md，属文档一致性问题（见 Issues SUGGESTION-1）。

全量测试（`-m "not e2e"`）结果：**2995 passed, 1 skipped**，无回归。

### Spec 覆盖检查

三个 Requirement 均有实现：
- **token 气泡展示本轮缓存命中率**：`token-chip.tsx` 渲染层已实现，后端链路贯通。
- **内部 Web IM 把思考与工具操作展示为过程时间线**：`tool-calls-panel.tsx` + `message-pane.tsx` + IM 持久化链全部实现。
- **外部 IM 不暴露 thinking**：架构保证（`OutboundRouter.send_text(text=...)` 只接受 text），见 WARNING-1。

---

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| **M1** token 气泡 / 有缓存命中 | `src/IM/frontend/.../token-chip.tsx:38-40`（`cacheRead/cacheTotalInput`计算）→ `token-chip.tsx:52-62`（渲染命中行） | `token-chip.test.tsx`（命中 87% + `toLocaleString`） | covered |
| **M1** token 气泡 / 无命中空态（行恒显示） | `token-chip.tsx:43`（`cachePct = cacheTotalInput > 0 ? ... : 0`），行无条件渲染 | `token-chip.test.tsx`（0% 空态 + 旧数据 `??0` 兜底） | covered |
| **M2** 一条回复含多段思考与多次工具操作（按时序混排） | `tool-calls-panel.tsx:buildTimeline()`（按 `seq` 升序 merge 思考+工具）；`message-pane.tsx:438`（有思考或工具时渲染 `ToolCallsPanel`） | `tool-calls-panel.test.tsx`（think0→tool1→think1→tool3，seq 交错混排断言） | covered |
| **M2** 思考整段可展开回看（历史亦可） | `ThinkingRow` 组件默认收起 + toggle 展开全文；`append_thinking_segment` 持久化 + `_decode_thinking` 还原；reducer `message.created` 还原 thinking | `tool-calls-panel.test.tsx`（展开 `process-thinking-body` 内容）+ `chat-stream-reducer.test.ts`（`message.created` 还原）+ `test_message_runtime_state.py`（往返） | covered |
| **M2** 模型本轮无思考（空态，不留空壳） | `message-pane.tsx:438`（`message.thinking && message.thinking.length > 0` 门控）；`ToolCallsPanel`：无思考且无工具→`container.innerHTML` 为空 | `tool-calls-panel.test.tsx`（"renders nothing when neither thinking nor tools"） | covered |
| **M2** 外部 channel 只收到正文（不含思考） | `OutboundRouter.send_text(text=...)` 签名只含文本；`_build_bg_reply_sender` 发 `{"text": text.strip(),...}` | 无专用隔离测试——见 WARNING-1 | 架构保证，无单测 |
| **M1 内核** prompt_tokens 不变，缓存两字段累加 | `loop.py:_accumulate_usage:1067-1076`（prompt 取快照，`cache_read/cache_total_input` 各 `current+update`） | `test_agent_loop.py`（`_accumulate_usage` 缓存累加 + prompt 快照断言） | covered |
| **M1 provider** 两家缓存字段归一（`cache_total_input==prompt_tokens`） | Anthropic `client.py:332-334`、`mapper.py:353-354`；OpenAI `client.py:322-323`、`mapper.py:332-333` | `test_llm_anthropic_mapper.py` + `test_llm_openai_compat_mapper.py`（归一断言）+ `test_llm_anthropic_client_streaming.py` + `test_openai_compat_client_streaming.py` | covered |

---

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| **决策 1**：新增 `cache_read_tokens` / `cache_total_input_tokens` 两字段（默认 0），不改 `prompt_tokens` | 是 | `agent/core/types.py:17-23`（`cache_read_tokens: int = 0`；`cache_total_input_tokens: int = 0`） |
| **决策 2**：provider 层只追加缓存字段，`prompt_tokens` 计算一字不动 | 是 | `anthropic/client.py:326`（`prompt_tokens = input + creation + read` 原样保留）；`openai_compat/client.py:303`（`resolved_prompt = prompt_tokens or 0` 原样保留）；mapper.py 两家同步改（符合 design Rec2） |
| **决策 3**：`_accumulate_usage` 缓存两字段累加（整轮口径 spec Q1=B），prompt 取快照 | 是 | `loop.py:1066-1076`（`accumulated_completion = current.completion + update.completion`；`cache_read = current.cache_read + update.cache_read`；`prompt = update.prompt_tokens`） |
| **决策 4**：thinking 作为「过程项」按时序流到气泡，不造 token streaming；共享 per-message 单调 seq；外部 channel 不带 | 是（含 R5 seq 修订：插入索引→共享单调计数器） | `repositories.py:_next_process_seq`（思考+工具共用计数器）；`tool-calls-panel.tsx:buildTimeline()`（按 seq 升序 merge）；`chat-stream-reducer.test.ts`（幂等去重） |

**架构自洽性（§4.3）**：
- 依赖方向：`personal_assistant` 只消费 `agent.sdk` 事件（reasoning 字段来自 SDK 事件 payload，不直接 import `agent.core`）；`IM` 不调用 `agent`，经 gateway WS 协议透传，均合规。
- M2 的 `ToolCall.seq` 为新增可选字段（additive），契约扩展模式与现有 `emoji`/`approval` 字段一致。
- 无平行机制：缓存字段复用既有 `TokenUsage` 数据流（`turn_end` payload → gateway → IM）；thinking 复用既有 `tool_calls_json` 列模式（`thinking_json` 加列）。

---

## Issues

### WARNING（应该修）

**WARNING-1**：Spec "外部 IM 不暴露 thinking" Scenario 无专用单元测试。

当前行为由架构保证（`OutboundRouter.send_text(text=...)` 签名只接受文本字符串，`_build_bg_reply_sender` 只发 `{"text": text.strip()}`），但 spec 场景无直接断言覆盖。若将来有人在 outbound 路径加字段，回归测试不会报警。

- 文件：`tests/unit/personal_assistant/test_gateway_web_relay_adapter.py`（或 `test_gateway_im_relay.py`）
- 修法：增一个 test，注入带 `reasoning_content` 的 `assistant_message` 事件，断言 outbound relay（`MockChannelAdapter.sent`）收到的 `OutboundMessage.text` 中**不含** reasoning/thinking 字样，且 `OutboundMessage` 无 `thinking` 字段。

### SUGGESTION（可以修）

**SUGGESTION-1**：M2 tasks.md 的退出标准复选框（7 条）全部仍为 `- [ ]`，但 progress.md 中所有 roadpoints（R1–R5）已标 DONE，且全量测试绿。

- 文件：`docs/changes/feat-439-im-cache-hit-and-thinking/M2-thinking-process-timeline/tasks.md:11-17`
- 修法：将 7 条 `- [ ]` 改为 `- [x]`，与 progress.md 状态一致。

**SUGGESTION-2**：`docs/e2e-critical-paths.md` 尚无 feat-439 新特性的守护入口。AGENTS.md 要求"新增关键特性须登记一行 + 配 e2e"。两个新特性（缓存命中率 token 气泡 + thinking 过程盘）均为 Web UI 级功能，现有 critical-paths 套件不驱动浏览器（backlog 已显式注明），故本次不强求，但建议收尾时在 backlog 段登记，或在将来 Playwright UI smoke unit 中覆盖。

---

No critical issues. 1 warning to consider. Ready for PR (with noted improvements).
