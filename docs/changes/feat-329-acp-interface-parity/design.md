# Design: Agent Core 核心能力补全（P0 + P1）

## 范围

本文档覆盖 P0（会话生命周期补齐）和 P1（会话高级操作）的技术方案。

---

## ACP 语义对照

ACP 使用 WebSocket + JSON-RPC；我们使用 HTTP + SSE。语义映射如下：

| ACP 操作 | 我们的映射 | 说明 |
|---|---|---|
| `session/load` | `GET /v1/sessions/{id}`（增强） | 增强 GET 返回完整配置；实际 load 由 run() 隐式承载 |
| `session/close` | `POST /v1/sessions/{id}:close` | flush JSONL + cancel 活跃 run + evict 内存 |
| `session/fork` | `POST /v1/sessions/{id}:fork` | 从内存深拷贝消息历史到新 session |
| `rewind` | `POST /v1/sessions/{id}:rewind` | 回到指定消息节点，截断后续历史 |
| `session/resume` | **不在 P1 实现** | 需要 SUSPENDED 状态机支撑，推 P2 |
| `session/cancel` | `POST /v1/sessions/{id}:cancel` | 封装 RunsRegistry，session 粒度取消 |

---

## P0 设计

### 1. GET /v1/sessions/{id}（增强，覆盖 ACP session/load）

**变更**：在现有 `SessionResponse` 中补全配置字段，让客户端重连时能拿到完整 session 上下文。

**现有 SessionResponse**（只有 session_id / status / created_at / metadata）扩展为：

```json
{
  "session_id": "sess_...",
  "status": "active",
  "created_at": "2026-04-20T...",
  "system_prompt": "...",
  "skills": ["skill_a"],
  "tool_allowlist": ["bash", "read"],
  "metadata": {}
}
```

**实现**：路由层 `get_session` handler 已调用 `session_service.get_session()`，`Session` 对象本身已有这些字段，只需在 `SessionResponse` 模型里补充字段映射即可，无逻辑变更。

**涉及文件**：
- `src/agent/platform/http_api/routes/session.py` — 扩展 `SessionResponse` 模型

---

### 2. POST /v1/sessions/{id}:close

**语义**：显式关闭 session，触发完整清理流程。幂等：session 不在内存中时静默返回 200。

**Request**：空 body（或 `{}`）

**Response**：`{}` (200 OK)

#### 语义

`:close` flush 未落盘的 JSONL 写入、cancel 活跃 run、释放进程内内存（`_session_histories` / `_session_configs` / `_session_paths`）。**不封闭 session**——close 之后发消息会从 JSONL 自然 resume，这是正确行为。session 没有 "archived" 状态。

#### 业务逻辑归属

编排逻辑移入 `AgentRuntime`：

```python
async def close_session(self, session_id: str) -> None:
    """Release in-memory context and cancel any active run. Idempotent."""
    # Step 1: cancel any run in flight
    run_id = self._runs_registry.get_active_run_id(session_id)
    if run_id:
        self._runs_registry.cancel(run_id)

    # Step 2: flush pending JSONL writes and evict memory under lock
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
```

幂等：session 不在内存中时静默返回，无需检查 session 是否存在。

**HTTP handler**（薄层）：

```python
@router.post("/{session_id}:close")
async def close_session(session_id: str, runtime = Depends(get_agent_runtime)):
    await runtime.close_session(session_id)
    return {}
```

**涉及文件**：
- `src/agent/core/agent/runtime.py` — 新增 `close_session()`
- `src/agent/platform/http_api/routes/session.py` — 新增路由

---

### 3. POST /v1/sessions/{id}:cancel

**语义**：取消该 session 当前活跃的 turn/run。无活跃 run 时幂等返回 200。

**Request**：空 body（或 `{}`）

**Response**：
```json
{
  "session_id": "sess_...",
  "had_active_run": true,
  "cancelled_run_id": "run_..."
}
```

**实现**（路由层直接调用，逻辑足够简单，不需要下沉到 runtime）：

