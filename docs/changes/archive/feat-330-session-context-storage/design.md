# Design: Session Context Storage 改造（JSONL + In-Memory History）

## 范围

将 session 消息历史从 SQLite 事件源迁移到 JSONL 文件存储，同时在 `AgentRuntime` 中引入进程内消息历史持有，实现正常多轮对话零磁盘读取。

SQLite 完全废弃（不考虑兼容旧数据，当前为开发态）。

---

## 架构总览

```
AgentRuntime (singleton HTTP server)
  │
  ├── _session_histories: dict[str, list[Message]]   ← 进程内主数据源
  │   • 正常多轮：只写内存，零磁盘读
  │   • 启动/resume：从 JSONL 加载一次
  │   • :close：evict（唯一逐出时机，无 LRU/idle timeout）
  │
  ├── _jsonl_writer: JsonlWriter                     ← 后台写入线程
  │   • queue.Queue + daemon thread
  │   • 每条消息 enqueue 即返回，不阻塞 turn
  │   • :close / compaction 前调 flush() 等待落盘
  │
  └── _session_file_states: dict[str, SessionFileState]   ← 现有，不变

持久化层（JSONL）
  {workspace_root}/.nano/sessions/{session_id}.jsonl
  • 仅追加，不修改历史
  • 持久化与上下文工程解耦：compaction 只动内存视图，不改已写 JSONL 行
```

---

## JSONL 文件格式

### 文件位置

**主 session**：

```
{workspace_root}/.nano/sessions/{session_id}.jsonl
```

**子 agent（sidechain）**：

```
{workspace_root}/.nano/sessions/{parent_session_id}/subagents/{subagent_session_id}.jsonl
```

- 子 agent 是独立 session，有自己的 `session_id`
- `session_created` 的 `metadata.parent_session_id` 记录父子关系
- resume 子 agent 时：读 `session_created` 拿到 `parent_session_id`，拼出完整路径

### Entry 类型（4 种，大幅简化 CC）

#### 1. `session_created`（第一行，session config）

```json
{
  "type": "session_created",
  "session_id": "sess_...",
  "created_at": "2026-04-22T10:00:00+00:00",
  "workspace_root": "/path/to/project",
  "system_prompt": "You are... <RUNTIME_FILL:AVAILABLE_TOOLS>",
  "skills": ["bash_runner"],
  "tool_allowlist": ["read", "write", "bash"],
  "metadata": {}
}
```

- `system_prompt`：模板字符串（含 `<RUNTIME_FILL:*>` 占位符），是 session config
- `metadata`：product 层透传的 opaque 数据（`conversation_type`、`participant_agent_ids` 等），core 不解释
- **不存** `system_prompt` 渲染结果——每次 turn 由 `build_system_prompt()` 动态组装，用完即弃
- config 变更历史通过 `config_update` 追加记录，resume 时取最新值

#### 2. `turn`（消息行）

```json
{
  "type": "turn",
  "uuid": "msg_...",
  "parent_uuid": "msg_...",
  "group_id": "msg_...",
  "session_id": "sess_...",
  "role": "user",
  "content": "帮我写一个排序函数",
  "timestamp": "2026-04-22T10:01:00+00:00",
  "entrypoint": "coding_cli",
  "is_meta": false,
  "is_compact_summary": false
}
```

| 字段 | 说明 |
|------|------|
| `uuid` | 消息唯一 ID（对应现有 `message_id`） |
| `parent_uuid` | 父消息 UUID；`null` = 链头。正常对话是线性链，rewind 后产生分支（DAG） |
| `group_id` | **同一 assistant response 产生的消息分组 ID**。assistant message 的 `group_id` = 自己的 `uuid`；该 assistant 产生的所有 tool results 共享此 `group_id`。用于 resume 时区分"当前路径的 parallel tool results"与"rewind 后旧路径的死分支" |
| `entrypoint` | `"coding_cli"` / `"agent_core"` 区分入口产品 |
| `is_meta` | harness 注入的合成 user 消息（不显示给用户，但发给 LLM）。场景：max_output_tokens 恢复指令、compaction 触发消息 |
| `is_compact_summary` | compaction 生成的摘要 user 消息（新历史上下文起点）；`is_meta` 同为 true |

