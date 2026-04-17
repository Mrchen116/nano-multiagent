# Read Tool mtime 去重 — 架构设计文档

## 目标

1. **最高优先级**：实现 mtime 去重（`file_unchanged`），避免重复读取未变更文件，节省 `cache_creation` token。
2. **架构升级**：把 Tool 业务语义与 LLM 协议序列化的**控制权**下放到每个工具自身，对齐 claude-code 的分层理念，同时避免基础设施级重构。

---

## 1. 核心机制：mtime 去重

### 1.1 双指纹判断

用 `(mtime_ms, size)` 联合判断是否 unchanged，防御毫秒级 mtime 精度不足。

```python
key = (file_path, offset, limit)
current = (floor(mtime_ms), size)

if key in cache and cache[key] == current:
    return {"type": "file_unchanged", "file": {"filePath": display_path}}
```

- mtime 获取失败（`None` 或异常）→ 跳过缓存，正常读取。
- 外部修改、内部 Edit/Write 修改 → `(mtime, size)` 任一变化即失效，统一防御。

### 1.2 缓存设计

- **`FileStateCache`**：轻量级 LRU（容量 128），只存元数据，不存 content。
  - key: `(file_path, offset, limit)`
  - value: `(mtime_ms, size)`
- **`SessionFileReadCache`**：按 `session_id` 隔离 `FileStateCache`，避免 `AgentRuntime` 直接操作裸字典。

### 1.3 传递链路

1. `ToolContext` 新增 `read_file_state: FileStateCache | None = None`
2. `ToolRegistry.execute()` 签名增加 `read_file_state`，透传给 `ToolContext`
3. `AgentLoop._execute_tool_call()` 接收 `read_file_state` 并注入 `ToolContext`
4. `AgentRuntime` 在 `_execute_loop` 前，通过 `SessionFileReadCache` 拿到当前 session 的 `FileStateCache`，传给 `AgentLoop.run()`

### 1.4 Edit / Write 零改动

写工具不碰 read 缓存。所有修改来源（内部/外部）统一由 `(mtime_ms, size)` 双指纹防御。

---

## 2. 协议适配层设计（务实方案）

### 2.1 为什么不改 `Message.content` / `LLMMessage.content` 类型

当前 `Message.content` 和 `LLMMessage.content` 都是 `str`。如果改成 `str | list[Mapping[str, Any]]`：

- **类型污染**：compaction、summarizer、session storage、UI 层等所有消费 `content` 的地方都要加分支防御。
- **序列化复杂度**：历史消息需要落盘，虽然 `list` 也能 JSON 序列化，但反序列化后所有代码都要处理"可能是 list"的情况。
- **compaction 降级困难**：context summary 时若 content 是 image block 数组，需要额外的降级逻辑才能转成文本给 summarizer。

claude-code 从第一天就用 `ContentBlockParam[] | string` 作为消息原语，所以 Tool 直接返回 array 是自然的。nano-multiagent 不是，现在硬改等于做一次基础设施重构，**不应与 mtime 去重这个具体需求混在一起**。

### 2.2 当前系统的实际通路

nano-multiagent 其实已经支持 image block，只是走了一条"扭曲但可用"的路：

```
ReadTool dict -> json.dumps -> LLMMessage(str)
                    -> AnthropicMapper json.loads -> 还原成 block array
```

这说明：**字符串只是 transport wrapper，真正的信息没有丢失**。`file_unchanged` 也可以走这条路——ReadTool 的 `serialize_result` 返回一段 stub 字符串即可直接给 LLM。

### 2.3 核心问题：序列化控制权不在 Tool 手里

当前链路：

```
Tool.run() -> dict -> ToolRegistry -> AgentLoop -> json.dumps -> LLMMessage(str)
```

`AgentLoop` 用全局的 `_serialize_tool_result_content()` 把 dict 包成 JSON，**Tool 无法决定最终呈现形式**。这导致：
- `file_unchanged` 无法优雅插入（会被包在 JSON wrapper 里）
- `GlobTool` 无法自己 join 文件名并加 truncation 提示
- `BashTool` 无法自己拼接 stdout/stderr 的文案

