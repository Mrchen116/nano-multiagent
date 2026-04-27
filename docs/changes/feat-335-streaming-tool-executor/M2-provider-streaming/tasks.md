# M2-provider-streaming: Provider 流式 SSE 解析

## Goal
实现 Anthropic 和 OpenAI-compat provider 的 SSE 流式解析，在 content block 边界 yield `LLMMessage`。

## Roadpoints

### R2.1 AnthropicClient 流式 SSE 解析
- 实现 `async def generate() -> AsyncIterator[LLMMessage]`
- SSE 事件解析：`message_start`, `content_block_start`, `content_block_delta`, `content_block_stop`, `message_delta`, `message_stop`
- 在 `content_block_stop` 时 yield 完整 `LLMMessage`（含单个 content block）
- 在 `message_stop` 时 yield terminal metadata message（`content=""`, `finish_reason`, `usage`）
- **文件**: `src/agent/platform/llm/providers/anthropic/client.py`
- **验收**: `test_streaming_anthropic_client` 通过

### R2.2 OpenAICompatClient 流式 SSE 解析
- 实现 `async def generate() -> AsyncIterator[LLMMessage]`
- 缓冲 `delta.content` 到 text buffer
- 缓冲 `delta.tool_calls` 到 tool_calls buffer（index-based 累积）
- 在 `finish_reason` 到达时一次性 yield 所有累积的 content blocks + terminal metadata
- **文件**: `src/agent/platform/llm/providers/openai_compat/client.py`
- **验收**: `test_streaming_openai_client` 通过

### R2.3 通用 SSE 解析工具
- 提取 `_iter_sse_lines()` 为可复用的 async generator
- 处理 SSE 格式：`data: {...}\n\n`
- **文件**: 可新建 `src/agent/platform/llm/providers/_sse.py` 或内联在各自 client 中
- **验收**: 两个 provider 共用同一解析逻辑或各自独立但行为一致

### R2.4 契约测试
- Mock SSE 响应流，assert yield 的 `LLMMessage` 序列与预期一致
- Anthropic: text block → tool_use block → terminal metadata
- OpenAI: 多个 delta 累积 → 一个 text message + 一个 tool_calls message + terminal metadata
- **文件**: `tests/contract/test_llm_provider_contract.py`
- **验收**: 契约测试全部通过

## 验收标准
1. Anthropic mock SSE → 正确 yield 3 个 `LLMMessage`（text, tool_use, terminal）
2. OpenAI mock SSE → 正确 yield 3 个 `LLMMessage`（text, tool_calls, terminal）
3. Terminal metadata message 的 `content==""` 且 `finish_reason` 不为 None
4. `mypy` 类型检查通过