**去掉的 CC 字段**：`gitBranch`（我们不感知 git）、`cwd`（用 session 级 workspace_root 即可）、`version`、`userType`、`isSidechain`（子 agent 本身就是独立 session）、`agentId`、`teamName`、`slug`、`logicalParentUuid`

#### 3. `compact_boundary`（compaction 边界标记）

```json
{
  "type": "compact_boundary",
  "session_id": "sess_...",
  "timestamp": "2026-04-22T11:00:00+00:00",
  "summary_uuid": "msg_..."
}
```

- `summary_uuid` 指向同文件中 `is_compact_summary: true` 的那条 turn 消息
- resume 加载时：找到最新 `compact_boundary`，跳过其之前所有 turn，从 summary_uuid 消息开始重建对话链

#### 4. `config_update`（session config 中途变更）

```json
{
  "type": "config_update",
  "session_id": "sess_...",
  "timestamp": "2026-04-22T11:30:00+00:00",
  "system_prompt": "新 prompt...",
  "skills": ["new_skill"],
  "tool_allowlist": ["read", "write"],
  "metadata": {"conversation_type": "pair"}
}
```

- 字段语义和 `session_created` 相同，只记录变更项
- resume 加载时：以 `session_created` 为基线，按时间顺序应用所有 `config_update`，得到当前 config
- 提供独立 API `PUT /v1/sessions/{id}/config` 触发写入

---

## 组件设计

### JsonlWriter（新增）

**文件**：`src/agent/core/session/jsonl_writer.py`

```python
class JsonlWriter:
    """Append-only JSONL writer with background batching.

    - enqueue: 入内存 buffer，立即返回，不阻塞 caller
    - _run:    后台线程，每 100ms 或 buffer 满 50 条时批量 flush
    - flush:   强制刷盘，asyncio-safe（内部用 run_in_executor）

    > NOTE: JSONL 文件只追加不删，长期运行会无限增长。清理由 product 层决定。
    > NOTE: _session_histories 内存无上限，product 层需控制并发 session 数。
    """

    _BATCH_SIZE = 50
    _FLUSH_INTERVAL_MS = 100

    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[Path, dict] | threading.Event] = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._last_error: Exception | None = None

    def enqueue(self, path: Path, entry: dict) -> None:
        self._queue.put((path, entry))

    def flush(self, timeout: float = 10.0) -> None:
        """Block until all queued writes are done. Raise on timeout or background error."""
        if self._last_error is not None:
            raise self._last_error
        event = threading.Event()
        self._queue.put(event)
        if not event.wait(timeout=timeout):
            raise TimeoutError(f"JsonlWriter flush timed out after {timeout}s")
        if self._last_error is not None:
            raise self._last_error

    async def flush_async(self) -> None:
        """Async-safe flush — never blocks the asyncio event loop."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.flush)

    def _run(self) -> None:
        buffer: list[tuple[Path, dict]] = []
        last_flush = time.monotonic()

        while True:
            try:
                item = self._queue.get(timeout=0.05)
            except queue.Empty:
                if buffer and (time.monotonic() - last_flush) * 1000 >= self._FLUSH_INTERVAL_MS:
                    try:
                        self._flush_buffer(buffer)
                    except Exception as e:
                        self._last_error = e
                    buffer = []
                    last_flush = time.monotonic()
                continue

            if isinstance(item, threading.Event):
                try:
                    if buffer:
                        self._flush_buffer(buffer)
                        buffer = []
                except Exception as e:
                    self._last_error = e
                item.set()
                last_flush = time.monotonic()
                continue

            buffer.append(item)
            if len(buffer) >= self._BATCH_SIZE:
                try:
                    self._flush_buffer(buffer)
                except Exception as e:
                    self._last_error = e
                buffer = []
                last_flush = time.monotonic()

    def _flush_buffer(self, buffer: list[tuple[Path, dict]]) -> None:
        by_path: dict[Path, list[dict]] = {}
        for path, entry in buffer:
            by_path.setdefault(path, []).append(entry)
        for path, entries in by_path.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                for entry in entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
```

