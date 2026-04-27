# M1-foundation: 基础设施异步化

## Goal
完成所有同步→异步的接口改造，为流式消费奠定基础。本 milestone 不改任何业务逻辑，只做接口和骨架调整。

## Roadpoints

### R1.1 LLMClient 协议改造
- `LLMMessage` 增加 `finish_reason: str | None = None` 和 `usage: TokenUsage | None = None`
- `LLMClient.generate()` 返回类型改为 `AsyncIterator[LLMMessage]`
- 移除 `LLMGenerateRequest.stream` 字段
- 移除 `LLMGenerateResponse` 同步返回类型
- **文件**: `src/agent/core/llm/interfaces.py`
- **验收**: `mypy` 全过，无类型错误

### R1.2 ToolRegistry 异步化
- `ToolRegistry.execute()` 改为 `async def execute()`
- `_dispatch_intercept()` / `_dispatch_observe()` 改为 `async def`，内部 `await hook_runner`
- 移除所有 `asyncio.run()` 调用
- `tool.run()` 同步执行用 `asyncio.to_thread()` 包装
- **文件**: `src/agent/core/tools/registry.py`
- **验收**: 现有调用点编译通过（可能暂时 broken，后续 milestone 修复）

### R1.3 Provider HTTP 异步化
- `AnthropicClient` 和 `OpenAICompatClient` 改用 `httpx.AsyncClient`
- 移除 `if request.stream: raise ...`
- 先保持同步返回（placeholder `async def generate` 但内部仍调用同步 API），等 M2 再改 SSE
- **文件**: `src/agent/platform/llm/providers/anthropic/client.py`, `openai_compat/client.py`
- **验收**: 类型检查通过

### R1.4 RetryingLLMClient 适配
- `generate()` 改为 `async def`，返回 `AsyncIterator[LLMMessage]`
- `time.sleep` → `asyncio.sleep`
- 重试时重新调用 `self._inner.generate()` 创建新 generator
- **文件**: `src/agent/core/llm/retry.py`
- **验收**: 单元测试通过

### R1.5 LLM Factory 适配
- 适配 async client 创建逻辑
- **文件**: `src/agent/core/llm/factory.py`
- **验收**: 类型检查通过

## 验收标准
1. `mypy src/agent/core/llm/` 无错误
2. `mypy src/agent/core/tools/` 无错误
3. `pytest tests/unit/test_llm_retry.py` 通过（如存在）
4. 所有修改文件 `import` 和基础类型检查通过
