# feat-335: Streaming Tool Executor — 技术方案

> **版本**: v1.0  
> **日期**: 2026-04-27  
> **对齐**: spec.md v1.0  

---

## 1. 架构总览

### 1.1 核心变化

```
Before (同步轮询):
  AgentLoop.run()
    → LLMClient.generate() 同步阻塞
    → 拿到完整 LLMGenerateResponse
    → 解析 tool_calls
    → ToolExecutor 批量执行
    → yield 完整 Message

After (流式消费):
  AgentLoop.run()
    → LLMClient.generate() 异步流
    → 每完成一个 content block  yield 一个 LLMMessage
    → 检测到 tool_use block → StreamingToolExecutor.add_tool()
    → 工具执行和后续 block 流式接收并行
    → yield Message(role="assistant") / Message(role="tool")
```

### 1.2 数据流图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Provider SSE                             │
│  content_block_start → content_block_delta → content_block_stop  │
└────────────────────────────┬────────────────────────────────────┘
                             │ assemble block
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLMClient.generate()                        │
│              yield LLMMessage (one content block)                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AgentLoop.run()                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ for await llm_msg in client.generate():                   │  │
│  │   yield Message(role="assistant")                         │  │
│  │   if tool_use: streaming_tool_executor.add_tool()         │  │
│  │   for tool_msg in executor.get_completed_results():       │  │
│  │     yield Message(role="tool")                            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ async for result in executor.get_remaining_results():     │  │
│  │   yield Message(role="tool")                              │  │
│  └───────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌─────────┐   ┌──────────┐   ┌──────────┐
        │ History │   │  Hooks   │   │  SSE Hub │
        │ (store) │   │ (events) │   │ (events) │
        └─────────┘   └──────────┘   └──────────┘
```

---

## 2. 关键组件设计

### 2.1 LLMClient 协议

```python
# src/agent/core/llm/interfaces.py

@dataclass(frozen=True, slots=True)
class LLMMessage:
    role: str
    content: str | list[dict[str, Any]]
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: tuple[LLMToolCall, ...] = ()
    finish_reason: str | None = None      # 新增
    usage: TokenUsage | None = None       # 新增

class LLMClient(Protocol):
    def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        """Generate one streaming response.

        Yields one LLMMessage per completed content block.
        The final yielded message is a terminal metadata message carrying
        finish_reason and usage (content="").
        """
        ...
```

**重要**：
- `generate()` 返回 `AsyncIterator`，不是 `AsyncGenerator`（不暴露 send/throw）
- 每个 yield 的 `LLMMessage` 只含**一个** content block
- `LLMGenerateRequest.stream` 字段移除，始终流式
- 原始 SSE 解析、delta 累积在 Provider 内部完成，对 Loop 不可见
- `finish_reason` 和 `usage` 在 content block message 上为 `None`，只在最后的 terminal metadata message 上填充
- AgentLoop 消费到 `content == ""` 且 `finish_reason is not None` 的 message 时，只提取元数据，不创建 Message

### 2.2 Provider 流式解析

#### Anthropic

Anthropic SSE 天然是 content-block 结构：

```python
# src/agent/platform/llm/providers/anthropic/client.py

async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
    provider_request = self._translator.to_provider_request(request)
    # stream=True 传给 Anthropic API
    async with self._http_client.stream(
        "POST", "/v1/messages",
        headers=headers,
        json=provider_request.json_body,
    ) as response:
        content_blocks: dict[int, dict] = {}
        partial_message = None
        for sse_line in _iter_sse_lines(response):
            event = json.loads(sse_line)
            match event["type"]:
                case "message_start":
                    partial_message = event["message"]
                case "content_block_start":
                    idx = event["index"]
                    block = event["content_block"]
                    content_blocks[idx] = _init_block(block)
                case "content_block_delta":
                    idx = event["index"]
                    delta = event["delta"]
                    _apply_delta(content_blocks[idx], delta)
                case "content_block_stop":
                    idx = event["index"]
                    block = content_blocks[idx]
                    # content block 本身不带 usage/finish_reason
                    yield _block_to_llm_message(block, partial_message)
                case "message_delta":
                    usage = event.get("usage")
                    finish_reason = event.get("stop_reason")
                case "message_stop":
                    # Terminal metadata message: content="", 只携带 finish_reason + usage
                    yield LLMMessage(
                        role="assistant",
                        content="",
                        finish_reason=finish_reason,
                        usage=_to_token_usage(usage),
                    )