### JsonlSessionStore（替换 SQLiteSessionStore）

**文件**：`src/agent/core/session/jsonl_store.py`

职责：
- `create(session_id, config)` → 写 `session_created` 行
- `append(session_id, entry)` → enqueue 到 JsonlWriter
- `load(session_id)` → 读文件，按行解析，重建 Session + 消息列表
- `list_session_ids()` → `glob("{data_dir}/sessions/*.jsonl")`，按 mtime 排序
- `resolve_path(session_id) -> Path`

**路径解析**（`resolve_path`）—— 支持主 session 平级路径和子 agent 子目录：

```python
def _resolve_path(session_id: str, parent_session_id: str | None = None) -> Path:
    """Resolve JSONL path. If parent_session_id given, subagent path; else main session path."""
    if parent_session_id:
        return data_dir / "sessions" / parent_session_id / "subagents" / f"{session_id}.jsonl"
    return data_dir / "sessions" / f"{session_id}.jsonl"
```

**加载逻辑（`load()`）的完整 resume 算法**：

```python
def load(session_id: str, parent_session_id: str | None = None) -> LoadResult:
    path = _resolve_path(session_id, parent_session_id=parent_session_id)
    if not path.exists():
        raise SessionNotFoundError(session_id)

    config: dict[str, Any] = {}
    turns: list[dict] = []          # 所有 turn 行（含 compact_summary）
    boundary_summary_uuid: str | None = None

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            etype = entry["type"]

            if etype == "session_created":
                config = _extract_config(entry)   # system_prompt/skills/.../metadata

            elif etype == "config_update":
                config = _merge_config(config, entry)  # 增量覆盖

            elif etype == "turn":
                turns.append(entry)

            elif etype == "compact_boundary":
                # 只认最新的 boundary（JSONL 只追加，后面的覆盖前面的）
                boundary_summary_uuid = entry.get("summary_uuid")
                turns.clear()   # 丢弃 boundary 之前的所有 turn

    # --- 从 compact_boundary 之后（或全部）的 turn 重建对话链 ---
    if not turns:
        return LoadResult(config=config, messages=[])

    # 构建 uuid -> entry 映射
    entry_by_uuid: dict[str, dict] = {t["uuid"]: t for t in turns}

    # 找 terminal：uuid 没有被任何 entry 作为 parent_uuid 引用
    all_parent_uuids = {t["parent_uuid"] for t in turns if t.get("parent_uuid")}
    terminals = [t for t in turns if t["uuid"] not in all_parent_uuids]

    # 正常情况下只有一个 terminal；有分支时取 timestamp 最新的
    leaf = max(terminals, key=lambda t: t["timestamp"])

    # 沿 parent_uuid 回溯到根，收集主链消息（逆序）
    chain: list[dict] = []
    seen: set[str] = set()
    current: dict | None = leaf
    while current is not None:
        chain.append(current)
        seen.add(current["uuid"])
        parent_uuid = current.get("parent_uuid")
        current = entry_by_uuid.get(parent_uuid) if parent_uuid else None

    chain.reverse()   # 从旧到新

    # --- DAG Recovery: 收集主链上遗漏的 parallel tool results ---
    # 问题：写入是 DAG（同一 assistant 的多个 tool results 都指向它），
    # 但 backtrack 是链表遍历，只能走一条分支，会丢失同组的 siblings。
    # 同时必须避免把 rewind 后旧路径（死分支）的 tool results 带进来。
    # 解决：只恢复和主链上节点同 group_id 的 orphans。
    #
    # 示例（rewind 后）：
    #   user_1 → asst_1(group=g1) → tool_A(g1) → asst_2(g2)   (旧路径)
    #            ↘
    #              user_2 → asst_3(g3) → tool_B(g3), tool_C(g3) → asst_4(g4)  (新路径)
    # backtrack 从 asst_4: [user_1, asst_1, user_2, tool_B, asst_4]
    #   tool_C(g3) 的 parent = asst_3(g3)，asst_3 在主链上 → 恢复 tool_C
    #   tool_A(g1) 的 parent = asst_1(g1)，asst_1 在主链上但 group_id 不同 → 不恢复

    # 收集主链上所有出现过的 group_id
    active_groups: set[str] = {
        t["group_id"]
        for t in chain
        if t.get("group_id")
    }

    # 多轮收集：orphan 的 parent 在主链 seen 中，且 orphan 的 group_id 在 active_groups 中
    recovered: list[dict] = []
    while True:
        newly_found = False
        for turn in turns:
            if turn["uuid"] in seen:
                continue
            parent_uuid = turn.get("parent_uuid")
            group_id = turn.get("group_id")
            if (
                parent_uuid
                and parent_uuid in seen
                and group_id
                and group_id in active_groups
            ):
                recovered.append(turn)
                seen.add(turn["uuid"])
                newly_found = True
        if not newly_found:
            break

    # 主链 + 恢复的 orphans 按时间戳排序（JSONL append-only，时间戳 = 写入顺序）
    all_entries = chain + recovered
    all_entries.sort(key=lambda t: t.get("timestamp", ""))

    # 转成 Message 对象
    messages = [_to_message(t) for t in chain]
    return LoadResult(config=config, messages=messages)
```

