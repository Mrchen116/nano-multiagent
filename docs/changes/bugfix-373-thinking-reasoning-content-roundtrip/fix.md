# bugfix-373: 主 agent 开 thinking 后,历史回传丢失 assistant tool-call 的 reasoning_content,工具执行后整轮停下

## Relations

- Related: bugfix-366（引入 thinking 时未让历史 round-trip reasoning_content）
- Related: bugfix-369（同一 thinking 连带问题的另一面：门禁分类器；#369 修复后才暴露本 bug）

## 原始报告

用户在 PA 聊天里反复观察到 agent "做了一些工具调用就结束了 / 拿到工具结果之后停下来了":

> http://127.0.0.1:8011/chat/a43e2465... 怎么停下来了，怎么他拿到工具结果之后停下来了？

> 还是和之前一样，做了一些工具调用就结束了。

（第二次是在 bugfix-369 门禁修复已生效、worktree 内核确认放行工具之后复现的，排除门禁因素。）

## 现象 / 复现

PA 聊天里,agent 调用一个工具(如 `bash`)、工具**执行成功完成**后,本该把工具结果回传给模型做下一步推理 / 文字总结,但整轮在这里**戛然而止**:agent 不再产出任何文字,会话结束。用户看到"做了工具调用就停了,没有最终回复"。

**复现链路**(worktree 内核 + kimi K2.6 + 主 agent thinking 开启,LLM proxy 日志 `logs/session/2026-05-20_11-32-10_374_sess_442ac3ad7289d184/`):

1. 用户发"请运行 pwd 和 ls -la"。
2. 主循环第 1 轮:模型返回 `bash: pwd && ls -la` 工具调用(`finish_reason=tool_calls`)。
3. 门禁放行(bugfix-369 已修),`bash` 执行 **completed**,无 ask。
4. 主循环第 2 轮(把工具结果回传):请求被上游**直接拒绝**:
   ```
   {"type":"error","error":{"type":"invalid_request_error",
    "message":"thinking is enabled but reasoning_content is missing in assistant tool call message at index 2"}}
   ```
5. 该轮返回空 content、`finish_reason=stop` → agent loop 收到空响应 → 整轮结束,无文字总结。

核对失败请求体确认:`thinking: {type: adaptive}` 开启,而历史里那条带 `tool_use` 的 assistant 消息既无 thinking 块、也无 `reasoning_content` 字段:

```
[0] role=user      tool_use=False
[1] role=assistant tool_use=True   thinking_block=False  reasoning_content=None   ← 缺失,被上游拒
[2] role=user (tool_result)
```

**触发条件**:主 agent 用带 thinking 的模型(kimi K2.6,`thinking: adaptive`)+ 任意一次工具调用。即"开 thinking + 用工具"必现,是 PA / coding 两个产品共性路径。

## 根因

kimi K2.6(及同类上游)在 `thinking` 开启时,有一条强约束:**回传的对话历史里,每条带 tool_call 的 assistant 消息都必须携带它当时产出的 `reasoning_content`(thinking 块)**——否则请求被判 `invalid_request_error`。

bugfix-366 给主 agent 开 thinking 时,只在**出站请求**加了 `thinking: adaptive`,但 agent loop 的**历史序列化**没有同步跟进:模型返回的 assistant 轮里带的 `reasoning_content` / thinking 块在落进会话历史、再回传给模型时被丢弃了。于是只要发生过一次工具调用,下一轮把"assistant(tool_use) + tool_result"回传时,那条 assistant 消息缺 `reasoning_content`,整个请求被上游拒,工具结果永远喂不回模型 → agent 停在工具调用之后。

**为什么这种错能进来**:

- bugfix-366 的关注点是"让主 agent 会推理"(出站开 thinking),把 thinking 当成一个单向的请求参数,没意识到它对**历史回传**有对称的格式要求(reasoning_content 必须 round-trip)。
- 开 thinking 前,历史里 assistant 消息从来没有 reasoning_content 这个维度,序列化路径自然不保留它;开 thinking 后这个维度才出现,而保留逻辑没补。
- 没有"开 thinking + 走完一次工具调用"的端到端测试 —— 单测多在不开 thinking 或不带工具的路径上,正好绕开这条必现链路。
- 现象长期被 bugfix-369 的门禁 fail-closed 掩盖:门禁先在工具调用前就 ask/卡住,根本走不到"工具执行完回传"这一步,所以这条更深的 round-trip 缺陷直到 #369 修好放行工具后才暴露。

## 修复

三处改动，构成完整 round-trip 链路：

**1. `src/agent/core/llm/interfaces.py`（47baf396）**

`LLMMessage` 新增 `reasoning_content: str | None = None` 字段，使整个数据模型能承载 thinking 块文本。

**2. `src/agent/core/agent/loop.py`（47baf396）**

- `_append_llm_message` 追加/合并时保留 `reasoning_content`（取 `prev.reasoning_content or msg.reasoning_content`）
- 调用处把 `llm_msg.reasoning_content` 传进新建的 `LLMMessage`

**3. `src/agent/platform/llm/providers/openai_compat/mapper.py`（11a80d71）**

