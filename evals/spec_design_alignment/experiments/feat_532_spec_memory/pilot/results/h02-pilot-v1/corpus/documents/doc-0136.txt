# feat-335: Streaming Tool Executor — 需求规格

> **变更单元**: feat-335  
> **状态**: 需求已澄清，待设计  
> **对齐日期**: 2026-04-27  
> **参考**: Claude Code `query.ts` + `StreamingToolExecutor.ts` + `services/api/claude.ts`

---

## 1. 目标

将 Agent 内核从"同步 request-response 轮询"模型改为"流式消费 + 实时工具执行"模型。只保留 streaming 路径，废弃非 streaming fallback。

核心收益：
- **延迟降低**: tool_use block 在流中一旦完整即可立即执行，无需等 assistant message 全部结束
- **并发提升**: LLM 后续 content block 的流式接收与工具执行并行进行
- **实时反馈**: coding_cli / IM 前端能看到打字机效果（text delta 实时渲染）
- **架构对齐**: 与 Claude Code 的 streaming architecture 保持一致

---

## 2. 用户场景

### 场景 A: 多文件读取并行
用户问"对比 src/a.py 和 src/b.py 的区别"。LLM 流式输出解释文字的同时 emit 两个 Read tool_use。第一个 Read 在流中即开始执行，第二个 Read（若并发安全）也同时启动。用户在前端先看到"我来读取两个文件..."的文字，随后工具结果实时回来，不需要等 LLM 说完一整段话。

### 场景 B: 写入前读取保障
LLM 先 emit Read("src/foo.py")，再 emit Edit("src/foo.py", ...)。Read 在流中立即执行，Edit 因非并发安全进入队列等待。Read 结果先回来，Edit 后执行。文件状态始终一致。

### 场景 C: 长文本打字机效果
LLM 输出长段分析文字。前端通过 SSE 实时接收 text delta，逐字渲染，而非等待整段文字完成后才一次性显示。

---

## 3. 核心决策

| # | 决策 | 选择 | 拒绝的方案 |
|---|------|------|-----------|
| 1 | 流式接口粒度 | content block 级别（`LLMMessage` 含一个 content block） | 原生 SSE 事件透传 / raw delta |
| 2 | yield 语义 | Loop 层 yield 完整 `Message`（content block 边界） | Loop 层 yield 增量片段 |
| 3 | 并发调度 | FIFO 队列，非并发安全工具阻塞后续所有工具 | 预先分区（partition_into_batches） |
| 4 | 并发判断 | 动态：`tool.is_concurrency_safe(args) → bool` | 静态：`ToolSpec.is_concurrency_safe` |
| 5 | 持久化 | 只持久化完整 Message，增量不存 | 增量也持久化 |
| 6 | Sync endpoint | 内部走流式再组装完整结果返回（过渡方案） | 废弃 sync 或改 SSE |
| 7 | Hook 事件 | 保留现有事件名，只在完整 Message 边界触发 | 废弃或改按 delta 触发 |
| 8 | 错误级联 | Bash 错误取消并行 sibling，其他工具独立 | 统一 gather 模式 |

---

## 4. 范围

### 4.1 In Scope

- `LLMClient` 接口改造：`generate()` → `AsyncIterator[LLMMessage]`（每个 yield 为一个 content block）
- Provider 层流式实现：Anthropic + OpenAI-compat 的 SSE 解析，content block 边界 yield
- `AgentLoop.run()` 流式消费重构：边收 content block 边 yield 完整 Message
- `StreamingToolExecutor` 引入：FIFO 队列 + 动态并发判断 + 实时 dispatch
- `Tool` / `ToolSpec` 接口扩展：`is_concurrency_safe(args)` 动态方法
- 现有 5 个内置工具实现并发安全判断
- `Message` / `TurnResult` 契约调整以支持多 block assistant message
- Sync endpoint (`POST /messages`) 内部流式化（组装后返回）
- Hook 事件语义调整：只在完整 Message 边界触发
- Session 持久化策略不变：只存完整 Message

### 4.2 Out of Scope

- coding_cli 前端实时渲染改造（335 只改内核接口，coding_cli 仍组装完整后显示）
- IM 前端 SSE 实时消费改造
- `/messages` 返回 `StreamingResponse`（TODO 后续 milestone）
- `stream_chunk` 级别 hook 事件（可后置）
- 非 streaming fallback（完全废弃）
- Provider 切换时的流式适配（已有 Anthropic + OpenAI-compat 即可）

### 4.3 明确废弃

| 被废弃项 | 替代方案 | 备注 |
|---------|---------|------|
| `LLMGenerateRequest.stream: bool` | 始终流式，字段移除 | 335 后不支持非流式 |
| `LLMClient.generate()` 返回 `LLMGenerateResponse` | 返回 `AsyncIterator[LLMMessage]` | 同步调用彻底移除 |
| `ToolSpec.is_concurrency_safe` 静态字段 | `Tool.is_concurrency_safe(args)` 动态方法 | 所有 ToolSpec 实例需更新 |
| `partition_into_batches()` 预先分区模型 | `StreamingToolExecutor` FIFO 队列 | 调度语义改变 |
| `ToolExecutor` 类 | `StreamingToolExecutor` | 执行模型改变 |

