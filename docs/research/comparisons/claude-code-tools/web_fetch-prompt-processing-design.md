# web_fetch prompt-based 内容处理架构设计

> **状态**：✅ 已实现（2026-04-20）。

## 目标

实现 `web_fetch` 工具的 `prompt` 参数——模型传入 `"提取所有 API endpoint"` 后，工具自动将提取到的网页内容 + prompt 发送给轻量 LLM 做结构化处理，返回整理后的结果。

## 1. claude-code 的设计

### 1.1 调用链路

```
WebFetchTool.call() → applyPromptToMarkdown()
  → makeSecondaryModelPrompt() 格式化 user message
  → queryHaiku() 调用 LLM
  → 从 response 第一个 text block 提取结果
```

### 1.2 Prompt 格式

**System prompt**: 空数组 `asSystemPrompt([])`

**User message**（由 `makeSecondaryModelPrompt()` 生成）：
```
Web page content:
---
{markdownContent}
---

{prompt}

{guidelines}
```

**Guidelines**（统一，不区分域名类型）：
`Provide a concise response based on the content above. Include relevant details, code examples, and documentation excerpts as needed.`

### 1.3 模型与参数

| 参数 | 值 |
|---|---|
| 模型 | Haiku 4.5 (`claude-haiku-4-5-20251001`) |
| System prompt | 空 |
| Thinking | disabled |
| Tools | 无 |
| Max output tokens | 32K default / 64K upper / 8K with slot cap |
| Content truncation | 100K 字符上限，超限截断后加 `[Content truncated...]` |
| 重试 | `withRetry()` 最多 10 次 |
| 调用方式 | async 但 blocking（awaited），无 streaming |
| 取消信号 | 检查 `AbortSignal`，取消时抛 `AbortError` |

### 1.4 错误处理

- LLM 调用失败（非 retryable 或重试耗尽）→ 错误向上传播 → 工具返回 `is_error` tool result
- Abort → 抛 `AbortError`
- Response 无 text block → 返回 `"No response from model"`

---

## 2. nano-multiagent 的现状

### 2.1 LLM 调用基础设施

| 组件 | 路径 | 职责 |
|---|---|---|
| LLMClient Protocol | `core/llm/interfaces.py` | `generate(request) -> response` |
| LLMGenerateRequest | `core/llm/interfaces.py` | session_id, model, messages, stream, max_tokens, tools, metadata |
| LLMGenerateResponse | `core/llm/interfaces.py` | model, message, finish_reason, usage, raw |
| 工厂 | `core/llm/factory.py` | `create_llm_client(config)` → provider-specific client |
| 重试包装 | `core/llm/retry.py` | `RetryingLLMClient` 指数退避，最多 20 次重试 |
| One-shot hook | `core/hooks/context.py` | `HookContext.call_model(system, user, model)` → `HookModelResult` |
| One-shot runtime | `core/agent/runtime.py` | `AgentRuntime._call_hook_model()` → `llm_client.generate()` |

### 2.2 轻量 LLM 调用模式（HookContext.call_model）

```python
# HookContext.call_model()
def call_model(self, *, system_prompt: str, user_prompt: str, model: str | None = None):
    return caller(HookModelCall(
        session_id=self.session_id,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
    ))

# AgentRuntime._call_hook_model()
def _call_hook_model(self, call: HookModelCall) -> HookModelResult:
    response = self._llm_client.generate(
        LLMGenerateRequest(
            session_id=normalized_session,
            model=model,
            stream=False,
            messages=(
                LLMMessage(role="system", content=call.system_prompt),
                LLMMessage(role="user", content=call.user_prompt),
            ),
            metadata=dict(call.metadata),
        )
    )
    return HookModelResult(
        model=response.model,
        content=response.message.content,
        raw=response.raw,
    )
```

### 2.3 ToolContext 现状

`ToolContext` 是 frozen dataclass，当前字段：
```python
repo_root, cwd, safety, session_id, tool_call_id,
safety_overrides, execution_event_callback, session_metadata, session_file_state
```

**没有 `llm_client` 字段**。工具 `run()` 只接收 `ToolContext`，无法直接调用 LLM。

---

## 3. 架构设计

### 3.1 核心决策：LLMClient 注入方式

| 方案 | 方式 | 优点 | 缺点 |
|---|---|---|---|
| A | `ToolContext` 加 `llm_client` 字段 | 与现有扩展方式一致；未来其他工具可复用 | 所有工具都能访问 LLM（但实际无风险） |
| B | `WebFetchTool.__init__` 注入 | 最小侵入性 | 需修改注册链传递 llm_client |
| C | 全局 factory/env | 零修改 | 耦合度高，测试困难 |

**选择方案 A**：在 `ToolContext` 添加可选的 `llm_client` 字段。

理由：
- `ToolContext` 已有 `session_metadata`、`session_file_state` 等扩展字段，模式一致
- `with_session()` 已支持克隆，自然扩展
- `llm_client` 是 optional，不破坏现有工具
- 未来 `web_search` 等工具也能复用

### 3.2 数据流

```
AgentRuntime.__init__()
  └── build_tool_registry(llm_client=active_llm_client)
        └── ToolContext.create(llm_client=llm_client)
              └── ToolContext(repo_root=..., safety=..., llm_client=...)

AgentRuntime.run(session_id, parts)
  └── AgentLoop.run()
        └── 模型调用 web_fetch(url, prompt="提取API")
              └── ToolRegistry.execute("web_fetch", args)
                    ├── 创建 per-call context: ctx.with_session(session_id, ...)
                    ├── WebFetchTool.run(args, ctx)
                    │     ├── fetch URL
                    │     ├── extract text (markdownify)
                    │     ├── if prompt and ctx.llm_client:
                    │     │     _process_with_prompt(text, prompt)
                    │     │       ├── format user message (content + prompt + guidelines)
                    │     │       ├── ctx.llm_client.generate(LLMGenerateRequest)
                    │     │       └── extract text from response.message.content
                    │     └── return result
                    └── serialize_result → LLM
```