```python
run_id = runs_registry.get_active_run_id(session_id)
if run_id:
    runs_registry.cancel(run_id)
    return {"session_id": session_id, "had_active_run": True, "cancelled_run_id": run_id}
return {"session_id": session_id, "had_active_run": False}
```

**涉及文件**：
- `src/agent/platform/http_api/routes/session.py` — 新增路由 + `CancelSessionResponse` 模型

---

## P1 设计

### 4. POST /v1/sessions/{id}:fork

**语义**：从现有 session 创建独立分支，复制当前内存中可见的消息历史到新 session。

**Request**：
```json
{ "metadata": {} }
```

**Response**：
```json
{
  "session_id": "sess_...",
  "forked_from": "sess_...",
  "forked_at": "2026-04-20T..."
}
```

#### 业务逻辑归属：AgentRuntime

F-330 架构下，session 消息历史以 `_session_histories` 内存持有为主数据源。fork 需要从内存复制历史并重新 stamp uuid/parent_uuid，属于 runtime 层职责。路由通过 `AgentRuntime.fork_session()` 调用。

**`AgentRuntime` 新增方法**：

```python
async def fork_session(
    self,
    source_session_id: str,
    *,
    extra_metadata: dict | None = None,
) -> Session:
    """Fork a session: copy in-memory config + message history into a new session."""
    # Source must be loaded in memory or loadable from JSONL
    if source_session_id not in self._session_histories:
        path = self._session_manager.store.resolve_path(source_session_id)
        result = self._session_manager.load(source_session_id)
        self._session_histories[source_session_id] = list(result.messages)
        self._session_configs[source_session_id] = result.config
        self._session_paths[source_session_id] = path

    source_config = self._session_configs[source_session_id]
    source_history = self._session_histories[source_session_id]

    # Create new session with copied config
    new_session = self._session_manager.create_session(
        workspace_root=source_config.workspace_root,
        system_prompt=source_config.system_prompt,
        skills=source_config.skills,
        tool_allowlist=source_config.tool_allowlist,
        metadata={
            **dict(source_config.metadata),
            **(extra_metadata or {}),
            "forked_from": source_session_id,
        },
    )
    new_session_id = new_session.session_id
    new_path = self._session_manager.store.resolve_path(new_session_id)

    # Re-stamp message chain: new uuid + new parent_uuid chain
    id_map: dict[str, str] = {}
    new_messages: list[Message] = []
    for msg in source_history:
        new_id = make_message_id()
        id_map[msg.message_id] = new_id
        new_parent = id_map.get(msg.parent_message_id) if msg.parent_message_id else None
        new_msg = Message(
            message_id=new_id,
            parent_message_id=new_parent,
            role=msg.role,
            content=msg.content,
            tool_call_id=msg.tool_call_id,
            metadata=dict(msg.metadata),
        )
        new_messages.append(new_msg)
        self._jsonl_writer.enqueue(new_path, _message_to_entry(new_msg, new_session_id))

    await self._jsonl_writer.flush_async()

    # Register in runtime memory
    self._session_histories[new_session_id] = new_messages
    self._session_configs[new_session_id] = SessionConfig(
        session_id=new_session_id,
        created_at=new_session.created_at,
        workspace_root=source_config.workspace_root,
        system_prompt=source_config.system_prompt,
        skills=source_config.skills,
        tool_allowlist=source_config.tool_allowlist,
        metadata={
            **dict(source_config.metadata),
            **(extra_metadata or {}),
            "forked_from": source_session_id,
        },
    )
    self._session_paths[new_session_id] = new_path

    return new_session
```

**设计决策**：
- 从 `_session_histories[source_id]` 内存复制，已处理 compaction 语义（只包含当前可见历史）。
- 重新 stamp 所有 uuid 和 parent_uuid，保持线性链结构（当前不支持 DAG 复制，rewind 实现后升级）。
- fork 时 flush JSONL 确保新 session 文件完整写入。
- source 不在内存中时自动冷加载（与 run() 的 cache-miss 行为一致）。