---

## 5. 关键接口

### 5.1 Content Block 流式契约

Provider 内部将 SSE 原始事件组装成完整 content block，在 content block 边界 yield 一个 `LLMMessage`。`LLMMessage` 的 `content` 只包含**单个** content block：

- text block → `LLMMessage(content=[{"type": "text", "text": "..."}])`
- tool_use block → `LLMMessage(content=[{"type": "tool_use", "name": "...", "input": {...}}])`

当 LLM stream 结束（`message_delta` / `message_stop`）时，Provider 额外 yield 一个 **terminal metadata message**：

- `LLMMessage(content="", finish_reason="tool_use", usage=TokenUsage(...))`

AgentLoop 消费时，正常 content block 转换为 `Message(role="assistant")` 并 yield；terminal metadata message 不创建 Message，只提取 `finish_reason` 和 `usage` 更新内部状态。

### 5.2 LLMClient 协议

```python
class LLMClient(Protocol):
    def generate(self, request: LLMGenerateRequest) -> AsyncIterator[LLMMessage]:
        ...
```

注意：
- `LLMGenerateRequest.stream` 字段移除，始终流式
- 每个 yield 为一个 content block 级别的 `LLMMessage`
- `LLMMessage` 新增可选字段 `finish_reason: str | None` 和 `usage: TokenUsage | None`
- 最后一个 yield 可以是 `content=""` 的 terminal metadata message，仅携带 `finish_reason` 和 `usage`

### 5.3 Tool 并发判断

```python
class Tool(Protocol):
    name: str
    schema: dict

    def run(self, args, ctx) -> ToolResult:
        ...

    def is_concurrency_safe(self, args: Mapping[str, Any]) -> bool:
        """动态判断本次调用是否可与其他安全调用并行。"""
        ...
```

### 5.4 StreamingToolExecutor

```python
class StreamingToolExecutor:
    def __init__(
        self,
        tool_registry: ToolRegistry,
        concurrency_map: dict[str, Callable[[Mapping], bool]],
    ) -> None:
        ...

    def add_tool(self, tool_call: ToolCall, assistant_message: Message) -> None:
        """流中检测到完整 tool_use 时立即加入队列并开始执行。"""
        ...

    def get_completed_results(self) -> Iterator[Message]:
        """非阻塞获取已完成的 tool_result（含 progress 消息）。"""
        ...

    async def get_remaining_results(self) -> AsyncIterator[Message]:
        """阻塞等待所有工具完成并 yield 结果。"""
        ...

    def discard(self) -> None:
        """丢弃所有排队中/执行中的工具（fallback / abort 时用）。"""
        ...
```

### 5.5 AgentLoop.run() yield 契约

```python
async def run(...) -> AsyncIterator[Message]:
    """Yield 完整 Message 流。

    具体序列：
    1. turn_start hook
    2. `Message(role="assistant")` — 从 content block yield
       - text block → content = text
       - tool_use block → content = "", metadata.tool_calls = [...]
    3. 若 assistant message 含 tool_calls → add_tool() + tool_call hook
    4. `Message(role="tool")`... — 从 get_completed_results() 非阻塞 yield
       每个 yield 前触发 tool_result hook
    5. LLMMessage(content="", finish_reason=..., usage=...) — terminal metadata
       不 yield Message，只更新 stop_reason / usage 内部状态
    6. 重复 2-5 直到无更多 content blocks
    7. `Message(role="tool")`... — 从 get_remaining_results() 最终 yield
       每个 yield 前触发 tool_result hook
    8. `Message(role="turn_meta")`
    9. turn_end hook

    Hook 事件触发规则：
    - message_start / message_update / message_end：在每个 content block 的
      Message(role="assistant") yield 时各触发一次
    - tool_call：在 StreamingToolExecutor.add_tool() 时触发
    - tool_result：在 yield Message(role="tool") 前触发
    """
```

---

## 6. 并发规则

```
规则 1: 无执行中工具 → 任何新工具可立即启动
规则 2: 有执行中工具 → 新工具必须自己安全 AND 所有执行中的也都安全，才能并行
规则 3: FIFO 队列遇到非安全工具时 break，后续所有工具等待
规则 4: Bash 错误触发 sibling abort，取消其他并行中的 Bash
规则 5: 非 Bash 工具错误不影响其他并行工具
```

示例调度：

```
流中收到 tool_calls: [ReadA, ReadB, EditC, ReadD]

T0: ReadA 启动 (executing)
T0: ReadB 启动 (executing) ← ReadA 也是安全的，可并行
T1: EditC 遇到 ReadA/ReadB 正在执行，且 EditC 不安全 → 等待
T2: ReadA 完成
T2: ReadB 完成
T2: EditC 启动 (executing) ← 现在可以了
T3: EditC 完成
T3: ReadD 启动 (executing) ← EditC 完成后，ReadD 安全可上
```

---

## 7. 各层改动清单

