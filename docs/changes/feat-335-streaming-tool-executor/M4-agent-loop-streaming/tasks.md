# M4-agent-loop-streaming: AgentLoop 流式消费改造

## Goal
改造 `AgentLoop.run()` 为流式消费 `LLMMessage`，集成 `StreamingToolExecutor`，并处理所有周边适配。

## Roadpoints

### R4.1 AgentLoop 流式消费
- `run()` 改为 `async def run(...) -> AsyncIterator[Message]`
- 流中消费 `LLMMessage`，每完成一个 content block yield 一个 `Message(role="assistant")`
- 检测到 terminal metadata message（`content==""`, `finish_reason`）时提取元数据，不 yield Message
- `message_start` / `message_update` / `message_end` hook 在每个 assistant Message yield 时触发
- `tool_call` hook 在 `add_tool()` 时触发
- `tool_result` hook 在 yield tool message 前触发
- **文件**: `src/agent/core/agent/loop.py`
- **验收**: `test_agent_loop_streaming` 通过

### R4.2 相邻 Assistant Message 合并
- `build_prompt_messages()` 中合并相邻 `role="assistant"` 的 `LLMMessage` 为一个（多 content blocks）
- **文件**: `src/agent/core/agent/prompting.py`
- **验收**: `test_merge_adjacent_assistant` 通过

### R4.3 Runtime 适配
- `_execute_loop()` 改为流式消费 async iterator
- `build_turn_result()` 适配多 block assistant message
- `_call_hook_model()` 改为 `async def`，手动消费 async iterator 组装完整结果
- `AgentContextFork` 适配 async iterator 消费
- **文件**: `src/agent/core/agent/runtime.py`
- **验收**: `test_agent_runtime` 通过

## 验收标准
1. FakeLLMClient yield 多 LLMMessage → AgentLoop yield 正确 Message 序列
2. `message_start`/`update`/`end` 在每个 content block 边界触发一次
3. `tool_call` 在 add_tool 时触发，`tool_result` 在 yield tool message 前触发
4. `build_prompt_messages()` 合并相邻 assistant 为多 content blocks
5. `_call_hook_model()` 正确消费 async iterator 并组装结果