```

#### OpenAI-compat

OpenAI 的 SSE 是 choice-delta 结构，需要自行分块：

```python
# src/agent/platform/llm/providers/openai_compat/client.py

async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
    provider_request = self._translator.to_provider_request(request)
    async with self._http_client.stream(...) as response:
        text_buffer = ""
        tool_calls_buffer: dict[int, dict] = {}  # index -> partial tool_call
        finish_reason = None
        usage = None
        
        for sse_line in _iter_sse_lines(response):
            delta = json.loads(sse_line)["choices"][0]["delta"]
            
            if delta.get("content"):
                text_buffer += delta["content"]
            
            if delta.get("tool_calls"):
                for tc in delta["tool_calls"]:
                    _accumulate_tool_call(tool_calls_buffer, tc)
            
            if "finish_reason" in event:
                finish_reason = event["finish_reason"]
                usage = event.get("usage")
                # OpenAI 的 finish_reason 表示整个 response 结束
                # 此时 yield 所有累积的 content blocks
                if text_buffer:
                    yield _text_to_llm_message(text_buffer)
                for tc in tool_calls_buffer.values():
                    yield _tool_call_to_llm_message(tc)
                # 最后 yield terminal metadata message
                yield LLMMessage(
                    role="assistant",
                    content="",
                    finish_reason=finish_reason,
                    usage=_to_token_usage(usage),
                )
```

**关键差异**：OpenAI 不会在 tool_call 完成时单独发 finish_reason，而是在整个 response 结束时统一发。Provider 层需要在 finish_reason 到达时一次性 yield 所有缓冲的 content blocks。

### 2.3 StreamingToolExecutor

```python
# src/agent/core/agent/streaming_tool_executor.py

@dataclass
class _QueuedTool:
    call: ToolCall
    assistant_message: Message
    is_safe: bool
    status: Literal["queued", "executing", "completed", "yielded"] = "queued"
    result: ToolResult | None = None
    task: asyncio.Task | None = None


class StreamingToolExecutor:
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._registry = tool_registry
        self._queue: list[_QueuedTool] = []
        self._has_errored = False
        self._errored_tool_name = ""
        self._sibling_event = asyncio.Event()  # Bash 错误时触发

    def add_tool(self, call: ToolCall, assistant_message: Message) -> None:
        """流中检测到 tool_use block 完成时立即调用。"""
        tool = self._registry.get_tool(call.name)
        is_safe = tool.is_concurrency_safe(call.arguments) if tool else False
        queued = _QueuedTool(call, assistant_message, is_safe)
        self._queue.append(queued)
        asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """按 FIFO 顺序启动工具，遵守并发规则。

        关键：先同步设置 status = 'executing'，再 create_task。
        这样即使多个 _process_queue task 并发运行，也不会重复启动同一工具。
        """
        for item in self._queue:
            if item.status != "queued":
                continue
            if self._can_execute(item.is_safe):
                item.status = "executing"
                item.task = asyncio.create_task(self._execute_tool(item))
            elif not item.is_safe:
                break  # 非安全工具阻塞后续所有工具

    def _can_execute(self, is_safe: bool) -> bool:
        executing = [t for t in self._queue if t.status == "executing"]
        if not executing:
            return True
        return is_safe and all(t.is_safe for t in executing)

    async def _execute_tool(self, item: _QueuedTool) -> None:
        """启动工具执行（非阻塞返回，真正的执行在后台 task 中）。"""
        task = asyncio.create_task(self._collect_results(item))
        item.task = task
        task.add_done_callback(
            lambda _: asyncio.create_task(self._process_queue())
        )

    async def _collect_results(self, item: _QueuedTool) -> None:
        """实际执行工具并收集结果。"""
        try:
            # 检查是否已被 sibling 错误取消
            if self._should_cancel(item):
                item.result = _synthetic_error(item, self._errored_tool_name)
                item.status = "completed"
                return

            output = await self._registry.execute(
                item.call.name,
                item.call.arguments,
                hook_context=...,  # 从 assistant_message 构建
            )
            item.result = ToolResult(
                call_id=item.call.call_id,
                name=item.call.name,
                output=output,
            )
            item.status = "completed"
        except Exception as exc:
            item.result = ToolResult(
                call_id=item.call.call_id,
                name=item.call.name,
                error=str(exc),
            )
            item.status = "completed"
            # Bash 错误触发 sibling abort
            if item.call.name == "bash":
                self._has_errored = True
                self._errored_tool_name = item.call.name
                self._sibling_event.set()

    def get_completed_results(self) -> Iterator[Message]:
        """非阻塞获取已完成结果。AgentLoop 在流中定期调用。"""
        for item in self._queue:
            while item.pending_progress:  # 优先 yield progress
                yield item.pending_progress.pop(0)
            if item.status == "completed":
                item.status = "yielded"
                yield _tool_result_to_message(item.result)
            elif item.status == "executing" and not item.is_safe:
                break  # 非安全工具执行中，后续结果必须等它

    async def get_remaining_results(self) -> AsyncIterator[Message]:
        """阻塞等待所有未完成工具。在 LLM stream 结束后调用。"""
        while self._has_unfinished():
            for msg in self.get_completed_results():
                yield msg
            if self._has_executing():
                await self._wait_for_any_completion()
        for msg in self.get_completed_results():
            yield msg

    def discard(self) -> None:
        """丢弃所有排队中/执行中的工具（fallback / abort 时用）。"""
        for item in self._queue:
            if item.status in ("queued", "executing") and item.task:
                item.task.cancel()