**涉及文件**：
- `src/agent/core/agent/runtime.py` — 新增 `fork_session()`
- `src/agent/platform/http_api/routes/session.py` — 新增路由 + `ForkSessionRequest` / `ForkSessionResponse` 模型

### 5. POST /v1/sessions/{id}:rewind

**语义**：回到对话历史中指定消息节点，丢弃该节点之后的所有消息，从该点继续对话。被丢弃的消息在 JSONL 中物理保留（形成 DAG 死分支），但逻辑上不可见。

**Request**：
```json
{ "message_id": "msg_..." }
```

**Response**：
```json
{
  "session_id": "sess_...",
  "rewinded_to": "msg_...",
  "dropped_messages": 3
}
```

#### 业务逻辑归属：AgentRuntime

Rewind 需要操作 `_session_histories` 内存列表，截断到目标消息为止。属于 runtime 层职责。

**`AgentRuntime` 新增方法**：

```python
async def rewind_session(
    self,
    session_id: str,
    *,
    target_message_id: str,
) -> dict[str, Any]:
    """Rewind session history to target message, dropping all messages after it."""
    lock = self._session_locks.get(session_id)
    if lock:
        async with lock:
            return self._rewind_session_locked(session_id, target_message_id)
    return self._rewind_session_locked(session_id, target_message_id)

def _rewind_session_locked(self, session_id: str, target_message_id: str) -> dict[str, Any]:
    history = self._session_histories.get(session_id, [])
    if not history:
        raise ValueError(f"session has no history: {session_id}")

    # Find target index
    target_index = None
    for i, msg in enumerate(history):
        if msg.message_id == target_message_id:
            target_index = i
            break
    if target_index is None:
        raise ValueError(f"message not found in session: {target_message_id}")

    dropped = len(history) - target_index - 1
    if dropped <= 0:
        return {"session_id": session_id, "rewinded_to": target_message_id, "dropped_messages": 0}

    # Truncate memory history: keep [0..target_index]
    self._session_histories[session_id] = history[:target_index + 1]

    # Write a rewind_boundary marker to JSONL for resume correctness
    path = self._session_paths.get(session_id)
    if path is not None:
        self._jsonl_writer.enqueue(path, {
            "type": "rewind_boundary",
            "session_id": session_id,
            "timestamp": _utc_now_iso(),
            "target_uuid": target_message_id,
        })
        # Re-flush is optional; JSONL DAG structure guarantees correctness on next load

    return {"session_id": session_id, "rewinded_to": target_message_id, "dropped_messages": dropped}
```

**设计决策**：
- 内存截断后立即生效，下一次 `run()` 使用截断后的历史。
- JSONL 中不删除已写的 turn 行（只追加 `rewind_boundary` 标记）。resume 时 `build_conversation_chain()` 以最新 terminal 回溯，死分支自动被丢弃。
- target_message_id 必须存在于当前可见历史中（不在死分支中）。
- 不支持 rewinding to a message from a dead branch（那就是 fork 的语义了）。

**涉及文件**：
- `src/agent/core/agent/runtime.py` — 新增 `rewind_session()`
- `src/agent/platform/http_api/routes/session.py` — 新增路由 + `RewindSessionRequest` / `RewindSessionResponse` 模型

---

### 关于 session/resume

P1 **不实现** `:resume` 端点。

原因：
- `:resume` 在 ACP 语义上针对 SUSPENDED 状态的 session（与 `:load` 的差异正在于此）
- 当前系统没有 SUSPENDED 状态，实现出来与 GET /v1/sessions/{id} 完全相同，是无意义的空壳
- SUSPENDED 状态机设计复杂度独立，应在 P2 里整体设计 suspend/resume 生命周期，届时 `:resume` 才有实质内容

---

## 架构增补：SessionContextCache（已废弃，见 feat-330）

> **注意**：本节设计已废弃。SessionContextCache（LRU + idle timeout）是 stateless 架构下的补丁思维。正确方向是 feat-330 的进程内持有状态方案（JSONL + in-memory history）。本节仅保留历史记录，不应实现。

### 背景与动机（已废弃）

