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

- R1 C1：在 `tests/unit/test_agent_loop.py` 中新增测试，验证 loop 在 assistant tool-call 轮能保留 reasoning_content，第二轮回传时消息里有 reasoning_content（当前失败）
- R2 C1：在 `tests/unit/test_openai_compat_mapper.py` 中验证 `_map_message` 把 reasoning_content 放回出站消息（当前失败）  
- R3 C1：在 `tests/integration/test_openai_compat_generation_integration.py` 中新增流式 SSE 测试，验证 `delta.reasoning_content` 被解析进 LLMMessage（当前失败）

测试类型：单元 + 集成，无需浏览器验收（纯后端修复）。

## Roadpoints

| ID | 标题 | 状态 |
|---|---|---|
| R1 | LLMMessage 新增字段 + loop 保留 reasoning_content | TODO |
| R2 | mapper 出站时回传 reasoning_content | TODO |
| R3 | client 流式解析 reasoning_content + 集成测试 | TODO |
