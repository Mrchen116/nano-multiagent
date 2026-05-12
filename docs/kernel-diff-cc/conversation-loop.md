# 对话循环与流式处理 —— nano-multiagent vs Claude Code

> 对比维度：agent 核心循环架构、流式处理、工具执行并发模型、错误恢复

---

## 1. 核心循环架构

### Claude Code

CC 的对话循环是**三层架构**：

```
REPL.tsx (UI层)
  └── onQueryImpl()
        └── for await (event of query({...}))   ← AsyncGenerator 链
              └── query.ts: queryLoop()
                    └── while (true) { ... }
                          └── deps.callModel() → claude.ts: queryModelWithStreaming()
                                └── anthropic.beta.messages.create({ stream: true })
```

- `query()` 是 `async function*`，通过 `yield` 逐条产出事件
- `queryLoop()` 内是 `while (true)` 循环，每次迭代代表一次 API 调用
- 状态通过不可变的 `State` 对象传递，带 `transition` 字段记录继续原因
- 两条消费路径：REPL 直接消费 `query()`；SDK/print 通过 `QueryEngine.submitMessage()` 包装

**关键代码**：`src/query.ts:218-238`（query 入口），`src/query.ts:240-1732`（queryLoop）

### nano-multiagent

Nano 的对话循环是**两层架构**：

```
AgentRuntime.run() (编排层)
  └── AgentLoop.run() (循环层)
        └── while True:
              └── self._llm_client.generate(LLMGenerateRequest(stream=False))
              └── 如果有 tool_calls → ToolExecutor.execute()
              └── 继续循环
```

- `AgentRuntime` 负责 session 管理、hook 调度、compaction
- `AgentLoop` 负责单次 turn 的 while 循环
- 无 AsyncGenerator，返回 `TurnResult` 对象
- `RunController` 提供 round-boundary 消息注入和中断信号

**关键代码**：`src/agent/core/agent/runtime.py:107-314`，`src/agent/core/agent/loop.py:85-411`

---

## 2. 流式处理 (Streaming)

### Claude Code —— 完整流式链

| 层级 | 流式能力 | 实现 |
|------|---------|------|
| API 层 | `anthropic.beta.messages.create({ stream: true })` | `src/services/api/claude.ts:1823` |
| 事件处理 | `for await (const part of stream)` 处理 6 种事件类型 | `src/services/api/claude.ts:1941-2300` |
| 中间层 | `query()` 通过 `yield message` 透传 | `src/query.ts:708-866` |
| UI 层 | `onQueryEvent(event)` 实时更新 `streamingText` | `src/screens/REPL.tsx:2750-2860` |
| 工具层 | `StreamingToolExecutor` 在流式返回时就开始执行工具 | `src/query.ts:562` |

**6 种流式事件**：`message_start`, `content_block_start`, `content_block_delta`, `content_block_stop`, `message_delta`, `message_stop`

**StreamingToolExecutor**：在 API 流式返回 `tool_use` content block 时，不等流结束就通过 `addTool()` 启动工具执行，`getCompletedResults()` 获取已完成结果。

### nano-multiagent —— 完全非流式

```python
# src/agent/platform/llm/providers/anthropic/client.py:45-49
if request.stream:
    raise ModelError("streaming generation is not implemented yet", retryable=False)
```

- `LLMGenerateRequest.stream: bool = False`
- `AgentLoop.run()` 中 `response = self._llm_client.generate(...)` 阻塞等待完整响应
- 无 StreamingToolExecutor，必须等完整 assistant message 返回后才执行工具
- `AgentRuntime.run()` 的 `stream: bool = True` 参数被显式 `del stream` 忽略

**缺陷**：
1. 大响应时用户无反馈，体验差
2. 工具执行无法与流式响应并行，增加总延迟
3. 无法实时展示模型"思考过程"
4. 不支持流式 UI 更新（打字机效果）

---

## 3. 工具执行并发模型

### Claude Code

两种模式：

1. **Streaming 模式（默认）**：`StreamingToolExecutor` 在流式响应时并行启动工具，收集完成结果
2. **Sequential 模式**：`runTools()` 传统顺序执行

工具结果通过 `for await (const update of toolUpdates)` 流式 yield 给上层。

