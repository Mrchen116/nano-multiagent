# refactor-345: compact-in-agent-loop — 技术方案

> 对齐: motivation.md v1
> Unit branch: `unit/refactor-345` (will be created by orchestrator)

## Changelog

<!-- 按时间倒序追加。格式：YYYY-MM-DD (Mx): 一句话 — 详见 Mx/progress.md -->

## 现状分析

### 涉及范围

- `src/agent/core/agent/loop.py` —— `AgentLoop.run()` 的 `while True`（153-312 行）只追加 tool results，无任何 token 检查
- `src/agent/core/agent/runtime.py` —— `_preflight_compaction`（285-288 行）turn 前单次检查；`_compact_session`（871-972 行）替换 `session_histories`；`_post_turn_check_overflow`（863 行）死代码
- `src/agent/core/agent/compaction/` —— planner / summarizer / applier / policy / types / prompts，核心逻辑可完整复用
- `src/agent/core/session/manager.py` —— `append_compaction` 写入 JSONL（compact_boundary + summary turn）
- `src/agent/core/agent/prompting.py` —— `build_prompt_messages`（51-97 行）把 system prompt 渲染为 `messages[0]`（role="system"）
- `src/agent/core/llm/interfaces.py` —— `LLMGenerateRequest` 只有 `messages` 字段，无独立 system_prompt

### 既有约束

- `SessionManager` 在 `core` 层（`agent/core/session/`），loop 直接访问不越界；但当前 loop 不持有 session_manager，compact 在 runtime 层执行
- 现有 compact 基于 `SessionEntry`（JSONL 适配层），非直接操作 `Message`
- `_estimate_context_tokens` 接收 `Sequence[Message]`，loop 内部持有的是 `list[LLMMessage]`（`content` 类型为 `str | list[dict]`），签名不匹配
- `_message_from_turn_entry` 在 `runtime.py` 定义，loop 不能 import runtime（循环依赖）
- `AgentContextFork` 复用 `AgentLoop.run()` 做 side-chain，已有 max_turns=1 的约束
- **JSONL 语义不存 system prompt** —— system prompt 是 session config 属性，非 turn 消息

### 可复用能力

- `CompactionPlanner` / `CompactionSummarizer` / `CompactionApplier` / `policy` / `prompts` —— 全部复用
- `_estimate_context_tokens` / `_is_context_overflow_error` —— 复用逻辑，需新增 LLMMessage 适配版本
- `build_system_prompt` / `_append_llm_message` / `_accumulate_usage` —— loop 内部已有或可直接复用
- `ToolResultCompressor` —— 已在 loop 内生效，不受本次变更影响

### 相关历史

- `feat-334-tool-result-budget` —— 单条工具结果预算压缩（`<persisted-output>`），在 loop 内通过 `ToolResultCompressor` 已生效

## 架构总览

### Before

```
┌──────────────┐     ┌──────────────────────────┐
│   runtime    │     │          loop            │
│              │     │                          │
│ 1. preflight │────▶│                          │
│    compact   │     │  while True:             │
│    (替换      │     │    LLM.generate()        │
│     session  │     │    tool exec             │
│     history) │     │    (无检查)              │
│              │     │                          │
│ 2. loop.run()│────▶│                          │
└──────────────┘     └──────────────────────────┘
```

### After

```
┌──────────────┐     ┌──────────────────────────┐
│   runtime    │     │          loop            │
│              │◄────│                          │
│ 消费 msg,    │     │  rendered_system_prompt  │
│ 写 JSONL     │     │  (独立,不参与compact)    │
│ (无preflight)│     │                          │
│              │     │  llm_messages = 历史+user│
│              │     │  while True:             │
│              │     │    check token ──▶ compact?│
│              │     │    LLM.generate()        │
│              │     │    (临时拼system)         │
│              │     │    tool exec             │
│              │     │    yield msg             │
└──────────────┘     └──────────────────────────┘
```