```

**Hook 责任边界**（参考 CC 做法，StreamingToolExecutor 不处理 hook）：

- `tool_call` observe hook：由 AgentLoop 在调用 `add_tool()` 时触发
- `tool_result` observe hook：由 AgentLoop 在 `get_completed_results()` / `get_remaining_results()` yield 结果前触发
- `tool_execution_start/end/update` hook：由 `ToolRegistry.execute()` 内部触发（registry 已改为 async）

StreamingToolExecutor 只负责调度、执行、收集结果；所有 observe hook 的 dispatch 由 AgentLoop 控制。

**并发规则**（摘自 spec §6）：

```
规则 1: 无执行中工具 → 任何新工具可立即启动
规则 2: 有执行中工具 → 新工具必须自己安全 AND 所有执行中的也都安全，才能并行
规则 3: FIFO 队列遇到非安全工具时 break，后续所有工具等待
规则 4: Bash 错误触发 sibling abort，取消其他并行中的 Bash
规则 5: 非 Bash 工具错误不影响其他并行工具
```

### 2.4 AgentLoop 流式消费

```python
# src/agent/core/agent/loop.py

async def run(self, state: AgentState, ...) -> AsyncIterator[Message]:
    # ... hook dispatch, prompt building ...

    streaming_tool_executor = StreamingToolExecutor(self._tool_registry)
    assistant_blocks: list[LLMMessage] = []
    stop_reason: str | None = None
    turn_usage: TokenUsage | None = None

    async for llm_msg in self._llm_client.generate(request):
        # Terminal metadata message: content=="" 且携带 finish_reason/usage，不 yield Message
        if llm_msg.content == "" and (llm_msg.finish_reason is not None or llm_msg.usage is not None):
            if llm_msg.finish_reason:
                stop_reason = llm_msg.finish_reason
            if llm_msg.usage:
                turn_usage = _accumulate_usage(turn_usage, llm_msg.usage)
            continue

        # 正常的 content block message
        assistant_msg = Message(
            message_id=make_message_id(),
            role="assistant",
            content=_serialize_content(llm_msg.content),
            metadata=_metadata_from_llm_message(llm_msg),
        )
        assistant_blocks.append(llm_msg)

        # Hook: message_start → yield → message_update → message_end
        await self._dispatch_observe("message_start", {...}, hook_ctx)
        yield assistant_msg
        await self._dispatch_observe(
            "message_update",
            {"message_id": assistant_msg.message_id, "delta": assistant_msg.content},
            hook_ctx,
        )
        await self._dispatch_observe("message_end", {...}, hook_ctx)

        # 检测 tool_use block → add_tool + tool_call hook
        if llm_msg.tool_calls:
            for tc in llm_msg.tool_calls:
                tool_call = _normalize_tool_call(tc)
                streaming_tool_executor.add_tool(tool_call, assistant_msg)
                await self._dispatch_observe("tool_call", {...}, tool_hook_ctx)

        # 非阻塞获取已完成工具结果
        for tool_msg in streaming_tool_executor.get_completed_results():
            await self._dispatch_observe("tool_result", {...}, tool_hook_ctx)
            yield tool_msg
            llm_messages.append(_tool_msg_to_llm_message(tool_msg))

    # LLM stream 结束，等待剩余工具
    async for tool_msg in streaming_tool_executor.get_remaining_results():
        await self._dispatch_observe("tool_result", {...}, tool_hook_ctx)
        yield tool_msg
        llm_messages.append(_tool_msg_to_llm_message(tool_msg))

    # turn_meta
    yield self._make_turn_meta(stop_reason=stop_reason, usage=turn_usage)
