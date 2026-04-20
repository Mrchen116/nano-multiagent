# Autocompact Spec & Design

## 设计原则

对齐 CC 完整 compact（非 session-memory compact）的最终模型上下文结构：
- 旧历史**整体被替换**为 summary user message + attachments user messages
- **不保留**原始消息尾巴（kept_events 归零）
- 所有 post-compact 内容都是 **user message**（无 system message）
- systemPrompt 单独存在（messages 列表外），不受 compact 影响

---

## 当前架构速览

```
AgentRuntime._compact_session()
  ├── CompactionPlanner.plan()      → 选择安全切点，保证不分割 tool call/result 对
  ├── CompactionSummarizer.summarize() → LLM 生成总结（当前：独立请求，极简 prompt）
  └── CompactionApplier.apply()     → 调用 session_manager.append_compaction() 写入 CompactionEntry

SessionManager.list_turn_messages() 的 compaction 语义：
  - 遍历 events，找到最新的 CompactionEntry
  - 只保留 first_kept_event_id 之后的 TURN_APPENDED events
  - 在消息数组开头插入一条 role="system" 的 summary message
```

---

## 设计目标

| 目标 | 说明 |
|------|------|
| 复用主 agent 上下文 | 压缩请求不是独立请求，而是在主 agent 的完整消息历史基础上追加 summary user message |
| 全面 summary prompt | 引入 9 章节英文结构化 prompt，含防工具调用指令 |
| 输出格式处理 | 剥离 `<analysis>`，只保留 `<summary>` 内容 |
| 文件恢复 | 压缩后恢复最近读取的最多 5 个文件内容到 context |
| 不保留原始尾巴 | 对标 CC 完整 compact：旧历史整体替换为 summary + attachments，无 kept_events |

---

## 已确认决策

| ID | 决策 | 说明 |
|----|------|------|
| Q1 | `max_tokens = 20_000` | 对标 CC 的 `MAX_OUTPUT_TOKENS_FOR_SUMMARY` |
| Q2 | 渲染后的完整 system prompt | 复用 `build_system_prompt()` 输出，含 tools/skills/cwd/datetime |
| Q3 | 从 `SessionFileState` 按 offset/limit 恢复 | 取最近 5 个文件，按记录的行范围读取，不是全文 |
| Q4 | 改为 user message | 对标 CC，加续接前缀 |
| Q5 | **不保留 kept_events** | 对标 CC 完整 compact：旧历史整体替换为 summary + attachments |

---

## 详细设计

### 1. 最终发给 LLM 的上下文结构（目标）

```txt
[systemPrompt 单独参数]  ← AgentLoop 的 system prompt，不受 compact 影响
systemPrompt + systemContext

[messages 列表]
0. user message (isMeta)        ← prependUserContext（如有，本次不改）
   content: <system-reminder>...</system-reminder>

1. user message (isCompactSummary)
   content:
   "This session is being continued from a previous conversation that ran out of context.
   The summary below covers the earlier portion of the conversation.

   Summary:
   1. Primary Request and Intent: ...
   2. Key Technical Concepts: ...
   ...

   Continue the conversation from where it left off without asking the user any further questions.
   Resume directly — do not acknowledge the summary..."

2. user message (isMeta)        ← 恢复文件（最多 5 个）
   content: "[Post-compact file restore] {file} (lines {o}-{l}):\n{content}"

3+. ...                         ← 当前 turn 的正常消息
```

### 2. Prompt 模板（新建 `src/agent/core/agent/compaction/prompts.py`）

定义 `BASE_COMPACT_PROMPT`，对标 CC 的 `getCompactPrompt()`：

- **NO_TOOLS_PREAMBLE**：明确禁止任何工具调用（"Do NOT call any tools"），因为压缩请求 max_tokens 有限且只有一个 turn
- **DETAILED_ANALYSIS_INSTRUCTION**：要求按时间线逐条分析每个消息段
- **9 个固定章节**：Primary Request、Key Technical Concepts、Files & Code、Errors & Fixes、Problem Solving、All User Messages、Pending Tasks、Current Work、Optional Next Step
- **NO_TOOLS_TRAILER**：再次提醒禁止工具调用
- **输出格式要求**：`<analysis>` 草稿区 + `<summary>` 结构化块