核心变化：
- **runtime 不再做 preflight**，`loop.run()` 接收完整的 `history_messages`
- **system prompt 从 messages 列表分离** —— loop 内部独立渲染，JSONL 不存，compact 只操作对话历史
- **loop 内部每次迭代开头**估算 `llm_messages` token（不含 system），超限则触发 compact
- **compact 只操作 `llm_messages`**（活跃上下文），`session_histories` 完整保留
- **loop yield `compact_boundary` msg**，runtime 消费后写入 JSONL
- **死代码 `_post_turn_check_overflow` 删除**

## 关键决策

### 决策 1: loop 如何获得 compact 能力

- **选择**：loop `__init__` 直接注入 `SessionManager` + `CompactionPlanner` + `CompactionSummarizer` + `CompactionSettings`。
- **理由**：这些组件都在 `core` 层，无 layer 越界；loop 自己管最内聚，和 CC `query.ts` 逻辑一致。
- **拒绝 Callback**：本项目的 compact 流程高度内聚，callback 会引入不必要的间接层。
- **拒绝异常驱动**：重新调用 `loop.run()` 会丢失当前 iteration 进度，和 CC "compact 后继续"语义不一致。

### 决策 2: compact 与 JSONL 写入解耦

- **选择**：loop 内部只做 compact（plan + summarize + 更新 `llm_messages`），**不**写 JSONL。loop yield summary msg（带 `is_compact_summary=True`），runtime 像消费普通 msg 一样消费它，检测到标记时额外写 `compact_boundary` entry。
- **理由**：和 CC 架构一致（query.ts 只管 compact，QueryEngine 管持久化），两件事无关。
- **拒绝 loop 内直接写 JSONL**：把持久化内聚到 loop 会破坏分层语义，且 applier 的 JSONL 写入逻辑无法和 runtime 的消息消费逻辑共享。

### 决策 3: system prompt 从 messages 列表分离（CC 方式）

- **选择**：`build_prompt_messages` 拆分为 `build_system_prompt`（已有）+ `build_chat_messages`（新）。loop 内部独立持有 `rendered_system_prompt: str`，`llm_messages` 只含对话历史（不含 system）。调用 `LLMClient.generate()` 前临时拼接 `system` message 到首位。
- **理由**：
  1. JSONL 语义本身不存 system prompt（它是 session config 属性），分离后语义一致。
  2. compact 只操作对话历史，system prompt 不受任何影响，彻底解决 compact 后 system prompt 丢失问题。
  3. 和 CC `query.ts` 的 `messagesForQuery` / `systemPrompt` 分离一致。
- **拒绝修改 `LLMGenerateRequest` 接口**：新增 `system_prompt` 字段需要改所有 provider mapper（OpenAI / Anthropic / Volcano 等），改动面大且无收益。临时拼接在 loop 层完成，provider 层零变更。

### 决策 4: token 估算直接新增 LLMMessage 版本

- **选择**：保留现有 `_estimate_context_tokens(history: Sequence[Message])` 不变，新增 `_estimate_llm_context_tokens(messages: Sequence[LLMMessage], system_prompt: str | None = None) -> int` 专供 loop 内部使用。
- **理由**：`_estimate_context_tokens` 被 runtime 的 `_preflight_compaction`（将移除）和 public `compact()`（保留）使用，但签名与 loop 内部数据结构不匹配。新增专用函数比泛化 Protocol 更简洁，不影响现有调用方。

## 接口与数据流

### 前置调整（非本 unit 核心，但阻塞实现）

1. **`_message_from_turn_entry` 迁移**：从 `runtime.py` 移到 `session/entries.py`（或 `compaction/` 公共模块），解除 loop 对 runtime 的循环依赖。
2. **`_read_file_slice` 迁移**：从 `runtime.py` 移到 `tools/session_file_state.py` 或公共 utils。

### prompting.py 变更