当前 `AgentRuntime.run()` 每次调用都会两次调用 `list_turn_messages(session_id)`（line 223 和 line 235），每次都走完整的 SQLite 查询。随着会话消息增长，这两次读取的代价越来越高。

### 设计

**新文件**：`src/agent/core/agent/session_cache.py`

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..session.models import TurnMessage  # 或实际消息类型

_DEFAULT_MAX_SIZE = 200       # 最多缓存 200 个 session
_DEFAULT_IDLE_TIMEOUT = 1800  # 30 分钟未访问自动逐出


@dataclass
class _CacheEntry:
    messages: list  # list[TurnMessage]，当前可见消息历史
    last_accessed: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        self.last_accessed = time.monotonic()


class SessionContextCache:
    """In-memory cache of materialized message history per session.

    Thread safety: RunsRegistry enforces one active run per session,
    so concurrent writers for the same session_id cannot exist.
    The lock here is only needed for LRU eviction (cross-session iteration).
    """

    def __init__(
        self,
        *,
        max_size: int = _DEFAULT_MAX_SIZE,
        idle_timeout: float = _DEFAULT_IDLE_TIMEOUT,
    ) -> None:
        self._max_size = max_size
        self._idle_timeout = idle_timeout
        self._entries: dict[str, _CacheEntry] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> list | None:
        """Return cached messages or None on miss."""
        with self._lock:
            entry = self._entries.get(session_id)
            if entry is None:
                return None
            if time.monotonic() - entry.last_accessed > self._idle_timeout:
                del self._entries[session_id]
                return None
            entry.touch()
            return list(entry.messages)  # 返回浅拷贝，防止调用方修改

    def set(self, session_id: str, messages: list) -> None:
        """Update or insert the cache entry, then evict if over capacity."""
        with self._lock:
            self._entries[session_id] = _CacheEntry(messages=list(messages))
            self._evict_if_needed()

    def evict(self, session_id: str) -> None:
        """Explicitly remove a session from cache (close / compaction)."""
        with self._lock:
            self._entries.pop(session_id, None)

    def _evict_if_needed(self) -> None:
        """LRU eviction when over max_size. Must be called under lock."""
        if len(self._entries) <= self._max_size:
            return
        lru_key = min(self._entries, key=lambda k: self._entries[k].last_accessed)
        del self._entries[lru_key]
```

### 集成点

**`AgentRuntime.__init__()`** — 与 `_session_file_states` 并排初始化：

```python
self._session_context_cache = SessionContextCache()
```

**`AgentRuntime.run()`** — cache-first 加载，run 结束后更新：

```python
# ---- run() 入口，替换现有的 list_turn_messages 调用 ----
cached = self._session_context_cache.get(session_id)
if cached is not None:
    history = cached
else:
    history = self._session_manager.list_turn_messages(session_id)

# ---- run() 末尾（turn 正常结束后），刷新 cache ----
final_history = self._session_manager.list_turn_messages(session_id)
self._session_context_cache.set(session_id, final_history)
```

这使每个 turn 的 SQLite 读次数从 2 次（缓存冷）→ 1 次（首次 run，末尾刷新）→ 1 次（后续 run，末尾刷新），命中时入口不再读 SQLite。

**`AgentRuntime.close_session()`** — 清理释放内存：

```python
def close_session(self, session_id: str) -> None:
    ...
    self._session_manager.archive_session(session_id)

    run_id = self._runs_registry.get_active_run_id(session_id)
    if run_id:
        self._runs_registry.cancel(run_id)

    self._session_context_cache.evict(session_id)   # ← 释放内存

    self._event_hub.publish(...)