### 3.3 修改的文件清单

| 文件 | 修改内容 |
|---|---|
| `core/tools/base.py` | `ToolContext` 添加 `llm_client: LLMClient \| None = None`；`create()` 和 `with_session()` 传递 |
| `platform/tools/loader.py` | `build_tool_registry()` 添加 `llm_client` 参数；`ToolContext.create()` 注入 |
| `core/agent/runtime.py` | `AgentRuntime.__init__()` 调用 `build_tool_registry(llm_client=...)` |
| `platform/tools/builtins/web_fetch.py` | 添加 `_process_with_prompt()` 和 `_make_prompt()` |

### 3.4 WebFetchTool 内部设计

```python
class WebFetchTool:
    def __init__(self, *, default_max_chars: int = _DEFAULT_MAX_CHARS) -> None:
        self._default_max_chars = min(default_max_chars, _HARD_MAX_CHARS)

    def run(self, args: Mapping[str, Any], ctx: ToolContext) -> Mapping[str, Any]:
        # ... fetch and extract text ...

        prompt = args.get("prompt")
        if prompt and ctx.llm_client is not None:
            text = self._process_with_prompt(text, prompt, ctx.llm_client)

        # ... return result ...

    def _process_with_prompt(
        self,
        content: str,
        prompt: str,
        llm_client: LLMClient,
    ) -> str:
        """Process extracted content via LLM using user prompt.

        Matches claude-code's applyPromptToMarkdown() semantics:
        - Empty system prompt
        - Content + prompt + guidelines as user message
        - Graceful fallback to original content on LLM failure
        """
        # Truncate to leave room for prompt + system message in context window
        max_content = 50_000
        if len(content) > max_content:
            content = content[:max_content] + "\n\n[Content truncated due to length...]"

        user_prompt = self._make_prompt(content, prompt)

        try:
            response = llm_client.generate(
                LLMGenerateRequest(
                    session_id=f"web_fetch_prompt_{id(content)}",
                    model=self._resolve_model(),
                    messages=(
                        LLMMessage(role="system", content=""),
                        LLMMessage(role="user", content=user_prompt),
                    ),
                    stream=False,
                )
            )
        except Exception:
            # LLM call failed — return original content (graceful degradation)
            return content

        processed = response.message.content
        if processed:
            return processed
        return content  # Fallback on empty response

    def _make_prompt(self, content: str, prompt: str) -> str:
        """Format user message matching claude-code's makeSecondaryModelPrompt()."""
        guidelines = (
            "Provide a concise response based on the content above. "
            "Include relevant details, code examples, and documentation excerpts as needed."
        )
        return (
            f"Web page content:\n---\n{content}\n---\n\n"
            f"{prompt}\n\n"
            f"{guidelines}"
        )

    def _resolve_model(self) -> str:
        """Resolve model for prompt processing.

        Phase 3: uses runtime's default model via env config.
        Future: support dedicated secondary_model config.
        """
        from agent.core.llm.factory import LLMFactoryConfig
        return LLMFactoryConfig.from_env().model
```

### 3.5 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| LLMClient 注入位置 | `ToolContext.llm_client` | 与现有扩展模式一致；`with_session()` 自然支持 |
| System prompt | 空字符串 `""` | 匹配 claude-code 的 `asSystemPrompt([])` |
| 模型选择 | `LLMFactoryConfig.from_env().model` | Phase 3 简化：复用运行时模型；后续可配置轻量模型 |
| 内容截断 | 50K 字符 | 给 prompt + guidelines 留上下文空间；已被 `max_chars` 截断的内容不再二次截断 |
| LLM 失败处理 | 返回原始内容 | graceful degradation，不中断工具执行 |
| 空 response 处理 | 返回原始内容 | 同上 |
| 调用方式 | blocking（`llm_client.generate()`） | 匹配 claude-code 的 awaited 模式；RetryingLLMClient 已处理重试 |
| Abort 信号 | 不处理 | nano-multiagent 当前无 abort signal 机制；LLM 超时由 `timeout_seconds` 控制 |

---

## 4. 与 claude-code 的差异

| 维度 | claude-code | nano-multiagent（本设计） |
|---|---|---|
| LLMClient 获取 | 全局 `getAnthropicClient()` | `ToolContext.llm_client` 注入 |
| 模型 | Haiku 4.5（硬编码轻量模型） | 运行时默认模型（env 配置） |
| System prompt | 空数组 | 空字符串 `""` |
| 内容截断 | 100K 字符 | 50K 字符（留上下文空间） |
| 重试 | `withRetry()` 10 次 | `RetryingLLMClient` 20 次 |
| Abort 信号 | 检查 `AbortSignal` | 不支持（无 signal 机制） |
| 错误处理 | 抛异常 → `is_error` tool result | graceful fallback 到原始内容 |
| Guidelines | 预批准 vs 非预批准两套 | 统一一套宽松 guidelines（不区分域名类型） |

---

## 5. 测试策略

1. **单元测试**：`_make_prompt()` 格式化正确（包含 content + prompt + guidelines）
2. **Mock 测试**：`_process_with_prompt()` 用 mock LLMClient 验证调用参数和 fallback 行为
3. **集成测试**：`build_tool_registry(llm_client=...)` 正确注入，AgentRuntime 完整链路
4. **端到端测试**：实际 LLM 调用（可选，标记为 slow/e2e）