```python
COMPACT_MAX_OUTPUT_TOKENS = 20_000
```

### 3. Summarizer 签名变更（`src/agent/core/agent/compaction/summarizer.py`）

当前签名：
```python
def summarize(self, *, session_id: str, dropped_messages: Sequence[Message]) -> str:
```

新签名：
```python
def summarize(
    self,
    *,
    session_id: str,
    system_prompt: str | None,
    dropped_messages: Sequence[Message],
) -> str:
```

**请求构建逻辑**（复用主 agent 上下文前缀）：

```python
messages: list[LLMMessage] = []
if system_prompt:
    messages.append(LLMMessage(role="system", content=system_prompt))
for msg in dropped_messages:
    messages.append(LLMMessage(role=msg.role, content=msg.content))
messages.append(LLMMessage(role="user", content=get_compact_prompt()))

response = self._llm_client.generate(
    LLMGenerateRequest(
        session_id=session_id,
        model=self._model,
        messages=tuple(messages),
        stream=False,
        max_tokens=COMPACT_MAX_OUTPUT_TOKENS,
    )
)
```

### 4. 输出格式处理（`src/agent/core/agent/compaction/prompts.py`）

新增 `format_compact_summary(summary: str) -> str`：

1. 用正则剥离 `<analysis>[\s\S]*?</analysis>`
2. 提取 `<summary>([\s\S]*?)</summary>`，替换为 `"Summary:\n{content.strip()}"`
3. 清理多余空行（`\n\n+` → `\n\n`）
4. fallback：如果模型未按格式输出，直接返回原始文本（strip 后）

新增 `get_compact_user_summary_message(summary: str) -> str`：
- 包装 formatted summary，前加 continuation prefix，后加 resume instruction

### 5. 文件恢复（Post-Compact File Restore）

**流程**：先取出信息，再清空状态。

```
AgentRuntime._compact_session()
  ├── 从 SessionFileState 取出最近 5 个 FileReadState
  ├── pop session_file_states（清空）
  └── 把取出的 5 个文件内容作为 restored_files 传给 CompactionApplier
```

实现要点：
- `SessionFileState._states` 是 OrderedDict，`move_to_end` 保证最近读取的在末尾
- 遍历 `reversed(self._states.values())` 取前 5 个
- 用 `offset`（1-indexed）和 `limit` 读取文件对应行范围
- 内容格式：`"[Post-compact file restore] {file_path} (lines {offset}-{offset+limit-1}):\n{content}"`
- 如果 `offset` 或 `limit` 为 `None`，回退到全文读取
- 文件不存在或读取失败则跳过

**恢复文件在 context 中的形态**：作为额外的 **user message** 跟在 summary 之后。每个文件可单独一条 message，或合并成一条 message（"Here are the recently accessed files:\n\n[file1]...\n\n[file2]..."）。

### 6. CompactionPlanner：只总结最新 compaction 之后的消息

**问题**：如果 session 已经被 compact 过一次，旧的 turn_appended events 仍然存在于 events 列表中。如果不做过滤，summarizer 会把**所有历史**（包括已被 summary 过的）重新发给模型，导致输入 token 随 compact 次数线性膨胀。

**CC 的行为**：`compactConversation` 内部用 `getMessagesAfterCompactBoundary(messages)` 只取上次 compact boundary 之后的消息来总结。

**目标行为**：`CompactionPlanner.plan()` 找到最新的 `CompactionEntry`，只取它之后的 `TURN_APPENDED` events 作为 `dropped_events`。

