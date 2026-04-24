# Design: Per-Tool Result Budget（工具结果单条预算与预览）

## 范围

在 `AgentLoop` 的工具结果序列化路径上插入一层透明压缩： oversized tool result 落盘保存，LLM 收到 preview 替代文本。Read 工具无限豁免。

不涉及 aggregate budget、跨 turn 状态追踪、LLM 摘要、动态阈值。

---

## 架构总览

```
AgentLoop
  │
  ├── _tool_registry.get_tool(name) → Tool 实例
  │        • max_result_size_chars: int | None
  │
  ├── _serialize_tool_result(result)
  │        → tool.serialize_result() → raw_content: str | list[dict]
  │        → _compressor.maybe_compress(raw_content, ...)
  │              ├─ size ≤ limit  → 原样返回
  │              └─ size > limit  → 落盘 + 返回 <persisted-output> preview
  │        → 写入 result.content（压缩后）
  │
  ├── 构造 LLMMessage(content=result.content)
  │
  └── yield Message(content=result.content, metadata={"tool_output": result.output})
              ↑ LLM 看到的是压缩后内容
              ↑ UI 可从 metadata["tool_output"] 读取原始结构化数据
```

**新增/修改组件**（5 个文件）：

| 文件 | 动作 | 职责 |
|------|------|------|
| `agent/core/tools/result_budget.py` | 新增 | `ToolResultCompressor`：落盘 + preview 生成 |
| `agent/core/types.py` | 修改 | `ToolSpec` 增加 `max_result_size_chars` |
| `agent/core/tools/base.py` | 修改 | `Tool` Protocol 增加同名属性 |
| `agent/core/tools/registry.py` | 修改 | `list_specs()` 传递新字段 |
| `agent/core/agent/loop.py` | 修改 | `_serialize_tool_result()` 调用压缩器 |

**仅声明变更**（builtin tools）：

| 文件 | 动作 | 变更 |
|------|------|------|
| `agent/platform/tools/builtins/read.py` | 修改 | `max_result_size_chars = None` |
| `agent/platform/tools/builtins/*.py` | 可选修改 | 显式声明或接受默认值 50K |

---

## 组件设计

### 1. ToolSpec 扩展

**文件**：`src/agent/core/types.py`

```python
@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Describe a tool contract exposed to the model."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    is_concurrency_safe: bool = False
    max_result_size_chars: int | None = None   # NEW: None = Infinity
```

- `None` 语义：该工具的结果永不压缩（Read 工具）。
- 省略语义：由调用方填充默认值 `DEFAULT_MAX_RESULT_SIZE_CHARS`。
- `int` 语义：该工具结果字符数超过此值即触发压缩。

**为什么放在 ToolSpec 而不是仅在 Tool 实例上**：
`AgentLoop` 在 `_serialize_tool_result()` 阶段需要通过 tool name 反查 limit。`ToolSpec` 是 tool 的公开契约，和 `is_concurrency_safe` 类似，属于模型可见的元数据（虽然模型不直接消费此字段，但运行时通过 registry 查 spec 是标准路径）。

### 2. Tool Protocol 扩展

**文件**：`src/agent/core/tools/base.py`

```python
@runtime_checkable
class Tool(Protocol):
    """Describe the public contract every tool implementation must satisfy."""

    name: str
    description: str
    input_schema: Mapping[str, Any]
    is_concurrency_safe: bool
    max_result_size_chars: int | None = None   # NEW

    def run(self, args: Mapping[str, Any], ctx: "ToolContext") -> Mapping[str, Any]:
        ...

    def serialize_result(self, output: Any, error: str | None = None) -> str | list[dict[str, Any]]:
        ...
```

Builtin tool 类的声明示例（Read 工具）：

```python
class ReadTool:
    name = "read"
    is_concurrency_safe = True
    max_result_size_chars = None   # Infinity — read 结果永远完整进入上下文
    ...
```

Bash 工具（接受默认值）：

```python
class BashTool:
    name = "bash"
    is_concurrency_safe = False
    # max_result_size_chars 省略 → 使用默认 50K
    ...
```

### 3. ToolRegistry.list_specs() 传递新字段

**文件**：`src/agent/core/tools/registry.py`

```python
def list_specs(self) -> tuple[ToolSpec, ...]:
    return tuple(
        ToolSpec(
            name=tool.name,
            description=tool.description,
            input_schema=dict(tool.input_schema),
            is_concurrency_safe=getattr(tool, "is_concurrency_safe", False),
            max_result_size_chars=getattr(tool, "max_result_size_chars", None),   # NEW
        )
        for tool in self._tools.values()
    )
```

