# M1-foundation Progress

## Context
将 Agent 内核从同步模型改造为异步流式模型的基础设施层。本 milestone 只做接口和骨架调整，不改业务逻辑。

## Decisions

### R1.1 LLMClient 协议改造
- `LLMMessage` 增加 `finish_reason` 和 `usage`，用于承载 terminal metadata
- `LLMClient.generate()` 返回 `AsyncIterator[LLMMessage]`，废弃 `LLMGenerateResponse`
- 移除 `LLMGenerateRequest.stream`，始终流式

### R1.2 ToolRegistry 异步化
- `execute()` 改为 `async def`
- `_dispatch_intercept()` / `_dispatch_observe()` 改为 `async def`，移除 `asyncio.run()`
- `tool.run()` 用 `asyncio.to_thread()` 包装，保持工具实现同步不变
- `execution_event_callback` 改为内部队列累积模式：tool.run() 期间同步写入队列，run 完成后批量 flush dispatch

### R1.3 Provider HTTP 异步化
- `httpx.Client` → `httpx.AsyncClient`
- `generate()` 改为 `async def`，但 M1 仍是 placeholder（同步请求后 yield 单条 message），M2 改为真 SSE

### R1.4 RetryingLLMClient 适配
- `generate()` 改为 `async def`，用 `async for` 消费内层 generator
- `time.sleep` → `asyncio.sleep`
- 重试时重新创建 generator，已 yield 的 chunks 不回溯

## Rationale
- `asyncio.to_thread()` 避免重写所有工具的同步实现
- 队列累积模式解决 `execution_event_callback` 同步签名与 async dispatch 的矛盾
- Provider placeholder 让 M1 可独立验证，M2 再改 SSE 解析

## Evidence
- `python -c "from agent.core.llm.interfaces import ...; ..."` 导入成功
- `pytest tests/unit/test_agent_runtime.py` 7 passed
- `pytest tests/unit/test_agent_loop.py` 8 passed
- `pytest tests/unit/ -k "tool"` 107 passed
- `pytest tests/unit/ -k "llm"` 34 passed

## Rollback
如需回滚，恢复 5 个文件的修改即可。无数据库/schema 变更。