```

**`AgentRuntime._compact_session()`** — 与现有 `_session_file_states.pop()` 并排：

```python
# 现有代码
self._session_file_states.pop(session_id, None)
# 新增
self._session_context_cache.evict(session_id)
```

compaction 改变了可见历史（summary 替换原始消息），必须使缓存失效，下次 run 重新从 SQLite 加载。

### 线程安全分析

- **写写安全**：`RunsRegistry` 保证同一 session 最多一个活跃 run，不存在并发写同一 session 的情况。
- **读写安全**：`get()`/`set()`/`evict()` 均在 `_lock` 下操作 `_entries`，跨 session 的 LRU 逐出与写入之间安全。
- **返回值隔离**：`get()` 返回浅拷贝，`set()` 存浅拷贝，防止调用方持有的引用意外修改缓存内容。

### 内存容量估算

一个 session 的 `list_turn_messages()` 结果：100 轮对话 × 平均 2KB = ~200KB。200 个 session = ~40MB。在典型 agent server 部署场景下可接受；max_size 可通过配置调整。

---

## 数据流汇总

```
GET /v1/sessions/{id}（增强）
  → session_service.get_session() → return full config

:close
  → runtime.close_session()
       → runs_registry.cancel(active_run_id)     # cancel 存量
       → jsonl_writer.flush_async()              # 等待落盘（加锁）
       → session_histories.pop(session_id)       # 释放内存
       → session_configs.pop(session_id)
       → session_paths.pop(session_id)
       → session_locks.pop(session_id)

:cancel
  → runs_registry.get_active_run_id()
  → runs_registry.cancel()

:fork
  → runtime.fork_session(source_id)
       → load source from JSONL if not in memory
       → session_manager.create_session()
       → re-stamp messages + enqueue to JSONL writer
       → flush_async()
       → register in _session_histories / _session_configs

:rewind
  → runtime.rewind_session(session_id, target_message_id)
       → find target index in _session_histories
       → truncate memory history to target
       → enqueue rewind_boundary to JSONL
```

---

## 错误码规范

| 场景 | HTTP | code |
|---|---|---|
| session 不存在 | 404 | `session_not_found` |
| source session 不在内存且 JSONL 缺失（fork/rewind） | 404 | `session_not_found` |
| target message 不存在于当前历史（rewind） | 400 | `message_not_found` |
| 无活跃 run（cancel） | 200 | — (had_active_run: false) |

---

---

## Coding CLI 改造设计

### 整体思路

参考 claude-code 的模式：
- **启动参数**：`--resume <session_id>`、`--fork <session_id>` 在进入 REPL 前完成会话切换（二者互斥）
- **REPL 命令**：`/resume`、`/fork`、`/close`、`/cancel` 在对话中随时操作
- **非交互命令**：`resume-session`、`fork-session`、`close-session`、`cancel-session` 供脚本调用

---

### Layer 1: ServerClient 新增方法（client.py）

```python
def get_session(self, *, session_id: str) -> dict[str, Any]:
    """Fetch full session config (enhanced GET)."""
    return self._request("GET", f"/v1/sessions/{session_id}")

def close_session(self, *, session_id: str) -> dict[str, Any]:
    return self._request("POST", f"/v1/sessions/{session_id}:close", json={})

def cancel_session(self, *, session_id: str) -> dict[str, Any]:
    return self._request("POST", f"/v1/sessions/{session_id}:cancel", json={})

def fork_session(self, *, session_id: str, metadata: dict | None = None) -> dict[str, Any]:
    return self._request("POST", f"/v1/sessions/{session_id}:fork",
                         json={"metadata": metadata or {}})

def rewind_session(self, *, session_id: str, message_id: str) -> dict[str, Any]:
    return self._request("POST", f"/v1/sessions/{session_id}:rewind",
                         json={"message_id": message_id})

def resume_session(self, *, session_id: str) -> dict[str, Any]:
    """Validate session exists and return its config. Actual load happens implicitly on next send_message via run() cache-miss."""
    return self._request("GET", f"/v1/sessions/{session_id}")