### 4. ToolResultCompressor（核心新增）

**文件**：`src/agent/core/tools/result_budget.py`

```python
import re
from pathlib import Path
from typing import Any

DEFAULT_MAX_RESULT_SIZE_CHARS = 50_000
PREVIEW_SIZE_CHARS = 2_000
PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"


class ToolResultCompressor:
    """Compress oversized tool results by persisting to disk and returning a preview.

    - Stateless: each call is independent. No cross-turn state needed.
    - Session-scoped: files saved under ``{base_dir}/{session_id}/{tool_call_id}.txt``.
    - Idempotent: same ``(session_id, tool_call_id)`` writes the same path;
      content is deterministic for a given tool_call_id, so overwrite is safe.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir.expanduser().resolve()

    def maybe_compress(
        self,
        content: str | list[dict[str, Any]],
        *,
        tool_name: str,
        tool_call_id: str,
        session_id: str,
        max_size_chars: int | None,
    ) -> str | list[dict[str, Any]]:
        """Return ``content`` unchanged if under limit, otherwise persist + preview."""
        # None = Infinity (Read tool, or explicit opt-out)
        if max_size_chars is None:
            return content

        # Skip non-text content (images, etc.)
        if isinstance(content, list):
            # Heuristic: if any block is non-text, skip compression.
            # Current only ReadTool returns lists, and it already has max_size=None.
            # This guard is defensive for future multimodal tools.
            if any(not (isinstance(b, dict) and b.get("type") == "text") for b in content):
                return content
            # Flatten text blocks to a single string for size check
            text_content = "\n".join(
                b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
            )
        else:
            text_content = content

        if len(text_content) <= max_size_chars:
            return content

        # --- Persist ---
        session_dir = self._base_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        filepath = session_dir / f"{tool_call_id}.txt"
        # Write atomically to avoid partial reads during concurrent access
        tmp_path = filepath.with_suffix(".tmp")
        tmp_path.write_text(text_content, encoding="utf-8")
        tmp_path.replace(filepath)

        # --- Preview ---
        preview = _generate_preview(text_content, PREVIEW_SIZE_CHARS)
        preview_msg = (
            f"{PERSISTED_OUTPUT_TAG}\n"
            f"Output too large ({len(text_content)} chars > {max_size_chars} limit). "
            f"Full output saved to: {filepath}\n\n"
            f"Preview (first {PREVIEW_SIZE_CHARS} chars):\n"
            f"{preview}\n"
            f"{'...' if len(text_content) > PREVIEW_SIZE_CHARS else ''}\n"
            f"{PERSISTED_OUTPUT_CLOSING_TAG}"
        )
        return preview_msg


def _generate_preview(text: str, max_chars: int) -> str:
    """Return first ``max_chars`` of text, cutting at newline when possible."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n")
    cut = last_newline if last_newline > max_chars * 0.5 else max_chars
    return text[:cut]
```

**设计决策**：

- **为什么不做 list[dict] 的压缩返回**：压缩后的 preview 是纯文本 `<persisted-output>...`，而 LLMMessage.content 接受 `str | list[dict]`。如果原始 content 是 `list[dict]`（含图片），我们已经跳过压缩。如果原始 content 是 `list[dict]` 纯文本块（当前无此场景），压缩后返回 str 是安全的——Claude API 的 tool result 可以是字符串。
- **为什么用 `write_text` + `replace`**：避免并发写入时产生残损文件。
- **为什么 base_dir 由外部注入**：方便测试（传临时目录），也方便 product 层配置。

### 5. AgentLoop 集成

**文件**：`src/agent/core/agent/loop.py`

**初始化**：`AgentLoop.__init__` 增加 `tool_result_compressor` 参数（可选，None 表示 feature 关闭）：

```python
class AgentLoop:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        model: str,
        ...
        tool_result_compressor: ToolResultCompressor | None = None,   # NEW
    ) -> None:
        ...
        self._tool_result_compressor = tool_result_compressor
```

**构造注入**：`AgentRuntime.__init__` 负责创建 compressor 并注入 loop：