新增 `build_chat_messages`，`build_prompt_messages` 标记 deprecated 或改为 `build_chat_messages` 的包装：

```python
def build_chat_messages(
    *,
    history_messages: tuple[Message, ...],
    user_text: str,
) -> tuple[LLMMessage, ...]:
    """Build chat messages (history + current user) without system prompt."""
    messages: list[LLMMessage] = []
    for message in history_messages:
        metadata = dict(message.metadata)
        messages.append(
            LLMMessage(
                role=message.role,
                content=message.content,
                name=message.name,
                tool_call_id=message.tool_call_id or _extract_tool_call_id(metadata),
                tool_calls=_extract_tool_calls(metadata),
            )
        )
    messages = _merge_adjacent_assistant(messages)
    messages.append(LLMMessage(role="user", content=user_text))
    return tuple(messages)
```

`build_prompt_messages` 可保留为兼容包装（内部调用 `build_system_prompt` + `build_chat_messages`），供 `AgentContextFork` 等不经过 loop 的调用方使用。

### loop.py 变更

```python
class AgentLoop:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        model: str,
        # ... 现有参数 ...
        session_manager: SessionManager | None = None,
        compaction_planner: CompactionPlanner | None = None,
        compaction_summarizer: CompactionSummarizer | None = None,
        compaction_settings: CompactionSettings | None = None,
    ) -> None:
        # ... 现有初始化 ...
        self._session_manager = session_manager
        self._compaction_planner = compaction_planner
        self._compaction_summarizer = compaction_summarizer
        self._compaction_settings = compaction_settings

    async def run(self, state: AgentState, ...) -> AsyncIterator[Message]:
        # 1. 独立渲染 system prompt
        rendered_system_prompt = build_system_prompt(
            system_prompt=system_prompt_override or self._system_prompt,
            available_skills=active_skills,
            available_tools=active_tools,
            current_datetime=session_created_at,
            current_working_directory=current_working_directory_override or self._current_working_directory,
        )

        # 2. 构建不含 system 的 llm_messages
        llm_messages = list(build_chat_messages(
            history_messages=state.history_messages,
            user_text=state.user_text,
        ))

        while True:
            # 每次迭代开头检查 token（含 system prompt）
            if self._should_compact(llm_messages, rendered_system_prompt):
                compacted = await self._maybe_compact(
                    llm_messages=llm_messages,
                    session_id=state.session_id,
                    system_prompt=rendered_system_prompt,
                    session_file_state=session_file_state,
                )
                if compacted:
                    yield compacted.summary_msg
                    llm_messages = compacted.new_llm_messages

            # 调用 LLM 前临时拼接 system prompt
            messages_for_llm = [
                LLMMessage(role="system", content=rendered_system_prompt),
                *llm_messages,
            ]

            stream = self._llm_client.generate(
                LLMGenerateRequest(
                    session_id=llm_session_id or state.session_id,
                    model=self._model,
                    messages=tuple(messages_for_llm),
                    tools=active_tools,
                )
            )
            # ... 现有 LLM.generate() + tool exec ...
```

`_should_compact` 实现：
```python
def _should_compact(self, llm_messages: list[LLMMessage], system_prompt: str) -> bool:
    if self._compaction_settings is None or not self._compaction_settings.enabled:
        return False
    estimated = _estimate_llm_context_tokens(llm_messages, system_prompt)
    return should_compact(
        context_tokens=estimated,
        context_window=self._compaction_settings.context_window,
        reserve_tokens=self._compaction_settings.reserve_tokens,
    ) is not None
```

