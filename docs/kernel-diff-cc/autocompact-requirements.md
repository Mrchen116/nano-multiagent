# Autocompact 改进需求

> 基于 Claude Code 的 autocompact 实现，对齐 nano-multiagent 的压缩能力。

---

## 背景

当前 nano-multiagent 的压缩实现（`CompactionSummarizer`）过于简陋：

- Prompt 只有一句话中文指令，无结构化输出要求
- 压缩使用当前主模型但无 prompt cache 复用，每次重发完整历史
- 压缩结果被处理为 system message 插入 context，无防套娃机制
- 压缩后无任何状态恢复，模型丢失最近读取的文件上下文

本需求文档聚焦两个核心改进：
1. **复用主 agent 上下文做压缩**：在已有消息历史基础上追加 summary user message，让模型自己总结自己
2. **全面的 summary prompt**：引入 Claude Code 级别的结构化英文 prompt（9 章节）

---

## 需求清单

### REQ-1：复用主 agent 上下文前缀做压缩

**现状**：`CompactionSummarizer` 构造一个独立请求，system prompt 只有一句话，user prompt 只有消息拼接。

**目标**：压缩请求应复用主 agent 的完整上下文前缀（system prompt + 历史消息），在此基础上追加一个 summary user message，让模型基于已有上下文生成总结。

**实现要点**：
- 调用压缩时，将 `dropped_messages` 作为历史消息传入 LLM 请求
- 在消息数组末尾追加一个 `user` 角色的 summary request message
- 使用主 loop 的 system prompt（或压缩专用的简化 system prompt）
- 使用当前主模型（低成本模型 / prompt caching 后续迭代再做，参见 REQ-6）

---

### REQ-2：全面的英文 Summary Prompt

**现状**：
```python
SUMMARY_SYSTEM_PROMPT = (
    "Summarize conversation context with fixed sections: "
    "目标, 约束, 进展, 决策, 下一步, 关键上下文. Keep it concise."
)
```

**目标**：引入 Claude Code 级别的结构化英文 prompt，要求模型按 9 个固定章节输出总结。

**Prompt 章节**（对标 CC 的 `BASE_COMPACT_PROMPT`）：

1. **Primary Request and Intent**：用户的所有显式请求和意图
2. **Key Technical Concepts**：涉及的重要技术概念、框架和模式
3. **Files and Code Sections**：具体文件和代码片段，包含完整代码引用和修改说明
4. **Errors and fixes**：遇到的错误及修复方式，用户的具体反馈
5. **Problem Solving**：已解决的问题和正在进行的排查
6. **All user messages**：列出所有非工具结果的用户消息（关键反馈和意图变化）
7. **Pending Tasks**：用户明确要求但尚未完成的任务
8. **Current Work**：压缩前一刻正在做的具体工作，包含文件名和代码片段
9. **Optional Next Step**：基于最近用户请求的直接下一步（需引用原话）

**防工具调用**：prompt 中需包含明确的工具调用禁止指令（"Do NOT call any tools"），因为压缩请求 max_turns=1，任何工具调用都会导致无文本输出。

**无自定义指令**：本次不实现 `customInstructions` 追加功能。

---

### REQ-3：输出格式处理

**现状**：直接取模型返回的 content 作为 summary，无格式校验和处理。

**目标**：要求模型输出包含 `<analysis>` 和 `<summary>` 标签，处理后只保留 `<summary>` 内容。

**处理流程**（对标 CC 的 `formatCompactSummary`）：
1. 剥离 `<analysis>...</analysis>` 草稿区（仅用于提升模型输出质量，不含有效信息）
2. 提取 `<summary>...</summary>` 内容，替换为 `"Summary:\n" + content`
3. 清理多余空行

---

### REQ-4：Post-Compact 文件恢复

**现状**：压缩后无任何上下文恢复，模型需重新读取文件。

**目标**：压缩后恢复最近读取的最多 5 个文件，让模型保留文件内容上下文。

**范围限制**：
- 仅做文件恢复，不做 skill、plan、async agent 等恢复
- 文件选择基于最近读取时间排序，取前 5 个
- 无 token budget 限制（简化实现，后续可优化）

**实现要点**：
- 在 `CompactionApplier.apply()` 中，压缩完成后读取最近文件列表
- 将文件内容作为 attachment 或额外的 user message 插入 post-compact context
- 需要和 `readFileState` 或类似机制对接（确认 nano 是否有文件读取追踪）

---

### REQ-5：边界标记（本次不做）

**决策**：边界标记（`SystemCompactBoundaryMessage`）需要 session 级别的消息日志支持，当前 nano 无此机制，本次不实现。

**影响**：
- 无防重复压缩机制，多次压缩可能导致 "summary of summary" 套娃
- 无压缩前后的 token 计数元数据
- 无 UI 级别的压缩边界展示

**后续可补充**：引入专门的 boundary 消息类型或标记 system message，实现 `getMessagesAfterCompactBoundary()` 逻辑。

---

### REQ-6：低成本模型 / Prompt Caching（本次不做）

**决策**：复用当前主模型做压缩，不引入专门的 summary 模型，不做 prompt cache sharing。

**原因**：
- nano 当前无 forked agent / prompt cache 机制，直接复用主模型是最小改动路径
- 低成本模型切换和 cache 优化可作为后续独立迭代

**已知风险**：长会话压缩时，重发完整历史 + summary prompt 会导致较高的 token 成本。

---

### REQ-7：自定义指令（本次不做）

**决策**：不实现用户/hook 提供的 `customInstructions` 追加到 summary prompt 的功能。

---

## 改动范围预估

| 文件 | 改动内容 |
|------|----------|
| `src/agent/core/agent/compaction/summarizer.py` | 重写 `summarize()` 方法，引入结构化英文 prompt，实现输出格式处理 |
| `src/agent/core/agent/compaction/prompts.py`（新建） | 定义全面的英文 summary prompt 模板 |
| `src/agent/core/agent/compaction/applier.py` | 压缩完成后恢复最近读取的 5 个文件 |
| `src/agent/core/agent/runtime.py` | 确认压缩调用的上下文传递方式，确保历史消息完整传入 |

---

## 验收标准

1. 压缩 prompt 为英文，包含 9 个固定章节要求
2. 压缩请求复用主 agent 的上下文历史，仅追加 summary user message
3. 模型输出包含 `<analysis>` 和 `<summary>` 标签，最终只保留 `<summary>` 内容
4. 压缩后最近读取的最多 5 个文件被恢复并插入 context
5. 不引入边界标记消息类型、不引入低成本模型、不引入自定义指令