```python
from agent.core.tools.result_budget import ToolResultCompressor, DEFAULT_MAX_RESULT_SIZE_CHARS

class AgentRuntime:
    def __init__(self, ...):
        ...
        # 落盘根目录：{workspace_root}/.nano/tool-results
        tool_results_dir = (repo_root or Path.cwd()) / ".nano" / "tool-results"
        compressor = ToolResultCompressor(tool_results_dir)
        self._loop = AgentLoop(
            ...,
            tool_result_compressor=compressor,
        )
```

**序列化时调用**：`_serialize_tool_result()` 修改：

```python
def _serialize_tool_result(self, result: ToolResult) -> str | list[dict[str, Any]]:
    """Route tool result serialization to the tool-specific adapter, then apply budget."""

    tool = self._tool_registry.get_tool(result.name) if self._tool_registry is not None else None
    if tool is not None and hasattr(tool, "serialize_result"):
        try:
            raw_content = tool.serialize_result(result.output, result.error)
        except Exception:
            raw_content = _fallback_serialize_tool_result(result)
    else:
        raw_content = _fallback_serialize_tool_result(result)

    # --- Apply per-tool result budget ---
    compressor = self._tool_result_compressor
    if compressor is not None and result.call_id and self._session_id_for_compressor:
        max_size = getattr(tool, "max_result_size_chars", None)
        raw_content = compressor.maybe_compress(
            raw_content,
            tool_name=result.name,
            tool_call_id=result.call_id,
            session_id=self._session_id_for_compressor,
            max_size_chars=max_size,
        )

    return raw_content
```

**session_id 传递问题**：`AgentLoop.run()` 在 turn 开始时已知 `state.session_id`，但 `_serialize_tool_result()` 是实例方法，不接收 session_id。解决方案：

- **方案 A**：`_serialize_tool_result` 增加 `session_id` 参数。改动最小，但签名变化。
- **方案 B**：`AgentLoop.run()` 开头把 `state.session_id` 写到实例变量 `_current_session_id`，`_serialize_tool_result()` 读取。简单但不太函数式。
- **方案 C**：`ToolResult` 增加 `session_id` 字段。改动面大。

**选择方案 B**（实例变量 `_active_session_id`），因为 `AgentLoop` 本身已经是 mutable 状态机（`_tool_registry`、`_llm_client` 都可热替换），加一个临时 session id 不破坏架构一致性：

```python
async def run(self, state: AgentState, ...) -> AsyncIterator[Message]:
    self._active_session_id = state.session_id
    try:
        ...
    finally:
        self._active_session_id = None
```

**_run_one_call 中更新 result.content**：当前 `_run_one_call` 内部已经调用了 `_serialize_tool_result` 并写入 `result.content`：

```python
result = ToolResult(
    call_id=parsed_call.call_id,
    name=parsed_call.name,
    output=result_payload,
    error=error_text,
    content=None,
)
content = self._serialize_tool_result(result)
result = ToolResult(
    call_id=result.call_id,
    name=result.name,
    output=result.output,
    error=result.error,
    content=content,   # ← 压缩后的 content
)
```

这段逻辑**无需修改**，`_serialize_tool_result` 内部完成压缩后返回的就是压缩后的 content。

---

## 数据流

### 正常 turn（工具结果未超限）

```
用户输入 → AgentLoop.run()
  → LLM 返回 tool_calls
  → _execute_tool_call() → tool.run() → ToolResult(output=...)
  → _serialize_tool_result()
       → tool.serialize_result() → raw_content (40K chars)
       → compressor.maybe_compress(limit=50K) → 未触发，原样返回
  → LLMMessage(content=raw_content)
  → yield Message(content=raw_content, metadata={"tool_output": output})
```

### 正常 turn（工具结果超限）

```
... → _serialize_tool_result()
       → tool.serialize_result() → raw_content (120K chars)
       → compressor.maybe_compress(limit=50K)
            → len=120K > 50K
            → write .nano/tool-results/{session_id}/{call_id}.txt (120K)
            → preview = 前 2000 字符
            → return "<persisted-output>...Preview..."
  → LLMMessage(content="<persisted-output>...")
  → yield Message(content="<persisted-output>...", metadata={"tool_output": output})
```

### Read 工具（无限豁免）

```
... → _serialize_tool_result()
       → ReadTool.serialize_result() → raw_content (200K chars)
       → compressor.maybe_compress(limit=None) → 直接返回，不检查大小
  → LLMMessage(content=完整 200K)
```

---

## Milestone 划分

### M1 — 核心压缩器 + 契约扩展

1. `src/agent/core/tools/result_budget.py`
   - `ToolResultCompressor`
   - `_generate_preview()`
   - 常量定义