关键细节：
- `compact_boundary` 之后的 `turn` 包含 `is_compact_summary=true` 的 summary 消息，它的 `parent_uuid` **指向 compaction 前最后一条保留的消息**（与 CC 一致）。resume 时那条消息已被 compact_boundary 逻辑丢弃，回溯 summary 的 parent 找不到，链构建正确停在 summary——summary 成为新链的根部
- 有 rewind 分支时，`terminals` 会有多个，取 timestamp 最新的那条作为活跃分支，死分支物理保留在 JSONL 但逻辑丢弃
- `_to_message()` 把 JSONL turn 行转成 `Message`，`uuid` → `message_id`，`parent_uuid` → `parent_message_id`
- **JSONL 损坏处理**：`load()` 中 `json.loads()` 抛 `JSONDecodeError` 时直接向上传播，不跳过残行。调用方（AgentRuntime）捕获后视为 session 损坏

`update_config(session_id, **fields)` → 追加 `config_update` 行到 JSONL，更新内存中 `_session_configs[session_id]`

### SessionManager（接口不变，底层换 JsonlSessionStore）

公共接口全部保留，调用方无需修改：
- `create_session()` → 写 `session_created` 行 + 初始化内存历史/config
- `get_session()` → 从 JsonlSessionStore 加载（仅 resume/cold start 调用）
- `update_session_config()` → 追加 `config_update` 行，更新内存
- `append_turn_message()` → 不再直接调用；由 AgentRuntime 统一管理（见下）
- `append_compaction()` → 写 `compact_boundary` + summary turn 行
- `list_sessions()` → 文件系统扫描（mtime 排序，offset/limit → 取前 N 个）
- `list_turn_messages()` → **AgentRuntime 内部直读内存**；`SessionManager` 保留方法但从 JSONL 读取（供 HTTP API 等外部调用方 fallback 使用）

**去掉**：
- `archive_session()`（session 没有 archived 状态）
- `append_run_status()`（RUN_STATUS 不写入 JSONL；`RunsRegistry` 改为只发 event hub 事件）

### AgentRuntime 改造

**新增字段**（与 `_session_file_states` 并列）：

```python
self._session_histories: dict[str, list[Message]] = {}
self._session_configs: dict[str, SessionConfig] = {}   # 内存持有 session config
self._session_paths: dict[str, Path] = {}              # 内存持有 session JSONL 路径
self._session_locks: dict[str, asyncio.Lock] = {}      # 每 session 一个并发锁
```