### nano-multiagent

**批处理模型**：

```python
# src/agent/core/agent/tool_executor.py
batches = partition_into_batches(normalized_calls, concurrency_map)
for batch in batches:
    batch_results = await tool_executor.execute(batch, _run_one_call)
```

- `partition_into_batches`：按 `is_concurrency_safe` 将工具调用分批
- 同一 batch 内并发执行（`asyncio.gather`）
- batch 间串行执行
- 每批执行后检查 `controller.is_aborted` 中断信号

**与 CC 的差异**：
- CC 的 StreamingToolExecutor 在 API 返回过程中就开始执行，nano 必须等完整响应
- CC 的工具结果也是流式 yield 的，nano 是批处理后一次性追加
- nano 的批处理粒度较粗（按安全标记分批），CC 可以更细粒度地启动

---

## 4. 错误恢复机制

### Claude Code

| 错误类型 | 恢复策略 |
|---------|---------|
| 529 Overloaded | `FallbackTriggeredError` → 切换到 `fallbackModel` → `continue` |
| 429 Rate Limit | `withRetry` 等待 `Retry-After` 后重试 |
| 500 Server Error | 指数退避重试 |
| prompt-too-long | `reactive compact` → 压缩消息后重试 |
| max_output_tokens | 第一次升级到 64k → `continue`；后续注入恢复消息 → `continue`；超过3次则报错 |
| 流式中途失败 | 非流式降级，完成剩余部分 |

**Withheld 消息机制**：可恢复错误先暂扣不 yield，恢复成功则吞掉错误，失败才 yield 错误消息。

**恢复消息内容**：
```
"Output token limit hit. Resume directly — no apology, no recap...
Break remaining work into smaller pieces."
```

### nano-multiagent

仅有一种恢复：

```python
# src/agent/core/agent/runtime.py:275-301
try:
    turn_result = await self._execute_loop(...)
except ModelError as exc:
    if not await self._post_turn_check_overflow(session_id=session_id, error=exc):
        raise
    # 一次 compaction 后重试
    turn_result = await self._execute_loop(...)
```

- 仅处理 `context overflow` 类错误（通过 `_is_context_overflow_error` 检测）
- 一次 compaction + 一次重试
- 无模型降级、无 max_output_tokens 恢复、无 rate limit 重试
- 无 withheld 消息机制

**缺陷**：
1. 529 过载时无 fallback model 切换
2. 429/500 错误直接抛出，无重试
3. max_output_tokens 截断无恢复
4. 流式失败无降级（因为本来就不支持流式）

---

## 5. 并发控制

### Claude Code —— QueryGuard

```ts
// src/screens/REPL.tsx
const queryGuard = useRef(new QueryGuard()).current;
// idle ──tryStart()──▶ running ──end()──▶ idle
//   └── tryStart() 返回 null（已在运行）→ 新消息排入队列
```

- 状态机防止并发 API 请求
- 带 `generation` 计数防竞态（cancel+resubmit 场景）

### nano-multiagent —— RunController

```python
# src/agent/core/agent/run_control.py
class RunController:
    def __init__(self):
        self._abort = False
        self._pending: list[LLMMessage] = []
```

- 仅提供中断信号（`is_aborted`）和 pending 消息注入
- 无并发请求防护
- 如果外层同时发起两个 `AgentRuntime.run()`，会直接并发执行

---

## 6. 关键差距总结

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| 流式处理 | AsyncGenerator 全链路 | 完全不支持 | 🔴 高 |
| StreamingToolExecutor | 流式响应时并行执行工具 | 响应结束后才执行 | 🔴 高 |
| 模型降级 (529) | 自动切换 fallbackModel | 无 | 🟡 中 |
| Rate Limit 重试 | 自动退避重试 | 无 | 🟡 中 |
| max_output_tokens 恢复 | 自动升级 + 恢复消息 | 无 | 🟡 中 |
| 流式降级 | 流式失败降级非流式 | N/A | 🟢 低 |
| 并发控制 | QueryGuard 状态机 | 仅 RunController 中断 | 🟡 中 |
| Withheld 消息 | 可恢复错误先暂扣 | 无 | 🟢 低 |