2. `src/agent/core/types.py` — `ToolSpec.max_result_size_chars`
3. `src/agent/core/tools/base.py` — `Tool.max_result_size_chars`
4. `src/agent/core/tools/registry.py` — `list_specs()` 传递新字段
5. 单元测试：`maybe_compress` 的各种分支（未超限、超限、None limit、list content、空字符串）

### M2 — AgentLoop 集成 + 工具声明

6. `src/agent/core/agent/loop.py`
   - `__init__` 接收 `tool_result_compressor`
   - `_serialize_tool_result()` 集成压缩调用
   - `_active_session_id` 临时状态
7. `src/agent/core/agent/runtime.py`
   - 构造 `ToolResultCompressor` 并注入 loop
8. Builtin tools 声明 `max_result_size_chars`
   - `read.py` → `None`
   - `bash.py` → 默认（省略）或显式 `50_000`
   - `web_fetch.py` → 可显式 `30_000`（网页通常不需要全文）
   - 其余工具 → 默认或按需
9. 集成测试：模拟 oversized bash 输出，验证 LLMMessage 收到 preview、文件落盘、metadata 保留原始 output

---

## 拒绝的方案

| 方案 | 拒绝原因 |
|------|---------|
| 在 `build_prompt_messages()` 阶段压缩 | 太晚了，`Message.content` 已经确定；需要同时修改 `Message` 和 `LLMMessage`，引入不一致风险 |
| 在 `Tool.serialize_result()` 内部各自实现压缩 | 重复代码；每个 tool 都要处理落盘、preview 格式；违背 DRY |
| 使用 SQLite 存储 oversized 结果 | SQLite 不适合存大段文本；JSONL 已经用文件存储，工具结果也应该用文件 |
| 内存缓存压缩结果避免重复写入 | 同一 `tool_call_id` 不会在同一会话中出现两次；resume 时重新压缩即可 |
| 基于 token 数而非字符数限制 | token 计数需要 tiktoken 等依赖，增加复杂度；字符数是足够好的启发式 |
| 压缩后删除原始 `Message.content` | `Message.content` 是 LLM-facing 的，应该与 LLM 看到的一致；原始数据保留在 `metadata["tool_output"]` |
| 为 preview 调用 LLM 生成智能摘要 | 过度设计；纯文本截断已满足"让模型知道大概内容"的目标 |
| 支持 GrowthBook / 动态配置 | 当前无配置系统；先硬编码，需要时再抽象 |

---

## 关键权衡

### 1. 为什么不做 aggregate budget？

CC 的 aggregate budget（单条 user message 内所有 tool result 总和 ≤ 200K）是为了解决 **parallel 工具调用** 的叠加爆炸。Nano-multiagent 的 parallel batch 规模通常很小（2-3 个工具），且以串行为主。per-tool limit 已能将单次 turn 的 tool result 总量控制在合理范围（假设 3 个 parallel 工具各 50K = 150K）。如果未来 parallel 规模扩大，再追加 aggregate budget 是向后兼容的。

### 2. 为什么 stateless（无 ContentReplacementState）？

CC 需要 state 是因为：
- aggregate budget 的 "frozen" 语义要求记住哪些结果已经被看过但未替换；
- resume 时需要从 transcript 重建决策状态。

本 feature 只有 per-tool limit，决策逻辑是 "内容 > limit ? 替换 : 不替换"，这是一个纯函数。resume 时从原始 Message 重新运行同样的逻辑，得到**完全相同**的结果（因为原始内容不变）。因此不需要持久化决策状态。

### 3. 为什么 Read 工具设为 Infinity？

这是 CC 的同等设计。Read 工具的结果是模型后续编辑、分析的依据，截断会导致模型基于不完整信息做错误决策。此外，Read 结果如果被截断到文件，模型可能再用 Read 读那个文件，形成循环。

### 4. 落盘路径选 `.nano/tool-results/` 而非 session 子目录下再嵌套

feat-330 已使用 `.nano/sessions/{session_id}.jsonl`。工具结果落盘与 session 存储是独立 concern，平级目录更清晰。清理时可直接 `rm -rf .nano/tool-results/` 而不影响 session 历史。

### 5. preview 大小 2000 字符

参考 CC 的 2000 bytes。由于我们按字符计数，2000 字符 ≈ 2000-4000 bytes（取决于内容），与 CC 同数量级。足够让模型感知内容类型和结构，又不占太多上下文。