`SessionConfig`：从 `session_created` + `config_update` 加载得到的当前 config，包含 `system_prompt`、`skills`、`tool_allowlist`、`metadata`。

**`AgentLoop.run()` 改造**：

从返回 `TurnResult` 改为纯流式 `AsyncIterator[Message]`，参考 CC 的 `query()` async generator 模式。流中最后一条是 `role="turn_meta"` 的元数据消息，携带 `stop_reason`、`completed`、`usage`。调用方从消息流中自行组装 `TurnResult`。

```python
class AgentLoop:
    async def run(self, state: AgentState, ...) -> AsyncIterator[Message]:
        last_parent_id = state.history_messages[-1].message_id if state.history_messages else None

        try:
            while True:
                response = self._llm_client.generate(...)
                assistant_msg = Message(
                    message_id=make_message_id(),
                    parent_message_id=last_parent_id,
                    role=response.message.role,
                    content=response.message.content,
                    metadata=_assistant_metadata_from_tool_calls(normalized_calls),
                )
                last_parent_id = assistant_msg.message_id
                yield assistant_msg

                if not normalized_calls:
                    yield self._make_turn_meta(
                        stop_reason=response.finish_reason or "completed",
                        completed=True,
                        usage=turn_usage,
                    )
                    return

                # Batch 内所有 tool results 共享同一个 parent（产生它们的 assistant），
                # 形成 DAG 语义。batch 结束后 last_parent_id 更新为最后一个 tool result。
                batch_parent_id = last_parent_id
                for parsed_call in normalized_calls:
                    result = await self._execute_tool_call(parsed_call)
                    tool_msg = Message(
                        message_id=make_message_id(),
                        parent_message_id=batch_parent_id,
                        role="tool",
                        content=result.content,
                        tool_call_id=result.call_id,
                        group_id=assistant_msg.message_id,  # 继承产生 tool 的 assistant 的 group_id
                        metadata={
                            "tool_name": result.name,
                            "tool_error": result.error,
                            "tool_output": result.output,  # 原始对象，内存-only
                        },
                    )
                    last_parent_id = tool_msg.message_id
                    yield tool_msg

                if interrupted:
                    yield self._make_turn_meta(stop_reason="interrupted", completed=False, usage=turn_usage)
                    return
                if max_turns_reached:
                    yield self._make_turn_meta(stop_reason="max_turns_reached", completed=False, usage=turn_usage)
                    return
        finally:
            await self._dispatch_turn_end(completed, stop_reason, usage=turn_usage)

    def _make_turn_meta(self, *, stop_reason: str, completed: bool, usage: TokenUsage | None) -> Message:
        return Message(
            message_id=make_message_id(),
            role="turn_meta",
            content="",
            metadata={"stop_reason": stop_reason, "completed": completed, "usage": usage},
        )
```

**`AgentRuntime.run()` 改造**：