```python
def plan(self, *, events: Sequence[SessionEntry | CompactionEntry], reason: CompactionReason) -> CompactionPlan | None:
    # 找到最新 CompactionEntry 的索引
    latest_compaction_idx = -1
    for i, event in enumerate(events):
        if isinstance(event, CompactionEntry):
            latest_compaction_idx = i

    # 只取最新 compaction 之后的 TURN_APPENDED events
    turn_events = tuple(
        event for event in events[latest_compaction_idx + 1:]
        if isinstance(event, SessionEntry) and event.kind is SessionEntryKind.TURN_APPENDED
    )

    if not turn_events:
        return None

    # 不保留 kept_events，旧历史整体被 summary 替代
    return CompactionPlan(
        reason=reason,
        first_kept_event_id="",           # 无保留消息
        dropped_events=turn_events,
        kept_events=(),
    )
```

### 7. 消息插入方式（list_turn_messages）

**当前行为**：
- 找到最新 CompactionEntry
- 保留 `first_kept_event_id` 之后的 TURN_APPENDED events
- 在开头插入一条 role="system" 的 summary message

**目标行为**：
- `list_turn_messages()` 不再按 `first_kept_event_id` 过滤消息（该字段在新语义下为空字符串）
- 找到最新 CompactionEntry 后，**忽略所有在此之前的 TURN_APPENDED events**（因为无 kept_events 尾巴）
- 只保留 CompactionEntry 之后的 TURN_APPENDED events（即当前 turn 的消息）
- 在保留的消息**之前**插入：
  1. summary user message（带 continuation prefix + resume instruction）
  2. restored files user message(s)

**注意**：`entry_id` 是随机字符串，不能用于排序比较。改为用**索引位置**判断——找到 `latest_compaction` 在 events 列表中的索引，只收集它之后的事件。

```python
def list_turn_messages(self, session_id: str) -> tuple[Message, ...]:
    loaded = self._store.load_session(session_id)
    if loaded is None:
        return ()

    latest_compaction_idx = -1
    for i, entry in enumerate(loaded.events):
        if isinstance(entry, CompactionEntry):
            latest_compaction_idx = i

    # 只收集最新 compaction 之后的 TURN_APPENDED events
    messages: list[Message] = []
    for entry in loaded.events[latest_compaction_idx + 1:]:
        if entry.kind is not SessionEntryKind.TURN_APPENDED:
            continue
        message = self._message_from_turn_event(entry)
        if message is not None:
            messages.append(message)

    if latest_compaction_idx >= 0:
        latest_compaction = loaded.events[latest_compaction_idx]
        # 1. Summary user message（插在最前面）
        summary_content = get_compact_user_summary_message(latest_compaction.summary)
        summary_message = Message(
            message_id=f"{latest_compaction.entry_id}:summary",
            role="user",
            content=summary_content,
            metadata={"compaction_summary": True},
        )
        messages.insert(0, summary_message)

        # 2. 恢复文件 user message（跟在 summary 后面）
        restored_files = latest_compaction.data.get("restored_files", [])
        if restored_files:
            files_content = "\n\n".join(restored_files)
            files_message = Message(
                message_id=f"{latest_compaction.entry_id}:files",
                role="user",
                content=files_content,
                metadata={"compaction_files": True},
            )
            messages.insert(1, files_message)

    return tuple(messages)
```

### 8. CompactionApplier 签名扩展

```python
def apply(
    self,
    *,
    session_id: str,
    plan: CompactionPlan,
    summary: str,
    restored_files: Sequence[str] = (),
) -> CompactionResult:
    entry = self._session_manager.append_compaction(
        session_id,
        first_kept_event_id=plan.first_kept_event_id,
        summary=summary,
        data={
            "reason": plan.reason.value,
            "restored_files": list(restored_files),
        },
    )
    return CompactionResult(
        reason=plan.reason,
        entry_id=entry.entry_id,
        first_kept_event_id=entry.first_kept_event_id,
        summary=entry.summary,
        dropped_event_ids=tuple(event.entry_id for event in plan.dropped_events),
        kept_event_ids=(),  # 始终为空
    )
```

