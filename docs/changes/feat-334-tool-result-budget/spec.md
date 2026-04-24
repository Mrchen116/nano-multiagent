# Spec: Per-Tool Result Budget（工具结果单条预算与预览）

## 背景

当前 `AgentLoop` 中所有工具结果都原封不动地进入 LLM 上下文。随着工具能力扩展（`bash` 跑测试产生大段输出、`web_fetch` 拉取长网页、`task` 返回子 agent 的多轮对话），单条工具结果可能膨胀到数万甚至数十万字符，带来两个问题：

1. **上下文爆炸**：一次 turn 的 token 消耗被单条工具结果主导，挤占后续对话空间。
2. **模型注意力稀释**：模型在长输出中容易忽略关键信息。

Claude Code 通过 `maxResultSizeChars` + `persisted-output` preview 机制解决了这个问题。本 feature 参考其设计，但大幅简化实现逻辑，只保留最核心的 per-tool limit + preview 替换能力。

---

## Claude Code 参考实现（关键取舍）

### CC 完整机制

| 层级 | 说明 |
|------|------|
| **Per-tool limit** | 每个工具声明 `maxResultSizeChars`，超出则落盘 + preview 替换 |
| **Per-message aggregate budget** | 单条 user message 中所有 tool result 的总字符数不得超过 200K，超出则按大小降序替换最大的 fresh 结果 |
| **ContentReplacementState** | 跨 turn 状态（`seenIds` + `replacements`），保证同一结果每次决策一致，维护 prompt cache 前缀稳定 |
| **Candidate 分区** | `mustReapply`（已替换过）、`frozen`（已看过未替换）、`fresh`（新结果）|
| **GrowthBook 动态覆盖** | `tengu_hawthorn_window` 覆盖 aggregate budget、`tengu_satin_quoll` 覆盖 per-tool 阈值 |
| **空内容注入** | 空 tool result 注入 `"(toolName completed with no output)"`，防止模型误发 stop sequence |
| **Transcript 持久化** | 替换决策写入 JSONL，`ContentReplacementEntry` 保证 resume 后 byte-identical 复现 |

### 本 feature 的简化方向

| CC 机制 | 本 feature 决策 | 理由 |
|---------|----------------|------|
| Per-message aggregate budget | **砍掉** | 场景以串行工具为主，parallel batch 规模可控；per-tool limit 已能 cover 绝大多数爆炸场景 |
| ContentReplacementState | **砍掉** | 每次独立决策即可；tool_use_id 是 UUID，resume 时内容不变则决策不变，prompt cache 自然稳定 |
| Candidate 分区（mustReapply/frozen/fresh）| **砍掉** | 无 aggregate budget 就不需要分区 |
| GrowthBook 动态覆盖 | **砍掉** | 直接代码常量，后续如需动态调整再加配置层 |
| 空内容注入 | **砍掉** | 各工具 `serialize_result` 已自行处理空内容（Read 返回 warning、Bash 返回 `completed with no output`）|
| Transcript 持久化替换决策 | **砍掉** | 不持久化决策状态，resume 时从原始 Message 重新决策；结果不变 |
| 落盘路径（session-specific tool-results 子目录）| **简化** | 直接 `.nano/tool-results/{session_id}/{tool_call_id}.txt`，无需再嵌套 session 子目录 |

---

## 需求边界

### 做什么

1. 每个工具可声明 `max_result_size_chars: int | None = None`：
   - `None` = 无限，不压缩（Read 工具使用）
   - 省略 = 系统默认值 `50_000`
2. 工具结果序列化后，若字符数超过该工具的 limit，则：
   - 将完整内容保存到磁盘
   - 替换为 `<persisted-output>` 包裹的 preview 消息发给 LLM
3. Preview 取前 2000 字符，优先在换行处截断，保留尾部 `...` 提示。
4. Read 工具设为无限，确保文件内容永远完整进入上下文（避免 Read → 截断 → 再 Read 的循环浪费）。
5. 压缩发生在 `AgentLoop._serialize_tool_result()` 阶段，对 `Message.content` 和 `LLMMessage.content` 同时生效。

### 不做什么