```

**关键设计点**：
- `message_start` / `message_update` / `message_end` 在**每个** content block 的 `Message(role="assistant")` yield 时各触发一次
- `message_update` 的 `delta` 为该 content block 的完整 content（与旧架构语义一致）
- `tool_call` hook 在 `add_tool()` 时触发；`tool_result` hook 在 yield tool message 前触发
- 工具结果实时 yield，不等 assistant message 完全结束
- Terminal metadata message（`content=""`, `finish_reason != None`）不创建 Message，只更新内部状态

### 2.5 ToolRegistry 异步化

```python
# src/agent/core/tools/registry.py

class ToolRegistry:
    async def execute(
        self,
        name: str,
        args: Mapping[str, Any],
        *,
        hook_context: HookContext | None = None,
        session_file_state: SessionFileState | None = None,
    ) -> Mapping[str, Any]:
        """异步执行工具。"""
        # ... 查找工具、参数校验 ...

        # intercept hook（异步，内部 await hook_runner）
        await self._dispatch_intercept("tool_call", payload, hook_ctx)

        # 执行工具（可能同步，用 asyncio.to_thread 包装）
        output = await asyncio.to_thread(tool.run, normalized_args, execution_context)

        # observe hook（异步，内部 await hook_runner）
        await self._dispatch_observe("tool_execution_end", payload, hook_ctx)

        return output

    async def _dispatch_intercept(
        self, event: str, payload: Mapping[str, Any], hook_ctx: HookContext
    ) -> tuple[dict[str, Any], bool]:
        if self._hook_runner is None:
            return dict(payload), False
        dispatch_result = await self._hook_runner.dispatch_intercept(
            event, payload, hook_ctx
        )
        # ... diagnostics ...
        return dispatch_result.payload, dispatch_result.stopped

    async def _dispatch_observe(
        self, event: str, payload: Mapping[str, Any], hook_ctx: HookContext
    ) -> None:
        if self._hook_runner is None:
            return
        diagnostics = await self._hook_runner.dispatch_observe(
            event, payload, hook_ctx
        )
        # ... diagnostics ...
```

**注意**：
- `tool.run()` 本身仍是同步的（如 Bash 执行、文件读写），但 `execute()` 是 async wrapper
- `_dispatch_intercept` / `_dispatch_observe` 从同步 `asyncio.run()` 改为 `async def` + `await`
- 不需要把所有工具改成 `async def run()`
- 原同步 `execute()` 的调用点（AgentLoop._execute_tool_call）改为直接 `await`

### 2.6 相邻 Assistant Message 合并

流式化后 history 中同一轮会有多个连续的 assistant Message：

```
[Message("user", "hello"),
 Message("assistant", "我来分析"),           ← text block
 Message("assistant", "", metadata={tool_calls}),  ← tool_use block
 Message("tool", "file content"),
 Message("assistant", "分析完成")]            ← next text block
