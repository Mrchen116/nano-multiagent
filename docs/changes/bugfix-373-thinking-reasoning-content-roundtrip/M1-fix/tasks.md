# bugfix-373-M1: reasoning_content round-trip 修复

## 目标

让 agent loop 在把 assistant tool-call 轮落进会话历史、再回传给模型时，保留并 round-trip 它的 reasoning_content。
修复后：开 thinking 的模型（如 kimi K2.6）工具调用完成后能继续推理并产出文字总结，不再被上游以 "reasoning_content is missing" 拒绝。

## 退出标准

1. `LLMMessage` 新增 `reasoning_content: str | None` 字段
2. `OpenAICompatClient._stream_response` 从 `delta.reasoning_content` 收集并填充该字段
3. `loop.py` 把 assistant 消息追加到 `llm_messages` 时保留 `reasoning_content`
4. `OpenAICompatMapper._map_message` 出站时把 `reasoning_content` 放回 assistant 消息
5. 新增集成测试：开 thinking + 走完一次工具调用 + 工具结果回传，验证 reasoning_content round-trip

## 测试策略

- R1：`tests/unit/test_agent_loop.py::test_loop_preserves_reasoning_content_in_tool_call_roundtrip` — 验证 loop 第二轮回传携带 reasoning_content
- R2：`tests/unit/test_llm_openai_compat_mapper.py` 两个测试 — 验证 mapper 出站 reasoning_content 行为
- R3：`tests/unit/test_openai_compat_client_streaming.py::test_stream_response_parses_reasoning_content` — 验证 SSE streaming 解析
- 附：`tests/contract/test_llm_interfaces_contract.py` — 更新了 LLMMessage 字段合约

测试类型：单元 + contract，无需浏览器验收（纯后端修复）。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | LLMMessage 新增字段 + loop 保留 reasoning_content | DONE |
| R2 | mapper 出站时回传 reasoning_content | DONE |
| R3 | client 流式解析 reasoning_content + contract 更新 | DONE |