1. **不做跨工具聚合预算**：N 个 parallel 工具结果的总和不做限制。
2. **不做 LLM-based 摘要**：preview 是纯文本截断，不调用模型生成摘要。
3. **不做图片内容压缩**：含图片 block 的结果直接跳过（当前仅 Read 工具返回图片，它已豁免）。
4. **不做运行时动态阈值调整**：常量配置，重启生效。
5. **不做子 agent / sidechain 的特殊路径**：统一走 session-scoped 落盘。

---

## 当前架构

```
AgentLoop.run()
  │
  ├── 工具执行 → ToolResult(output=原始对象, content=None)
  │
  ├── _serialize_tool_result(result)
  │      → 调用 tool.serialize_result() → str | list[dict]
  │      → 写入 result.content
  │
  ├── 构造 LLMMessage(role="tool", content=result.content)
  │
  └── yield Message(role="tool", content=result.content, metadata={"tool_output": result.output})
```

当前 `Message.content` 和 `LLMMessage.content` 都使用同一序列化结果，无中间压缩层。

---

## 验收标准

### A1 — 基本压缩

```python
# 给定一个虚拟工具，max_result_size_chars=100
# 当工具返回 500 字符的字符串
# 则 LLM 收到的 content 为 <persisted-output> 包裹的 preview（前 2000 字符，此处为全部 500 字符 + 提示文本）
# 且原始 500 字符被保存到 .nano/tool-results/{session_id}/{tool_call_id}.txt
```

> 注：500 < 2000，preview 展示全部内容，但包裹提示文本告知"已保存到文件"。如果不需要提示文本干扰小结果，则只在大于 limit 时触发。

修正：只在大于 limit 时触发压缩。500 > 100，触发压缩；preview = 500 字符（< 2000），无尾部 `...`。

### A2 — Read 工具豁免

```python
# Read 工具 max_result_size_chars = None
# 当读取一个 10 万字符的文件
# 则 LLM 收到完整 10 万字符，不触发压缩
```

### A3 — 默认值生效

```python
# Bash 工具未声明 max_result_size_chars
# 当返回 6 万字符的输出
# 则触发压缩（默认 50K limit）
```

### A4 — 含图片结果不压缩

```python
# Read 工具读取图片，serialize_result 返回 list[dict] 含 image block
# 则跳过压缩检查，原样发送
```

### A5 — 落盘文件可找回

```python
# 压缩后的 tool result
# 文件保存到 .nano/tool-results/{session_id}/{tool_call_id}.txt
# 文件内容为原始完整字符串
```

### A6 — 会话隔离

```python
# session_A 和 session_B 各跑一个大工具
# 落盘文件分别位于 .nano/tool-results/{session_id_A}/ 和 .nano/tool-results/{session_id_B}/
# 互不干扰
```

### A7 — 内存原始数据保留

```python
# 压缩后 Message.metadata["tool_output"] 仍保留原始结构化输出
# UI/render 层仍可从 metadata 读取完整结果用于展示
```

---

## 影响范围

| 模块 | 变更类型 | 说明 |
|------|---------|------|
| `agent.core.types.ToolSpec` | 扩展 | 新增 `max_result_size_chars` |
| `agent.core.tools.base.Tool` | 扩展 | 新增同名属性（Protocol + 实现类）|
| `agent.core.tools.registry.ToolRegistry` | 修改 | `list_specs()` 传递新字段 |
| `agent.core.agent.loop.AgentLoop` | 修改 | `_serialize_tool_result()` 集成压缩 |
| `agent.core.tools.result_budget` | 新增 | `ToolResultCompressor` |
| `agent.platform.tools.builtins.read` | 修改 | 显式声明 `max_result_size_chars = None` |
| `agent.platform.tools.builtins.bash` | 修改 | 显式声明或接受默认值 |
| `agent.platform.tools.builtins.web_fetch` | 修改 | 显式声明或接受默认值 |
| `agent.platform.tools.builtins.write` | 修改 | 显式声明或接受默认值 |
| `agent.platform.tools.builtins.edit` | 修改 | 显式声明或接受默认值 |
| `agent.platform.tools.builtins.task` | 修改 | 显式声明或接受默认值 |