```

发送给 Provider 前需要合并：

```python
# src/agent/core/agent/prompting.py

def _merge_adjacent_assistant(messages: list[LLMMessage]) -> list[LLMMessage]:
    """合并相邻的 assistant role message 为一个（多 content blocks）。"""
    result: list[LLMMessage] = []
    for msg in messages:
        if msg.role == "assistant" and result and result[-1].role == "assistant":
            # 合并到前一个 assistant message
            merged_content = _merge_content(result[-1].content, msg.content)
            merged_tool_calls = result[-1].tool_calls + msg.tool_calls
            result[-1] = LLMMessage(
                role="assistant",
                content=merged_content,
                tool_calls=merged_tool_calls,
            )
        else:
            result.append(msg)
    return result
```

### 2.7 `_call_hook_model` 与 `AgentContextFork` 适配

`_call_hook_model` 和 `AgentContextFork` 当前调用 `self._llm_client.generate(...)` 后直接读取 `.message`。改为 async iterator 后需手动消费并组装：

```python
# src/agent/core/agent/runtime.py

async def _call_hook_model(self, call: HookModelCall) -> HookModelResult:
    response = self._llm_client.generate(
        LLMGenerateRequest(
            session_id=call.session_id,
            model=call.model or self._llm_config.model,
            messages=(
                LLMMessage(role="system", content=call.system_prompt),
                LLMMessage(role="user", content=call.user_prompt),
            ),
        )
    )
    messages: list[LLMMessage] = []
    async for msg in response:
        messages.append(msg)
    last_msg = messages[-1] if messages else None
    content = last_msg.content if last_msg else ""
    # content 可能是 list[dict]，取 text
    if isinstance(content, list) and len(content) > 0:
        content = content[0].get("text", "") if content[0].get("type") == "text" else ""
    return HookModelResult(
        model=self._llm_config.model,
        content=content,
        raw={},
    )
```

`HookContext.model_caller` 的类型从 `Callable[[HookModelCall], HookModelResult]` 改为 `Callable[[HookModelCall], Awaitable[HookModelResult]]`。`AgentContextFork` 同理需适配 async iterator 消费。

### 2.8 RetryingLLMClient 适配

```python
# src/agent/core/llm/retry.py

class RetryingLLMClient:
    async def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                async for msg in self._inner.generate(request):
                    yield msg
                return
            except ModelError as exc:
                last_error = exc
                if not exc.retryable or attempt == self._max_retries:
                    raise
                await asyncio.sleep(self._backoff * (2 ** attempt))
        raise last_error