### core/llm/interfaces.py
- 移除 `LLMGenerateRequest.stream`
- `LLMClient.generate()` 返回 `AsyncIterator[LLMMessage]`（每个 yield 为一个 content block）
- `LLMMessage` 新增 `finish_reason: str | None` 和 `usage: TokenUsage | None`
- 移除 `LLMGenerateResponse` 同步返回类型

### platform/llm/providers/*/
- `AnthropicClient.generate()`: SSE 流式解析，yield 语义化 chunks
- `OpenAICompatClient.generate()`: SSE 流式解析，yield 语义化 chunks
- 移除 `if request.stream: raise ...`

### core/tools/base.py
- `Tool` 协议增加 `is_concurrency_safe(self, args)` 方法

### core/tools/registry.py
- `ToolRegistry.execute()` 改为 `async def execute()`
- `_dispatch_intercept()` / `_dispatch_observe()` 改为 `async def`，内部 `await` hook_runner
- 移除内部的 `asyncio.run()` 调用

### platform/tools/builtins/*.py
- 每个内置工具实现 `is_concurrency_safe(args)`:
  - `read`: 始终安全（只读）
  - `bash`: 看命令内容（`ls`/`cat`/`grep` 安全，`git commit`/`rm` 不安全）
  - `write`: 不安全（文件系统写操作）
  - `edit`: 不安全（文件系统写操作）
  - `task`: 不安全（subagent 有副作用）

### core/agent/tool_executor.py
- 移除 `partition_into_batches()` 和 `ToolExecutor`
- 新增 `StreamingToolExecutor`

### core/agent/loop.py
- `run()` 改为流式消费 content blocks
- 流中检测完整 tool_use content block 并触发工具执行
- 集成 `StreamingToolExecutor`
- `message_start`/`message_update`/`message_end` hook 在完整 message 边界触发

### core/agent/runtime.py
- `_execute_loop()` 改为流式消费
- `build_turn_result()` 适配多 block assistant message
- `_call_hook_model()` 改为 `async def`，手动消费 async iterator 组装完整结果
- `AgentContextFork` 适配 async iterator 消费

### platform/http_api/routes/session.py
- `send_message()`: 内部调用 `runtime.run()` 流式执行，收集完整结果后返回
- 保留现有 `SendMessageResponse` 格式（过渡）
- 添加 TODO: 后续改为 StreamingResponse

### tests/
- 所有测试中的 mock LLMClient 需改为 AsyncIterator
- `test_loop_retry.py` 等需适配新流式语义
- 新增 `test_streaming_tool_executor.py`

---

## 8. 验收标准

1. **接口契约**: `LLMClient.generate()` 返回 `AsyncIterator[LLMMessage]`，非 `LLMGenerateResponse`
2. **流式解析**: Anthropic 和 OpenAI-compat provider 能正确解析 SSE 并在 content block 边界 yield `LLMMessage`
3. **Terminal metadata**: 流结束时最后一个 yield 携带 `finish_reason` 和 `usage`，AgentLoop 正确提取并写入 turn_meta
4. **工具实时执行**: tool_use content block 完成后，工具在流结束前即开始执行
5. **并发安全**: 两个 Read 调用可并行，Read + Edit 串行（Edit 阻塞后续）
6. **FIFO 阻塞**: `[safeA, unsafe, safeB]` 中 safeB 必须等 unsafe 完成
7. **Bash 级联**: Bash 错误时取消其他并行中的 Bash，Read 错误不影响他人
8. **Hook 边界**: `message_start`/`message_update`/`message_end` 只在完整 assistant message yield 时各触发一次；`tool_call` 在 add_tool 时触发；`tool_result` 在 yield tool message 前触发
9. **持久化不变**: JSONL store 中只出现完整 Message entry，无增量片段
10. **Sync 兼容**: `POST /messages` 仍返回 `SendMessageResponse`，内部走流式
11. **Abort 正确**: 用户中断时，StreamingToolExecutor 为排队/执行中工具生成 synthetic error
12. **Retry 兼容**: `RetryingLLMClient` 正确包装 async iterator，重试时重新创建 generator
13. **History 合并**: `build_prompt_messages()` 正确合并相邻 assistant Message 为多 content blocks

---

## 9. TODO（后续 milestone）

- [ ] `POST /messages` 改为返回 `StreamingResponse`（SSE），coding_cli 切 EventSource 消费
- [ ] coding_cli 前端实时渲染打字机效果
- [ ] IM 前端 SSE 实时消费
- [ ] 可选新增 `stream_chunk` observe hook 事件

---

## 10. 风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| Provider SSE 解析差异 | 不同 provider 的流格式不同，需分别适配 | 先实现 Anthropic 和 OpenAI-compat，其他 provider 后续跟进 |
| 现有测试大面积失效 | mock LLMClient 的测试全部需要重写 | 提供 mock chunk generator helper，批量迁移 |
| Tool 并发判断遗漏 | 某工具被误判为安全导致竞态 | 默认不安全，逐个工具显式声明安全条件 |
| Sync endpoint 过渡方案技术债 | 内部流式再组装浪费了流式收益 | spec 中明确 TODO，后续 milestone 排期 |