`_map_message` 在序列化 `assistant+tool_calls` 消息时，若 `message.reasoning_content` 非空则写入出站 JSON 的 `reasoning_content` 字段。

**4. `src/agent/platform/llm/providers/openai_compat/client.py`（e885a6d9）**

`_stream_response` 新增 `reasoning_buffer`，收集 `delta.reasoning_content`；flush 时通过 `_finalize_tool_calls(reasoning_content=...)` 挂到生成的第一个 tool_call LLMMessage 上。

**同步更新 contract**（c9ad75f2）：`tests/contract/test_llm_interfaces_contract.py` 更新 `LLMMessage` 字段列表 + `LLMGenerateRequest.extra_body`（已有字段但 contract 未更新）。

## 验证

**自动化测试（全部新增，全绿）：**

```
tests/unit/test_agent_loop.py::test_loop_preserves_reasoning_content_in_tool_call_roundtrip
  → 验证开 thinking 后 loop 第二轮请求中 assistant 消息携带 reasoning_content

tests/unit/test_llm_openai_compat_mapper.py::test_map_message_assistant_with_tool_calls_and_reasoning_content
  → 验证 mapper 出站时把 reasoning_content 放回 assistant+tool_calls 消息

tests/unit/test_llm_openai_compat_mapper.py::test_map_message_assistant_without_reasoning_content_omits_field
  → 验证不带 thinking 时出站不多余地加 reasoning_content

tests/unit/test_openai_compat_client_streaming.py::test_stream_response_parses_reasoning_content
  → 用 httpx.MockTransport 构造 SSE 流验证 delta.reasoning_content 被解析到 LLMMessage.reasoning_content
```

**覆盖的必现路径：** "开 thinking + 一次工具调用 + 工具结果回传" —— 这正是 fix.md 现象段描述的必现链路，修前 loop 第二轮被拒，修后完整 round-trip 通过。

**命令：**
```bash
pytest tests/unit/test_agent_loop.py tests/unit/test_llm_openai_compat_mapper.py tests/unit/test_openai_compat_client_streaming.py tests/contract/test_llm_interfaces_contract.py tests/contract/test_llm_provider_contract.py -q
# 结果：全部 PASSED（37+ tests）
```

## 修复（补）—— 改错 provider 的二次修正

PR #38 合并后做 e2e 复现，缺陷**依然存在**：follow-up 请求仍被上游以
`thinking is enabled but reasoning_content is missing in assistant tool call message` 拒绝。

**二次根因：改错了 provider。** `kimiCoding:K2.6` 在 `model_registry.py` 是 `provider="anthropic"`，
运行时走 **anthropic** provider，而 PR #38 的 round-trip 修复全部落在 **openai_compat** provider
（client + mapper），运行时根本不经过那条路径。单测只覆盖 openai_compat 且无真 e2e，所以绿测掩盖了缺陷。
anthropic provider 里：

- `anthropic/client.py:_stream_response` 在 `content_block_stop` 时显式丢弃 `thinking` / `redacted_thinking` 块，reasoning_content 在源头就被扔掉。
- `anthropic/mapper.py:_map_message` 序列化 assistant 消息时不产出 thinking 块。

**真实修复**（anthropic provider，对称于已有的 openai_compat 修复 + 复用 #38 的 `LLMMessage.reasoning_content` 字段与 loop 合并逻辑）：

1. **`anthropic/client.py`**：`_stream_response` 用 `turn_reasoning` 累积本轮 thinking 块文本，挂到该轮**每一个** tool_use / text 块上。
   关键点：一个 assistant 轮可能返回 thinking + **多个** tool_use（共享一个 thinking 块），loop 之后把它们拆成多条独立 assistant 消息，kimi 要求**每条** tool-call 消息都带 reasoning_content，故不能只挂第一个。
2. **`anthropic/mapper.py`**：`_map_message` 在 assistant 消息 `reasoning_content` 非空时，把 `{"type":"thinking","thinking":...,"signature":""}` 块**置于 content 数组最前**（Anthropic 要求 thinking 块在前），对称回写。
3. 顺手补 `anthropic/client.py` 缺失的 `Mapping` / `Any` import（`isinstance(raw_input, Mapping)` 的潜在 NameError）。

**e2e 验证（worktree 内核 + 真实 kimi K2.6 + PA 聊天）：**

- 发"请运行 pwd 和 ls -la,然后用一句话总结"——agent 执行工具后**产出文字总结**（修前在此处停下、无输出）。
- LLM proxy 日志确认 follow-up 请求里**两个** tool_use 消息均带 thinking 块、全程**无** `invalid_request_error`。

新增 anthropic provider 测试（锁住运行时路径）：

```
tests/unit/test_llm_anthropic_client_streaming.py
  ::test_stream_response_carries_thinking_into_tool_call           单 tool_use round-trip
  ::test_stream_response_shares_thinking_across_parallel_tool_calls 多 tool_use 共享 thinking（二次根因）
  ::test_stream_response_omits_reasoning_when_no_thinking_block     无 thinking 不臆造
tests/unit/test_llm_anthropic_mapper.py
  ::test_map_message_assistant_tool_call_round_trips_thinking_block thinking 块出站置顶
  ::test_map_message_assistant_without_reasoning_omits_thinking_block
```