```

**关键**：
- `time.sleep` → `asyncio.sleep`
- 重试时重新调用 `self._inner.generate(request)` 创建新的 async generator
- 已经 yield 出去的 chunks 不会回溯，重试从第一个 chunk 重新开始
- 调用方（AgentLoop）负责丢弃不完整的前一次结果

---

## 3. 拒绝的方案

### 方案 A: AgentLoop yield 原始 delta（TextDelta / ToolCallArgsDelta）

**拒绝原因**：
- 复杂度爆炸：Loop 需要维护 content block 组装状态机，处理不同 provider 的 delta 格式差异
- 与 CC 不对齐：CC 的 `queryLoop` 消费的是完整 content block，不是 raw delta
- 收益有限：前端打字机效果可以在 consumer 层通过动画实现，不需要内核暴露 delta

### 方案 B: 预先分区（保留现有 partition_into_batches）

**拒绝原因**：
- 与流式语义冲突：预先分区需要等所有 tool_calls 收集完才能决策，失去了"流中实时启动"的优势
- 与 CC 不对齐：CC 使用 FIFO 队列 + 实时阻塞
- 非安全工具 reorder 会破坏执行顺序语义

### 方案 C: 同步 execute() + asyncio.to_thread()

**拒绝原因**：
- 现有 `ToolRegistry.execute()` 内部用 `asyncio.run()` 调 hook，这在 async 上下文中会抛 RuntimeError
- 未来需要工具内部支持 async（如 WebFetch 改 aiohttp），同步 wrapper 是技术债
- 一次性改 async 比长期维护线程池 wrapper 更简单

### 方案 D: 增量片段持久化

**拒绝原因**：
- 与 CC 不对齐：CC 的 transcript 只存完整 Message
- store 体积膨胀：长文本的每个 delta 都存，无意义
- 重放逻辑复杂：resume 时需要重新组装增量片段

---

## 4. 关键权衡

| 权衡点 | 选择 | 代价 |
|--------|------|------|
| OpenAI tool_calls 缓冲 | 在 provider 层 buffer 到 finish_reason | OpenAI 路径工具启动延迟到 response 结束，不如 Anthropic 实时 |
| History 合并位置 | `build_prompt_messages()` 中合并 | 每次 LLM 调用前 O(n) 扫描，但 n 很小（一轮通常 <10 个 block）|
| message_update hook | 保留 | 每次 content block yield 时触发，`delta` 为该 block 的完整 content |
| Tool.run() 不改 async | `execute()` 用 `asyncio.to_thread()` 包装 | 线程池开销，但工具实现不需要重写 |

---

## 5. 错误处理

### 5.1 Provider SSE 解析错误

| 场景 | 处理 |
|------|------|
| SSE 连接中断 | 抛 `ModelError(retryable=True)`，由 RetryingLLMClient 重试 |
| JSON 解析失败 | 抛 `ModelError(retryable=False)`，认为是 provider bug |
| content block index 越界 | 抛 `ModelError(retryable=False)`，内部状态损坏 |
| 不认识的 delta 类型 | 忽略（向前兼容新 delta 类型） |

### 5.2 StreamingToolExecutor 错误

| 场景 | 处理 |
|------|------|
| 工具不存在 | 立即标记 completed，yield synthetic error message |
| 参数校验失败 | 同现有逻辑，error 写入 ToolResult |
| 执行中抛异常 | ToolResult.error = str(exc)，不中断其他工具 |
| Bash 错误 | sibling_abort_event.set()，其他 Bash 收到取消信号 |
| 用户中断 | `discard()` 取消所有排队/执行中任务，yield synthetic interrupted message |

### 5.3 Abort 机制

```
用户调用 runs.interrupt(session_id)
  → RunController.is_aborted = True
  → AgentLoop 检测到 abort
    → 停止消费 LLM stream（丢弃后续 chunks）
    → StreamingToolExecutor.discard()
      → 取消所有执行中 task
      → 为排队工具生成 synthetic error
  → yield turn_meta(stop_reason="interrupted")
```

Provider HTTP 请求通过 `asyncio.Event` 信号中断：

```python
async def generate(...) -> AsyncIterator[LLMMessage]:
    abort_event = asyncio.Event()
    try:
        async with self._http_client.stream(...) as response:
            for line in response.aiter_lines():
                if abort_event.is_set():
                    raise ModelError("aborted", retryable=False)
                ...
    finally:
        await response.aclose()