### 2.4 新方案：把序列化下放到 Tool 层

#### `Tool` Protocol 增加必选方法

```python
class Tool(Protocol):
    name: str
    description: str
    input_schema: Mapping[str, Any]
    is_concurrency_safe: bool

    def run(self, args: Mapping[str, Any], ctx: "ToolContext") -> Mapping[str, Any]:
        ...

    def serialize_result(self, output: Any) -> str:
        """将本工具的结构化输出序列化为 LLM tool_message content 字符串。"""
        ...
```

#### `ToolResult` 新增 `content` 字段

```python
@dataclass(frozen=True, slots=True)
class ToolResult:
    call_id: str
    name: str
    output: Any = None          # 结构化数据：给 Hook / Run Registry / 调试
    error: str | None = None
    content: str | None = None  # LLM-facing 字符串：给 LLM 和 History
```

#### 流转链路

```
ReadTool.run()
    │
    ▼
返回 {"type": "file_unchanged", "file": {...}}
    │
    ▼
ToolRegistry.execute() ──► Hook observe (output=dict) ──► Run Registry 持久化
    │
    ▼
AgentLoop ──► ToolResult(output=dict, content="File unchanged since last read...")
    │
    ├── LLMMessage(content=ToolResult.content) ──► 发给 Anthropic API
    │
    └── AgentRuntime 存 History ──► Message(content=ToolResult.content)
```

**关键点**：
- `output` = **内部结构化数据**（机器看）
- `content` = **LLM 字符串**（模型看）
- `AgentLoop` 只调用一次 `serialize_result()`，结果写进 `ToolResult.content`
- `AgentRuntime` 存 history 时**直接复用 `ToolResult.content`**，不再重复序列化

#### 全局辅助函数

`src/agent/core/tools/serialization.py` 仅提供：

```python
def json_serialize(output: Any) -> str:
    try:
        return json.dumps(output, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return str(output)
```

#### `ReadTool.serialize_result()` 实现

```python
def serialize_result(self, output: Any) -> str:
    if isinstance(output, Mapping) and output.get("type") == "file_unchanged":
        file_path = output.get("file", {}).get("filePath", "unknown")
        return (
            "File unchanged since last read. The content from the earlier "
            "Read tool_result in this conversation is still current — "
            "refer to that instead of re-reading."
            f" ({file_path})"
        )
    return json_serialize(output)
```

其他 built-in 工具先统一 `return json_serialize(output)` 保持兼容。

---

## 3. 改动文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `src/agent/core/tools/file_state_cache.py` | 新增 | `FileStateCache` + `SessionFileReadCache` |
| `src/agent/core/tools/serialization.py` | 新增 | `json_serialize` helper |
| `src/agent/core/tools/base.py` | 修改 | `Tool` Protocol 增加 `serialize_result`；`ToolContext` 增加 `read_file_state` |
| `src/agent/core/tools/registry.py` | 修改 | `execute()` 透传 `read_file_state`；增加 `get_tool()` alias |
| `src/agent/core/types.py` | 修改 | `ToolResult` 增加 `content` 字段 |
| `src/agent/platform/tools/builtins/read.py` | 修改 | mtime 去重 + `file_unchanged` 返回 + `serialize_result()` |
| `src/agent/platform/tools/builtins/bash.py` | 修改 | 增加 `serialize_result()`，保持兼容 |
| `src/agent/platform/tools/builtins/write.py` | 修改 | 增加 `serialize_result()`，保持兼容 |
| `src/agent/platform/tools/builtins/edit.py` | 修改 | 增加 `serialize_result()`，保持兼容 |
| `src/agent/platform/tools/builtins/task.py` | 修改 | 增加 `serialize_result()`，保持兼容 |
| `src/agent/core/agent/loop.py` | 修改 | 注入缓存 + `ToolResult` 带 `content` + 调用 `tool.serialize_result()` |
| `src/agent/core/agent/runtime.py` | 修改 | `_execute_loop` 前获取 session 缓存 + history 直接写 `ToolResult.content` |