```python
async def run(
    self,
    session_id: str,
    parts: Sequence[Mapping[str, Any]],
    *,
    parent_session_id: str | None = None,
    ...
) -> TurnResult:
    # --- 加载历史和 config（只在 miss 时读盘）---
    if session_id not in self._session_histories:
        path = _resolve_path(session_id, parent_session_id=parent_session_id)
        result = self._session_manager.load(path)
        self._session_histories[session_id] = list(result.messages)
        self._session_configs[session_id] = result.config
        self._session_paths[session_id] = path

    history = self._session_histories[session_id]
    config = self._session_configs[session_id]
    path = self._session_paths[session_id]

    # --- 先写用户消息（async-safe 同步等待落盘）---
    input_parts = parse_input_parts(parts)
    user_text = render_user_text(input_parts)
    user_msg = Message(
        message_id=make_message_id(),
        parent_message_id=history[-1].message_id if history else None,
        role="user",
        content=user_text,
    )
    history.append(user_msg)
    self._jsonl_writer.enqueue(path, _message_to_entry(user_msg, session_id))
    await self._jsonl_writer.flush_async()

    # --- 逐条消费 loop yield 的消息，实时写入 JSONL ---
    all_messages: list[Message] = [user_msg]
    try:
        async for msg in self._loop.run(
            AgentState(
                session_id=session_id,
                turn_id=turn_id,
                history_messages=tuple(history),
                input_parts=input_parts,
                user_text=user_text,
            ),
            ...
        ):
            if msg.role == "turn_meta":
                all_messages.append(msg)
                continue

            history.append(msg)
            all_messages.append(msg)
            entry = _message_to_entry(msg, session_id)
            if msg.role == "tool":
                self._jsonl_writer.enqueue(path, entry)
                await self._jsonl_writer.flush_async()
            else:
                self._jsonl_writer.enqueue(path, entry)
        # turn 结束：强制 flush 最后一批 assistant 消息
        await self._jsonl_writer.flush_async()
    except ModelError:
        await self._jsonl_writer.flush_async()
        raise

    turn_result = build_turn_result(session_id, turn_id, all_messages)

    await self._dispatch_observe(
        "agent_end",
        {
            "session_id": session_id,
            "turn_id": turn_id,
            "completed": turn_result.completed,
            "stop_reason": turn_result.stop_reason,
        },
        hook_ctx,
    )
    return turn_result
```

**`_append_turn_events()` 删除**：消息已在 `async for` 中实时写入 JSONL，无需事后拆分 `TurnResult` 再写入。

**`build_turn_result()` — 纯函数组装**：

```python
def build_turn_result(session_id: str, turn_id: str, messages: list[Message]) -> TurnResult:
    if not messages:
        return TurnResult(session_id=session_id, turn_id=turn_id, completed=False, stop_reason="error")

    *body, turn_meta = messages
    if turn_meta.role != "turn_meta":
        meta = {}
        body = messages
    else:
        meta = turn_meta.metadata

    assistant_msgs = [m for m in body if m.role == "assistant"]
    tool_calls = []
    tool_results = []

    for msg in body:
        if msg.role == "assistant":
            for tc in msg.metadata.get("tool_calls", []):
                tool_calls.append(ToolCall(call_id=tc["call_id"], name=tc["name"], arguments=tc["arguments"]))
        elif msg.role == "tool":
            tool_results.append(ToolResult(
                call_id=msg.tool_call_id,
                name=msg.metadata.get("tool_name"),
                content=msg.content,
                output=msg.metadata.get("tool_output"),
                error=msg.metadata.get("tool_error"),
            ))

    return TurnResult(
        session_id=session_id,
        turn_id=turn_id,
        messages=tuple(assistant_msgs),
        tool_calls=tuple(tool_calls),
        tool_results=tuple(tool_results),
        completed=meta.get("completed", False),
        stop_reason=meta.get("stop_reason", "completed"),
        usage=meta.get("usage"),
    )
```

**`close_session()` 改造**：

```python
async def close_session(self, session_id: str) -> None:
    run_id = self._runs_registry.get_active_run_id(session_id)
    if run_id:
        self._runs_registry.cancel(run_id)

    lock = self._session_locks.get(session_id)
    if lock:
        async with lock:
            await self._jsonl_writer.flush_async()
            self._session_histories.pop(session_id, None)
            self._session_configs.pop(session_id, None)
            self._session_paths.pop(session_id, None)
    else:
        await self._jsonl_writer.flush_async()

    self._session_file_states.pop(session_id, None)
    self._session_locks.pop(session_id, None)
    self._event_hub.publish(...)
```

**并发锁**：`AgentRuntime` 新增 `self._session_locks: dict[str, asyncio.Lock] = {}`。`run()`、`close_session()`、`compact()` 等对同一 session 的操作需要加锁：

```python
lock = self._session_locks.setdefault(session_id, asyncio.Lock())
async with lock:
    # 所有对 _session_histories[session_id] 的读写
```

`setdefault` 在 asyncio 单线程事件循环下安全。close 时先 cancel run、再拿锁，确保 run 退出后才清理。

**`_compact_session()` 改造**：

