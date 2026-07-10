# bugfix-373-M1 进度

## R1 — LLMMessage 新增字段 + loop 保留 reasoning_content

- Context: `LLMMessage` 无 `reasoning_content` 字段，loop 追加历史时只传 role/content/tool_calls，reasoning_content 在模型返回后立即被丢弃，无处存储。
- Decision: 在 `LLMMessage` 末尾新增 `reasoning_content: str | None = None`；`loop.py` 在 `_append_llm_message` 调用时把 `llm_msg.reasoning_content` 传进去；`_append_llm_message` 合并时取 `prev.reasoning_content or msg.reasoning_content`。
- Rationale: 最小侵入：只改数据模型和传递路径，不改业务语义。字段放末尾不破坏现有构造调用。
- Evidence:
  - Tests: `pytest tests/unit/test_agent_loop.py::test_loop_preserves_reasoning_content_in_tool_call_roundtrip` PASSED
  - Entry: 单元测试验证第二轮请求的 messages[2].reasoning_content 等于第一轮返回的 thinking_text
  - Frontend State Matrix: N/A（纯后端）
  - Browser QA: N/A
  - E2E/Regression: N/A（单元测试覆盖完整链路）
  - Visual/Interaction: N/A
- Rollback: 回退到 662c7b6d（R1 红测试之前）
- Commits: C1=662c7b6d, C2=47baf396
- Next: R2

## R2 — mapper 出站时回传 reasoning_content

- Context: `OpenAICompatMapper._map_message` 处理 assistant+tool_calls 时只序列化 content 和 tool_calls，不含 reasoning_content，出站请求缺少该字段导致 kimi K2.6 返回 invalid_request_error。
- Decision: 在 `_map_message` 的 `assistant+tool_calls` 分支里，当 `message.reasoning_content` 非空时把它加入 mapped dict。不加默认 None 的情况（避免多余字段）。
- Rationale: 与 claude-code `convertInternalAssistantMessage` 的 reasoning_content 处理逻辑一致：只有非空时才加进去。
- Evidence:
  - Tests: `pytest tests/unit/test_llm_openai_compat_mapper.py` 2 passed
  - Entry: 测试直接调 `mapper.map_generate_request`，验证出站 JSON 里存在/不存在 reasoning_content
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A
  - Visual/Interaction: N/A
- Rollback: 回退到 b2276729（R2 红测试之前）
- Commits: C1=b2276729, C2=11a80d71
- Next: R3

## R3 — client 流式解析 reasoning_content + contract 更新

- Context: `_stream_response` 只收集 `delta.content` 和 `delta.tool_calls`，`delta.reasoning_content` 被忽略。即使 R1/R2 把 loop 和 mapper 修好，入口处还是解析不到 reasoning_content，round-trip 整条链路还是断的。另外 `_finalize_tool_calls` 生成 LLMMessage 时也没地方放 reasoning_content。
- Decision: `_stream_response` 新增 `reasoning_buffer`，收集 `delta.reasoning_content`；flush 时把它传给 `_finalize_tool_calls(reasoning_content=...)`；`_finalize_tool_calls` 接受新参数，把它挂到第一个 tool_call 消息上（loop 的 `_append_llm_message` 合并时会保留）。同步更新 `tests/contract/test_llm_interfaces_contract.py` 的字段列表。
- Rationale: 参考 claude-code `streamAdapter.ts` 的 `delta.reasoning_content → thinking block` 映射逻辑，等效实现：先在 streaming 层收集，再在历史序列化层透传。
- Evidence:
  - Tests: `pytest tests/unit/test_openai_compat_client_streaming.py tests/unit/test_llm_openai_compat_mapper.py tests/unit/test_agent_loop.py tests/contract/test_llm_interfaces_contract.py tests/contract/test_llm_provider_contract.py` 全部 PASSED
  - Entry: 单元测试用 httpx.MockTransport 构造真实 SSE 流，验证 tool_call 消息携带 reasoning_content
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A（覆盖完整 client→loop→mapper round-trip 链路）
  - Visual/Interaction: N/A
- Rollback: 回退到 1e127148（R3 红测试之前）
- Commits: C1=1e127148, C2=e885a6d9, C3=c9ad75f2