`_maybe_compact` 流程：
1. `entries = self._session_manager.list_entries(session_id)`
2. `plan = self._compaction_planner.plan(events=entries, reason=CompactionReason.THRESHOLD)`
3. `dropped_messages = [_message_from_turn_entry(e) for e in plan.dropped_events]`
4. `summary = await self._compaction_summarizer.summarize(..., dropped_messages=dropped_messages)`
5. **post-compact file restore**：从 `session_file_state` 读取最多 5 个最近访问文件，内容拼入 summary（复用 `_read_file_slice`，已从 runtime.py 迁移）
6. 构建新的 `llm_messages`：summary LLMMessage（role="user"）+ 保留的尾部消息（当前 planner `kept_events` 为空，尾部消息暂为 0 条）
7. 返回 `summary_msg`（`Message(role="user", content=summary, metadata={"is_compact_summary": True, "compact_reason": reason.value, "restored_files": [...]})`）+ 新的 `llm_messages`

### runtime.py 变更

移除 `_preflight_compaction` 调用（285-288 行）。`_post_turn_check_overflow` 删除。

消费 msg 时新增 compact_boundary 写入：

```python
async for msg in self._execute_loop(...):
    if msg.role == "turn_meta": ...
    history.append(msg)
    # 检测到 compact summary，先写 compact_boundary
    if msg.metadata.get("is_compact_summary"):
        self._session_manager.writer.enqueue(path, {
            "type": "compact_boundary",
            "session_id": session_id,
            "timestamp": _utc_now_iso(),
            "summary_uuid": msg.message_id,
            "data": {
                "reason": msg.metadata.get("compact_reason", "threshold"),
                "restored_files": msg.metadata.get("restored_files", []),
            },
        })
    entry = _message_to_entry(msg, session_id)
    self._session_manager.writer.enqueue(path, entry)
```

### public compact() API

保留 `AgentRuntime.compact()` 供手动触发，内部仍走 `_compact_session` + `applier`（直接写 JSONL）。loop 内部 compact 不走 applier，两者最终 JSONL 形态一致，只是触发路径不同。

## 风险与回退

- **风险 1：loop 内部 compact 时 LLM 调用失败**。summarizer 调用 LLM 生成 summary，如果失败会导致当前 turn 中断。缓解：复用 summarizer 现有的 fallback summary 机制（`_fallback_summary`）。
- **风险 2：token 估算不准导致提前/延迟 compact**。`_estimate_llm_context_tokens` 是字符估算（`(len + 7) // 8`），和真实 tokenizer 有偏差。缓解：保留 `_is_context_overflow_error` 兜底，overflow 后仍可通过异常恢复（虽然 motivation 要求主动检查，但被动恢复作为最后一道防线保留）。
- **风险 3：session_histories 内存膨胀**。不再替换 session_histories 后，长 session 的内存历史会持续增长。缓解：session 恢复时 `list_turn_messages` 已会跳过 compact_boundary 之前的消息，内存历史可在 session 恢复时按需裁剪（非本期范围）。

## 迁移与回滚策略

- **行为不变保证**：compact 核心逻辑（planner + summarizer + prompts）完全复用，只移动触发位置。
- **回滚**：还原 `loop.py` 移除 compact 检查 + 恢复 `runtime.py` preflight 调用即可。不涉及 compact 核心逻辑。

## Runbook for Reviewer

无常驻服务。本 unit 只改 agent core 内部逻辑，无新增进程/端口/服务。

## Milestones

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| refactor-345-M1 | compact-in-loop | — | A | 前置：`session/entries.py` 迁入 `_message_from_turn_entry`；`tools/session_file_state.py` 迁入 `_read_file_slice`；`prompting.py` 新增 `build_chat_messages` + token 估算泛化适配 `LLMMessage`。核心：`loop.py` 新增 token 检查 + compact 触发（system prompt 分离 + file restore）；`runtime.py` 移除 preflight + 消费 msg 时写 compact_boundary；`compaction/applier.py` 保留但仅用于 public compact() | 单元测试通过：(1) loop 内 token 超限触发 compact；(2) compact 后 iteration 继续；(3) session history 不被修改；(4) runtime 消费 summary msg 时正确写 compact_boundary；(5) system prompt 在 compact 后不丢失 |