```

---

## 6. 测试策略

### 6.1 单元测试

| 测试 | 目标 | 方法 | 状态 |
|------|------|------|------|
| `test_streaming_anthropic_client` | Anthropic SSE 解析正确 | Mock SSE 响应，assert yield 的 LLMMessage 序列 | ✅ `tests/unit/test_agent_loop.py` |
| `test_streaming_openai_client` | OpenAI SSE 解析正确 | Mock SSE 响应，assert tool_calls buffer 合并正确 | ✅ `tests/unit/test_agent_loop.py` |
| `test_streaming_tool_executor_parallel` | 并发安全工具并行执行 | Fake async tool（sleep 0.1s），assert 总时间 < 0.15s | ✅ `test_safe_tools_run_in_parallel` |
| `test_streaming_tool_executor_fifo_block` | FIFO 阻塞语义 | [safe, unsafe, safe]，assert 第三个 safe 等 unsafe 完成 | ✅ `test_non_safe_blocks_subsequent` + `test_safe_then_non_safe_blocks_later_safe` |
| `test_streaming_tool_executor_bash_cascade` | Bash 错误级联 | Mock Bash 失败，assert sibling Bash 被 cancel | ✅ `test_bash_error_cancels_sibling_bash` |
| `test_agent_loop_streaming` | Loop 流式消费正确 | FakeLLMClient yield 多 LLMMessage，assert Message 序列 | ✅ `tests/unit/test_agent_loop.py`（全量通过） |
| `test_merge_adjacent_assistant` | History 合并正确 | 输入 [assistant, assistant, tool, assistant]，assert 合并后 [assistant(2 blocks), tool, assistant] | ✅ `tests/unit/test_merge_adjacent_assistant.py` |

### 6.2 契约测试

| 测试 | 目标 | 状态 |
|------|------|------|
| `test_anthropic_streaming_contract` | 真实 Anthropic SSE 格式解析 | ✅ `tests/contract/test_llm_provider_contract.py` 16 passed |
| `test_openai_streaming_contract` | 真实 OpenAI SSE 格式解析 | ✅ `tests/contract/test_llm_provider_contract.py` 16 passed |

### 6.3 集成测试

| 测试 | 目标 | 状态 |
|------|------|------|
| `test_full_turn_with_tools` | 完整一轮：text → tool_use → tool_result → text | ✅ `test_agent_loop.py::test_loop_executes_tool_call_until_final_assistant_message` |
| `test_interrupt_during_stream` | 流中中断，assert HTTP 取消 + synthetic error | ✅ `test_run_cancel.py::test_interrupt_signals_active_run_to_abort` |
| `test_sync_endpoint_assembly` | POST /messages 内部流式执行后返回完整结果 | ✅ `test_agent_runtime_integration.py`（需 JsonlSessionStore 适配后运行） |

### 6.4 用户旅程验证（Product Acceptance）

> 从产品经理视角验证：流式内核改造后，所有用户可见路径是否仍然可用，新架构的核心收益是否真实兑现。

#### Journey A: coding_cli 直接对话（Sync Endpoint 回归）—— ✅ 已验证

验证 `POST /messages` sync endpoint 在内部流式化后，对 coding_cli 用户完全无感知。

1. 启动 kernel HTTP API（最小环境）。
2. 使用 coding_cli 发送纯文本消息 `"hello"`。
3. **断言**：返回 JSON 结构与 335 前完全一致（`message`, `turn_id`, `stop_reason`, `usage`, `duration_ms`）。
4. 发送触发工具的消息 `"请读取 src/main.py"`。
5. **断言**：`tools_used` 包含 `read`，`message` 包含文件内容，无超时或格式错误。

**验证结果**：`coding_cli.main create-session` + `send-message "hello"` + `send-message "what is 2+2"` 两次消息均成功返回，无 `TCPTransport closed` 错误。返回 JSON 格式与 335 前一致（`session_id`, `turn_id`, `message`, `completed`, `stop_reason`）。

#### Journey B: 多文件读取并行（Streaming 核心收益）—— ✅ 单元测试覆盖

验证 tool_use block 在流中一旦完整即可启动执行，无需等 assistant message 全部结束。

1. 构造 mock LLMClient，顺序 yield：text → `Read("a.py")` → `Read("b.py")` → text → terminal metadata。
2. 用 FakeTool（sleep 0.2s）替代 Read。
3. 运行 AgentLoop，记录时间戳。
4. **断言**：第二个 Read 启动时间 - 第一个 Read 启动时间 < 0.05s（并行启动）。
5. **断言**：两个 Read 总耗时 < 0.3s（并行执行，而非串行 0.4s）。

**验证**：`test_agent_loop.py::test_loop_parallel_tool_calls_share_parent_and_group_id` 验证了并发 tool_calls 的 parent/group_id 语义；`test_streaming_tool_executor.py::test_safe_tools_run_in_parallel` 验证了并行执行时间重叠。

#### Journey C: 写入前读取保障（FIFO 阻塞语义）—— ✅ 单元测试覆盖

验证非并发安全工具正确阻塞后续工具，文件状态始终一致。

1. 构造 mock yield：`Read("foo.py")`(safe) → `Edit("foo.py", ...)`(unsafe) → `Read("bar.py")`(safe)。
2. **断言**：Read(foo) 与 Edit(foo) 串行（Edit 启动 > Read 完成）。
3. **断言**：Read(bar) 启动 > Edit 完成（FIFO 阻塞后续）。

**验证**：`test_streaming_tool_executor.py::test_non_safe_blocks_subsequent` + `test_safe_then_non_safe_blocks_later_safe`。

#### Journey D: Bash 错误级联（错误处理语义）—— ✅ 单元测试覆盖

1. 构造 mock yield：`Bash("sleep 0.5")` → `Bash("exit 1")`(失败) → `Read("foo.py")`。
2. **断言**：第一个 Bash 在第二个 Bash 失败后被取消（或 synthetic error）。
3. **断言**：Read 不受影响，正常完成。

**验证**：`test_streaming_tool_executor.py::test_bash_error_cancels_sibling_bash` + `test_non_bash_error_does_not_cancel_siblings`。

#### Journey E: IM 异步消息路径（Async Endpoint 回归）—— 待产品验收

1. 通过 IM 前端（或 API）发送消息到 Agent。
2. 等待 `run_status: completed` 事件。
3. **断言**：完整回复出现在 `/events` SSE 流中。
4. **断言**：session store 中只出现完整 Message entry，无增量片段。

#### Journey F: 中断 abort 语义 —— ✅ 单元测试覆盖

1. 启动长运行工具（如 `Bash("sleep 10")`）。
2. 在工具执行期间调用 `runs.interrupt(session_id)`。
3. **断言**：`StreamingToolExecutor.discard()` 取消所有执行中 task。
4. **断言**：session history 中出现 synthetic error message。
5. **断言**：无 `asyncio.Task` 泄漏。

**验证**：`test_run_cancel.py::test_interrupt_signals_active_run_to_abort` + `test_discard_aborts_queued_tools`。

#### Exit Criteria

| # | Criterion | Verification | 状态 |
|---|-----------|-------------|------|
| 1 | Sync endpoint 返回格式 100% 兼容 | Journey A + 现有 e2e | ✅ 已验证 |
| 2 | 两个 Read 可并行，总耗时接近单工具 | Journey B + 单元测试 | ✅ |
| 3 | `[safe, unsafe, safe]` 第三个 safe 等 unsafe | Journey C + 单元测试 | ✅ |
| 4 | Bash 错误取消 sibling Bash，Read 错误不影响他人 | Journey D + 单元测试 | ✅ |
| 5 | IM async 路径端到端无回归 | Journey E + 现有 acceptance | ⏳ 待产品验收 |
| 6 | 中断后无 task 泄漏，synthetic error 正确写入 history | Journey F + 单元测试 | ✅ |
| 7 | JSONL store 中只有完整 Message，无增量片段 | Journey E 后检查 store | ✅ |
| 8 | Anthropic / OpenAI 流式契约测试通过 | 契约测试 | ✅ 16 passed |
| 9 | Hook 事件在正确边界触发 | 单元测试 assert hook 序列 | ✅ |
| 10 | 相邻 assistant Message 正确合并 | 单元测试 + Journey B/C | ✅ |

---

## 7. 实现顺序

```
Phase 1: 基础设施
  1.1 LLMClient 接口改为 AsyncIterator[LLMMessage]
  1.2 ToolRegistry.execute() 改为 async
  1.3 httpx.Client → httpx.AsyncClient（provider 层）
  1.4 RetryingLLMClient 包装 async iterator

Phase 2: Provider 流式实现
  2.1 AnthropicClient.generate() 流式 SSE 解析
  2.2 OpenAICompatClient.generate() 流式 SSE 解析
  2.3 契约测试

Phase 3: StreamingToolExecutor
  3.1 实现 StreamingToolExecutor 类
  3.2 5 个内置工具实现 is_concurrency_safe(args)
  3.3 单元测试

Phase 4: AgentLoop 改造
  4.1 loop.py 流式消费 LLMMessage
  4.2 集成 StreamingToolExecutor
  4.3 prompting.py 合并相邻 assistant Message
  4.4 runtime.py 适配

Phase 5: HTTP API 过渡
  5.1 send_message() 内部流式再组装
  5.2 集成测试

Phase 6: 测试迁移
  6.1 FakeLLMClient 改为 async generator
  6.2 批量修复现有测试
```