---

## 4. 设计原则

- **可读性强**：Tool 层只表达"发生了什么"，每个工具自己决定"怎么给 LLM 看"。
- **架构清晰**：业务逻辑、协议适配、运行时调度三层分离；协议适配是工具契约的一部分，不是全局硬编码。
- **运行稳定**：去重是客户端纯优化，不依赖服务端；双指纹防御精度问题；Edit/Write 零改动降低回归风险。
- **风险可控**：不改 `Message.content` / `LLMMessage.content` 类型，不触发基础设施级重构，只通过 additive change 达成目标。

---

## 5. 后续待设计的 Read 工具优化

以下内容已识别为高价值优化点，但**不在本次实施范围内**，后续逐步进行专项设计。

### 5.1 大文件读取性能（双路径优化）

**问题**：当前 `read.py` 使用一次性 `path.read_text()` 再 `splitlines()`，大文件会全量进内存。  
**参考 claude-code**：`readFileInRange.ts` 实现 fast path（< 10 MB 直接读）+ streaming path（`createReadStream` 逐行解析，只保留目标范围内的行）。  
**待设计**：是否引入 Python 的 streaming read 双路径实现，以及 abort/cancel 信号支持。

### 5.2 图像压缩与 Token Budget 控制

**问题**：当前图像直接原图 base64，无压缩、无 resize，既浪费 token 也可能触发 API 大小限制。  
**参考 claude-code**：依赖 `sharp` 做多阶段压缩（标准 resize → downsample → 激进压缩 → 400x400 JPEG quality 20 fallback）。  
**待设计**：选择 `PIL`/`pillow` 还是其他图像处理方案，以及多阶段压缩策略和 token budget 控制逻辑。

### 5.3 文本输出加行号

**问题**：`read.py` 的 description 声称输出是 "cat -n format"，但实际代码并没有添加行号前缀，描述与实现不符。  
**参考 claude-code**：`addLineNumbers` 函数确实在每行前面加了行号。  
**待设计**：行号格式统一方案，以及是否需要将其纳入输出 schema 的一部分。

### 5.4 安全与沙盒增强

**问题**：当前缺少设备文件黑名单、二进制扩展名检查、ENOENT 时的模糊路径建议。  
**参考 claude-code**：
- 设备文件黑名单：`/dev/zero`、`/dev/urandom`、`/dev/stdin`、`/dev/tty`、`/dev/fd/0-2`、`/proc/*/fd/0-2` 等
- 二进制扩展名检查：`hasBinaryExtension` 拦截非文本文件（放行 PDF/图片/SVG）
- ENOENT 模糊匹配：`findSimilarFile` 自动建议相似文件
- macOS 截图特殊空格兼容  
**待设计**：安全增强的优先级排序，以及如何在 `safety` 层与 Tool 层之间划分职责。

### 5.5 PDF 与 Notebook 支持

**问题**：当前 Read 工具完全不支持 `.pdf` 和 `.ipynb`。  
**参考 claude-code**：
- PDF：支持 `pages` 参数提取特定页，大 PDF 自动转图片页，小 PDF 直接作为 document block 发送
- Notebook：解析 `.ipynb` 为 cells 数组，支持代码+文本+可视化输出  
**待设计**：是否需要引入 `pypdf`/`pdf2image` 和 `nbformat`，以及输出 schema 如何扩展。

### 5.6 更细粒度的错误类型

**问题**：当前所有读取错误都统一抛 `ToolError`，难以区分"文件太大"、"token 超限"、"图像 resize 失败"等场景。  
**参考 claude-code**：`FileTooLargeError`、`MaxFileReadTokenExceededError`、`ImageResizeError` 等专用异常类。  
**待设计**：错误类型分层方案，以及是否需要与 Tool 框架的错误处理协议对齐。