```python
async def _compact_session(self, session_id: str, ...) -> ...:
    path = self._session_paths[session_id]
    # ... 现有 compaction 逻辑生成 summary ...

    # 1. 写 is_compact_summary + is_meta 的 turn 行
    summary_msg = Message(
        message_id=make_message_id(),
        role="user",
        content=summary_text,
        metadata={"is_compact_summary": True, "is_meta": True},
    )
    self._session_histories[session_id].append(summary_msg)
    self._jsonl_writer.enqueue(path, _message_to_entry(summary_msg, ...))

    # 2. 写 compact_boundary 行
    self._jsonl_writer.enqueue(path, {
        "type": "compact_boundary",
        "session_id": session_id,
        "timestamp": _utc_now_iso(),
        "summary_uuid": summary_msg.message_id,
    })
    await self._jsonl_writer.flush_async()

    # 3. 更新内存：截断为 [summary_msg] + post-compaction 消息
    self._session_histories[session_id] = [summary_msg]
    self._session_file_states.pop(session_id, None)   # 现有逻辑保留
```

### Message 模型扩展

**文件**：`src/agent/core/types.py`（或 `session/models.py`）

```python
@dataclass(frozen=True)
class Message:
    message_id: str          # = JSONL uuid
    role: str
    content: str | list
    parent_message_id: str | None = None   # = JSONL parent_uuid（新增）
    group_id: str | None = None            # = JSONL group_id（新增）
    metadata: dict[str, Any] = field(default_factory=dict)
```

`is_meta` / `is_compact_summary` 存在 `metadata` dict 中（`metadata["is_meta"]`、`metadata["is_compact_summary"]`），不作为 first-class 字段，避免污染 Message 接口。JSONL 序列化时从 metadata 中提取并展平到顶层字段。

**`_message_to_entry()` — Message 转 JSONL turn 行**：

```python
def _message_to_entry(msg: Message, session_id: str) -> dict:
    entry = {
        "type": "turn",
        "uuid": msg.message_id,
        "parent_uuid": msg.parent_message_id,
        "session_id": session_id,
        "role": msg.role,
        "content": msg.content,
        "timestamp": _utc_now_iso(),
    }
    if msg.tool_call_id:
        entry["tool_call_id"] = msg.tool_call_id
    if msg.group_id:
        entry["group_id"] = msg.group_id
    # 从 metadata 提取需要持久化的字段
    if msg.metadata.get("is_meta"):
        entry["is_meta"] = True
    if msg.metadata.get("is_compact_summary"):
        entry["is_compact_summary"] = True
    if msg.metadata.get("entrypoint"):
        entry["entrypoint"] = msg.metadata["entrypoint"]
    # NOTE: tool_output 是内存-only 原始对象，不写入 JSONL
    return entry
```

---

## 数据流

### 正常多轮对话（cache hit）

```
client → POST /v1/sessions/{id}/messages:async
  → AgentRuntime.run()
       → _session_histories[id]  ← 内存命中，零磁盘读
       → 执行 turn
       → _append(user_msg)       → queue ← enqueue（非阻塞）
       → _append(assistant_msg)  → queue ← enqueue（非阻塞）
                                    ↓ 后台线程
                                  {workspace_root}/.nano/sessions/{id}.jsonl
```

### 启动 / Resume（cache miss）

```
AgentRuntime.run()
  → session_id not in _session_histories
  → JsonlSessionStore.load(session_id)
       → 读 .jsonl 文件
       → 找最新 compact_boundary
       → build_conversation_chain()
       → 返回 list[Message]
  → _session_histories[session_id] = msgs
  → 继续正常执行
```

### Fork

> **NOTE**: 当前 fork 只复制线性链（活跃分支）。数据结构已支持 DAG（`parent_uuid`），但 rewind 尚未实现，因此死分支不复制。未来支持 rewind 后，fork 逻辑需升级为复制完整 DAG（保持所有分支的 parent_uuid 关系并 re-stamp）。