```

---

### Layer 2: REPL 命令扩展（repl_commands.py）

**新增命令**：

| 命令 | 参数 | 语义 |
|---|---|---|
| `/resume <session_id>` | 必填 | 验证 session 存在，切换到它 |
| `/fork` | 无 | fork 当前 session，切换到新 fork |
| `/rewind <message_id>` | 必填 | 回到指定消息节点，截断后续历史 |
| `/close` | 无 | 关闭当前 session 并退出 CLI |
| `/cancel` | 无 | 取消当前 session 的活跃 run |

更新 `REPL_COMMANDS` 常量：
```python
REPL_COMMANDS = (
    "/help", "/new", "/use", "/resume", "/fork", "/rewind", "/close", "/cancel",
    "/session", "/tools", "/compact", "/history", "/exit",
)
```

**命令实现逻辑**：

`/resume <session_id>`:
```
client.resume_session(session_id)  # GET，验证存在
  → 404: actionable error "session not found."
  → 成功: active_session_id = session_id
print_session_resumed(session_id)
```

`/fork`:
```
if not active_session_id → error: "no active session, run /new first."
payload = client.fork_session(session_id=active_session_id)
new_id = payload["session_id"]
print_session_forked(source_id=active_session_id, new_id=new_id)
active_session_id = new_id
```

`/close`:
```
if not active_session_id → error: "no active session."
client.close_session(session_id=active_session_id)
print_session_closed(session_id=active_session_id)
# close 后退出 REPL，语义与 /exit 一致（但先释放 server 内存）
should_exit = True
```

`/rewind <message_id>`:
```
if not active_session_id → error: "no active session."
if not message_id → error: "missing message_id for /rewind."
payload = client.rewind_session(session_id=active_session_id, message_id=message_id)
print_session_rewinded(session_id=active_session_id, target_id=message_id, dropped=payload["dropped_messages"])
```

`/cancel`（需处理 run_queue，防止取消后 queue 立即触发新 run）：
```
if not active_session_id → error: "no active session."

# 先暂停本地 queue，对齐 /exit 的处理模式
if run_queue is not None:
    run_queue.close(wait_for_drain=False, discard_pending=True)
    run_queue = None  # 取消后 queue 作废，需在外层重建

payload = client.cancel_session(session_id=active_session_id)
if payload["had_active_run"]:
    print "Cancelled run {cancelled_run_id} for session {id}."
else:
    print "No active run for session {id}."
```

注意：`run_queue` 是 `_run_repl()` 的局部变量，`handle_repl_command` 目前不能直接修改它。需将 `run_queue` 以可变容器形式传入，或通过返回值通知外层重建。建议在 `ReplCommandResult` 里增加 `reset_run_queue: bool = False` 字段，由外层 `_run_repl()` 负责重建。

---

### Layer 3: CLI 参数扩展（commands.py）

**REPL 启动参数**（`--resume` 和 `--fork` 互斥）：

```python
session_group = parser.add_mutually_exclusive_group()
session_group.add_argument(
    "--resume", dest="resume_session_id", default=None,
    metavar="SESSION_ID", help="Resume an existing session on startup.",
)
session_group.add_argument(
    "--fork", dest="fork_session_id", default=None,
    metavar="SESSION_ID", help="Fork an existing session on startup.",
)
```

在 `_run_repl()` 入口处处理：
```python
if args.resume_session_id:
    client.resume_session(session_id=args.resume_session_id)
    active_session_id = args.resume_session_id
    repl_commands.print_session_resumed(out=out, session_id=active_session_id)

elif args.fork_session_id:
    payload = client.fork_session(session_id=args.fork_session_id)
    active_session_id = payload["session_id"]
    repl_commands.print_session_forked(
        out=out, source_id=args.fork_session_id, new_id=active_session_id,
    )
```

**非交互子命令**：

```python
for name in ("resume-session", "fork-session", "close-session", "cancel-session"):
    p = subparsers.add_parser(name)
    p.add_argument("--session-id", required=True)

rewind_parser = subparsers.add_parser("rewind-session")
rewind_parser.add_argument("--session-id", required=True)
rewind_parser.add_argument("--message-id", required=True)
```

在 `_run_single_command()` 中分发：
```python
if args.command == "resume-session":
    return client.resume_session(session_id=args.session_id)
if args.command == "fork-session":
    return client.fork_session(session_id=args.session_id)
if args.command == "rewind-session":
    return client.rewind_session(session_id=args.session_id, message_id=args.message_id)