### 9. 调用链路变更

```
AgentRuntime._compact_session()
  ├── build_system_prompt(...)                    ← 渲染完整 system prompt
  ├── CompactionPlanner.plan()
  │      └── dropped_events = 所有 turn_appended events
  │      └── kept_events = ()
  ├── CompactionSummarizer.summarize(
  │      system_prompt=rendered_system_prompt,
  │      dropped_messages=...,                     ← 全部历史消息
  │   )
  │      └── 构建 LLM 请求：system + history + summary user message
  │      └── format_compact_summary() 处理输出
  ├── 从 SessionFileState 取出最近 5 个文件
  ├── pop session_file_states（清空）
  ├── CompactionApplier.apply(
  │      summary=...,
  │      restored_files=[file1_content, file2_content, ...],
  │   )
  └── 触发 "session_compact" observe hook

SessionManager.list_turn_messages()
  └── 忽略 compaction 之前的所有 TURN_APPENDED events（无 kept 尾巴）
  └── 在保留消息之前插入：
      1. summary user message（continuation prefix + resume instruction）
      2. restored files user message

AgentLoop.build_prompt_messages()
  └── 正常处理 history_messages（其中已包含 summary + files + 当前 turn 消息）
  └── 在开头插入 system prompt（不受 compact 影响）
```

### 10. 回退策略

如果模型未按格式输出（无 `<summary>` 标签）：
- `format_compact_summary()` 直接返回原始文本（strip 后）
- 如果 LLM 调用失败（异常）：`CompactionSummarizer` 保留现有 fallback summary 机制

---

## 改动范围

| 文件 | 改动内容 |
|------|----------|
| `src/agent/core/agent/compaction/prompts.py`（新建） | 完整英文 prompt、输出格式处理、continuation wrapper |
| `src/agent/core/agent/compaction/summarizer.py` | 新签名（+system_prompt）、复用上下文前缀构建请求、调用 format_compact_summary |
| `src/agent/core/agent/compaction/applier.py` | 扩展签名（+restored_files）、写入 data |
| `src/agent/core/agent/compaction/planner.py` | kept_events 始终为空 |
| `src/agent/core/session/manager.py` | list_turn_messages：不保留 kept 尾巴、summary 改 user message、插入 restored files |
| `src/agent/core/agent/runtime.py` | _compact_session：渲染 system prompt、文件恢复、传 restored_files |

---

## 边界说明

- **不保留原始消息尾巴**：`CompactionPlanner` 的 `kept_events` 始终为空。如果用户需要"保留最近 N 条"的行为，后续可引入 session-memory compact 路径作为补充。
- **无 boundary marker**：边界标记（SystemCompactBoundaryMessage）本次不实现，因为没有独立的 session 日志系统。`CompactionEntry` 本身充当日志中的边界。
- **无 attachments 抽象**：恢复文件直接作为 user message content，不引入 CC 的 attachment message 类型。未来如需支持 plan/skills/MCP 恢复，再引入 attachments 抽象。
- **无 PTL retry / circuit breaker**：这些 CC 的容错机制本次不实现，保留现有异常 fallback。
- **无自定义指令**：`customInstructions` 追加到 summary prompt 的功能本次不实现。
- **已知架构限制：tool call 信息丢失**：`_message_from_turn_entry()` 只取 `message_id`、`role`、`content`，`metadata` 中的 `tool_calls` 和 `tool_call_id` 被忽略。这意味着 summarizer 看到的 assistant tool call 消息只有空 content，"Files and Code" 章节可能缺少 Read/Edit 的具体信息。这是 `Message` 类型不支持 Anthropic content blocks（tool_use / tool_result）的已知限制。
- **文件恢复为现场重新读取**：和 CC 一样，我们从 `SessionFileState` 取出路径后现场重新 `read_text()`。如果文件在最后一次 Read tool 调用后被外部修改，恢复的是最新内容而非 Read 时的快照。这是可接受的行为。