```
POST /v1/sessions/{id}:fork
  → SessionService.fork_session(source_id)
       → 新建 session_id
       → 写 session_created 行（复制 source config，metadata 加 forked_from）
       → 遍历 _session_histories[source_id]，逐条 re-stamp（新 uuid、新 timestamp、新 session_id）
       → 重新计算 parent_uuid 链（按顺序，非 DAG 复制）
       → 写入新 JSONL
       → _session_histories[new_id] = re-stamped msgs
       → _session_configs[new_id] = copy(source_config)
       → 返回 new_session
```

### Config 更新

```
PUT /v1/sessions/{id}/config
  → runtime.update_session_config(session_id, system_prompt="...", skills=[...])
       → 校验字段
       → 追加 config_update 行到 JSONL
       → _session_configs[session_id] = merged_config
       → 返回 {} (200 OK)
```

---

## Session Listing

`GET /v1/sessions` 底层改为文件系统扫描：

```python
def list_session_ids(*, limit: int, offset: int) -> list[str]:
    # 主 session（平级）+ 子 agent（子目录）
    main_files = Path(data_dir).glob("sessions/*.jsonl")
    subagent_files = Path(data_dir).glob("sessions/*/subagents/*.jsonl")
    all_files = sorted(
        chain(main_files, subagent_files),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [p.stem for p in all_files[offset: offset + limit]]
```

分页语义变更：offset 仍支持，但排序依据从 SQLite insert order 改为 mtime（最近活跃优先）。HTTP 接口签名不变。

---

## Milestone 划分

### M1 — JSONL 存储层

1. `JsonlWriter`（`src/agent/core/session/jsonl_writer.py`）
2. `JsonlSessionStore`（`src/agent/core/session/jsonl_store.py`）：create / append / load / list
3. `build_conversation_chain()`：compact_boundary 跳读 + parent_uuid 回溯
4. `SessionManager` 底层换 `JsonlSessionStore`，去掉 `append_run_status()`
5. `Message` 增加 `parent_message_id` 字段
6. 单元测试：load / compact_boundary 跳读 / DAG 回溯

### M2 — AgentRuntime 进程内持有

7. `AgentRuntime._session_histories` / `_session_configs` / `_session_locks` 初始化
8. `run()` cache-first：miss 时调 `load()`（返回 messages + config），hit 时直接用内存
9. `AgentLoop.run()` 改为 yield 模式（assistant + tool + turn_meta），`build_turn_result()` 纯函数组装
10. `AgentRuntime._execute_loop()` / `run()` 改为 `async for` 实时消费 + 写入 JSONL；删除 `_append_turn_events()`
11. `_compact_session()` 改造：写 compact_boundary + 更新内存视图
12. `close_session()` 改造：加锁 + flush + evict（历史 + config + 锁）
13. `PUT /v1/sessions/{id}/config` 路由 + `update_session_config()` 方法
14. 集成测试：多轮 → compaction → resume → 验证历史一致

### M3 — Fork

14. `SessionService.fork_session()` 改造：从内存历史复制 + re-stamp + 写新 JSONL
15. 单元测试：fork 后两个 session 历史独立

---

## 拒绝的方案

| 方案 | 拒绝原因 |
|------|------|
| SQLite 保留做 session metadata | 两套持久化层，增加维护成本；JSONL 第一行存 config 足够 |
| LRU / idle timeout 逐出 | in-memory history 是主数据源不是 cache；任意逐出破坏"进程内持有"语义 |
| 同步写入 JSONL | 阻塞 turn 执行；background thread + queue 是标准异步写模式 |
| RUN_STATUS 写入 JSONL | 运行时状态不需要持久化恢复；增加文件噪音 |
| `is_meta` / `is_compact_summary` 作为 Message first-class 字段 | 避免污染核心 Message 接口；metadata dict 已有此语义 |
| gitBranch 写入 JSONL | 我们不感知 git，且无 session listing UI 使用场景 |
| `cwd` 写入每条消息 | 用 session 级 workspace_root 即可，无子 agent 切换 cwd 场景 |