if args.command == "close-session":
    return client.close_session(session_id=args.session_id)
if args.command == "cancel-session":
    return client.cancel_session(session_id=args.session_id)
```

---

### Layer 4: 新增打印函数（repl_commands.py）

```python
def print_session_resumed(*, out: TextIO, session_id: str) -> None:
    _write_line(out, f"Resumed session {session_id}.")

def print_session_forked(*, out: TextIO, source_id: str, new_id: str) -> None:
    _write_line(out, f"Forked {source_id} → {new_id}.")

def print_session_closed(*, out: TextIO, session_id: str) -> None:
    _write_line(out, f"Closed session {session_id}.")

def print_session_rewinded(*, out: TextIO, session_id: str, target_id: str, dropped: int) -> None:
    _write_line(out, f"Rewinded session {session_id} to {target_id} ({dropped} messages dropped).")
```

---

## Milestone 划分

### M1 — P0 会话生命周期（HTTP + CLI）

**HTTP 层**：
1. `AgentRuntime.close_session()` 方法（cancel → flush JSONL → evict 内存）
2. `GET /v1/sessions/{id}` 增强（SessionResponse 补全配置字段：system_prompt / skills / tool_allowlist）
3. 2 个新路由：`:close`、`:cancel`

**CLI 层**：
4. `ServerClient` 新增 `get_session`、`close_session`、`cancel_session`、`resume_session` 方法
5. REPL 命令：`/close`、`/cancel`（含 run_queue 处理）
6. `ReplCommandResult` 增加 `reset_run_queue` 字段
7. 非交互子命令：`close-session`、`cancel-session`
8. 单元测试：HTTP 端点核心逻辑 + CLI 命令

> **依赖 feat-330**：进程内消息历史持有（`_session_histories`）、JSONL 持久化（`JsonlWriter` / `JsonlSessionStore`）由 feat-330 提供，feat-329 直接复用。

### M2 — P1 会话 Fork + Rewind（HTTP + CLI）

**HTTP 层**：
1. `AgentRuntime.fork_session()` 方法（从内存历史复制 + re-stamp uuid/parent_uuid + 写新 JSONL）
2. `AgentRuntime.rewind_session()` 方法（内存截断 + rewind_boundary 标记）
3. `:fork` 路由 + `ForkSessionRequest` / `ForkSessionResponse` 模型
4. `:rewind` 路由 + `RewindSessionRequest` / `RewindSessionResponse` 模型

**CLI 层**：
5. `ServerClient` 新增 `fork_session`、`rewind_session` 方法
6. REPL 命令：`/resume <session_id>`、`/fork`、`/rewind <message_id>`
7. CLI 启动参数：`--resume`、`--fork`（互斥 group）
8. 非交互子命令：`resume-session`、`fork-session`、`rewind-session`
9. 打印函数：`print_session_resumed`、`print_session_forked`、`print_session_rewinded`
10. 单元测试：fork 后历史独立、rewind 后历史截断正确

---

## 拒绝的方案

| 方案 | 拒绝原因 |
|---|---|
| 单独建 `:load` 路由 | F-330 下 resume 由 run() 隐式承载（cache miss → JSONL load）；增强 GET 足够 |
| P1 实现 `:resume` 端点 | 没有 SUSPENDED 状态支撑时与 GET 完全相同，是无意义空壳；留 P2 |
| `:close` 编排逻辑放 HTTP handler | 违反分层；关闭逻辑有副作用（cancel + flush + evict），属于 runtime 业务逻辑 |
| archive_session() + archived 状态 | F-330 明确废弃 archived 状态；JSONL 自然 resume 不需要 archive 封闭 |
| Fork 放在 SessionService 层 | F-330 下主数据源是 `_session_histories` 内存，fork 必须访问 runtime 内存状态；放 runtime 更直接 |
| Fork content 静默替换为空字符串 | 无声数据丢失；Message.content 已是 str \| list，直接复制 |
| `--resume`/`--fork` 不做互斥 | 两者同时传时行为未定义，argparse mutually_exclusive_group 一行解决 |
