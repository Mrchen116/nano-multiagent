# Session File State — 需求&设计文档

> 本文档定义 nano-multiagent 的**跨工具会话级文件状态基础设施**。核心决策：用一个统一的 `SessionFileState` 取代现有的 `FileStateCache`，同时支撑 Read 去重和 Write/Edit 的 Read-Before-Write 校验。

---

## 1. 背景与动机

### 1.1 当前问题

- **Write/Edit 直接覆盖**：模型可能在不知情的情况下覆盖用户最新修改或 linter 自动修复后的内容
- **无 staleness 感知**：文件被外部修改后，模型仍基于过时的内存副本做编辑
- **状态容器分裂**：现有 `FileStateCache` 只做 Read 分页去重，Write/Edit 无法消费；需要引入新容器，增加认知负担

### 1.2 claude-code 的参照

claude-code 只有一个 `readFileState`：
- **文件级**，key = 绝对路径，不区分 offset/limit
- **同时服务两个场景**：
  1. Read 去重：同一文件再次读取且 mtime 未变 → `file_unchanged`
  2. Read-Before-Write：Write/Edit 覆盖前检查是否已读、是否 stale
- **强制拒绝**：未读 → errorCode 6；stale → errorCode 7

**我们的策略**：与 claude-code 对齐——**单一容器、强制 Read-Before-Write**。

---

## 2. 设计目标与非目标

### 2.1 目标 (In Scope)

1. **统一状态容器**：一个 `SessionFileState` 取代 `FileStateCache`，同时支撑 Read 去重和 Read-Before-Write
2. **强制 Read-Before-Write**：Edit/Write 覆盖现有文件时，未读或 stale 均拒绝
3. **file_unchanged 去重**：重复读取同一文件（最后记录的范围）且 mtime 未变，返回 stub
4. **状态自动更新**：Edit/Write 成功后更新指纹，消除自我编辑导致的 stale 误报
5. **错误码体系**：errorCode 6（未读）、errorCode 7（stale），放在 `ToolError.details` 中
6. **压缩后清空**：Session compaction 发生时清空该 session 的 `SessionFileState`。因为 compaction 会删除 Read 的 tool_result，模型实际上已无法看到文件内容，此时若 state 仍说"已读"等于让模型蒙眼编辑

### 2.2 非目标 (Out of Scope)

1. **分页级去重**（精确匹配历史上任意一次 `(path, offset, limit)`）：改为文件级去重（匹配最后一次读取范围），与 claude-code 对齐
2. **内容级缓存**：不存文件内容，只存元数据指纹
3. **增量续读**：不自动推断续读范围
4. **外部进程实时监听**：不做 inotify/fs-watch
5. **is_error API 标记**：不设置 Anthropic/OpenAI 的 `is_error`
6. **Bash 间接修改检测**：`sed -i` 等不在本次范围

---

## 3. 架构决策：为什么合并为一个容器

### 3.1 当前分裂的问题

| 维度 | `FileStateCache`（现有） | `SessionFileState`（原设计） |
|------|-------------------------|----------------------------|
| key | `(Path, offset, limit)` | `str(绝对路径)` |
| 用途 | Read 分页去重 | Read-Before-Write |
| 存储 | `(mtime_ms, size)` | `FileReadState` |
| 容量 | 128 | 128 |

**问题**：
- 两者管理的是**同一类状态**（文件读取后的元数据），却用两个独立容器
- 数据冗余：都存 mtime + size
- 认知负担：开发者要理解两个缓存的语义差异
- 与 claude-code 不一致：cc 只有一个 `readFileState`

### 3.2 合并后的设计

用一个 `SessionFileState`，key = 文件路径，value = `FileReadState`（含最后读取的 offset/limit）。

**去重行为**：
`check_unchanged` 同时比较文件指纹（mtime_ns + size）和读取范围（offset + limit）。只有**范围完全相同且文件未变**时才返回 True。不同范围代表不同内容，正常读取——这是正确行为。

**与旧 FileStateCache 的区别**：
- 旧：`FileStateCache` key 是 `(path, offset, limit)`，可以同时记住同一文件的多个不同范围，每个独立去重
- 新：`SessionFileState` 每个文件只保留**最后一次**读取的范围。如果模型读 A 范围后，又读 B 范围，再回头读 A 范围，A 范围的去重信息已丢失

**取舍**：后者在"同一文件交替读不同范围"的场景下会多一次磁盘读取，但典型工作流中极少出现。换来的收益是：
- 单一容器，概念统一
- 消除数据冗余
- 与 claude-code 架构对齐
- 容量 128 指文件数，语义清晰

---

## 4. 数据模型

### 4.1 FileReadState

```python
@dataclass(frozen=True, slots=True)
class FileReadState:
    file_path: str      # 绝对路径，规范化后存储
    mtime_ns: int       # 上次读取时的 st_mtime_ns
    size: int           # 上次读取时的 st_size
    offset: int | None  # 最后一次读取的 offset（1-indexed，None=从头）
    limit: int | None   # 最后一次读取的 limit（None=到末尾）
```

**设计决策**：
- `mtime_ns`（纳秒）替代 `mtime_ms`：Python `os.stat` 原生提供
- 不存 `was_full_read`：`offset=None` 且 `limit=None` 即表示 full read

### 4.2 SessionFileState（统一容器）

```python
class SessionFileState:
    """Session-scoped file read state tracker.

    同时服务两个场景：
    1. Read 去重：同一文件同一范围且 mtime 未变 → file_unchanged
    2. Read-Before-Write：检查文件是否已读、是否 stale
    """

    def __init__(self, capacity: int = 128) -> None:
        self._capacity = max(1, capacity)
        self._states: OrderedDict[str, FileReadState] = OrderedDict()

    def check_unchanged(self, file_path: str, offset: int | None,
                        limit: int | None) -> bool:
        """Return True if this exact range was last read and file is unchanged."""
        normalized = str(Path(file_path).resolve())
        state = self._states.get(normalized)
        if state is None:
            return False
        if state.offset != offset or state.limit != limit:
            return False
        try:
            stat = Path(file_path).stat()
            return stat.st_mtime_ns == state.mtime_ns and stat.st_size == state.size
        except (OSError, ValueError):
            return False

    def record_read(self, file_path: str, mtime_ns: int, size: int,
                    offset: int | None, limit: int | None) -> None:
        """记录一次成功读取，覆盖该文件的最后读取范围。"""
        normalized = str(Path(file_path).resolve())
        state = FileReadState(
            file_path=normalized,
            mtime_ns=mtime_ns,
            size=size,
            offset=offset,
            limit=limit,
        )
        if normalized in self._states:
            self._states.move_to_end(normalized)
        self._states[normalized] = state
        if len(self._states) > self._capacity:
            self._states.popitem(last=False)

    def can_write(self, file_path: str) -> tuple[bool, int | None]:
        """检查是否可以写入/编辑。

        Returns:
            (True, None)  — 可以写入（文件已读且未 stale）
            (False, 6)    — 错误码 6：文件尚未读取
            (False, 7)    — 错误码 7：文件已 stale
        """
        normalized = str(Path(file_path).resolve())
        state = self._states.get(normalized)
        if state is None:
            return False, 6
        try:
            stat = Path(file_path).stat()
            if stat.st_mtime_ns != state.mtime_ns or stat.st_size != state.size:
                return False, 7
            return True, None
        except (OSError, ValueError):
            return False, 6

    def record_write(self, file_path: str, mtime_ns: int, size: int) -> None:
        """记录一次成功写入，更新指纹以消除自我编辑导致的 stale 误报。

        写入后 offset/limit 设为 None/None，因为 Write 是整文件重写。
        """
        normalized = str(Path(file_path).resolve())
        state = FileReadState(
            file_path=normalized,
            mtime_ns=mtime_ns,
            size=size,
            offset=None,
            limit=None,
        )
        if normalized in self._states:
            self._states.move_to_end(normalized)
        self._states[normalized] = state
        if len(self._states) > self._capacity:
            self._states.popitem(last=False)

    def remove(self, file_path: str) -> None:
        """移除指定路径的状态记录（文件被删除时）。"""
        normalized = str(Path(file_path).resolve())
        self._states.pop(normalized, None)
```

---

## 5. 归属与生命周期

### 5.1 挂接位置

```python
@dataclass(frozen=True, slots=True)
class ToolContext:
    repo_root: Path
    cwd: Path
    safety: ToolSafetyLike
    session_file_state: SessionFileState | None  # 统一容器（取代 read_file_state）
```

- **read_file_state 字段废弃**：`FileStateCache` 及 `SessionFileReadCache` 一并删除
- **session_file_state 替代**：所有现有 `read_file_state` 的引用迁移到 `session_file_state`

### 5.2 生命周期

1. **创建**：`AgentRuntime` 在每个 session 启动时创建 `SessionFileState`（通过 `dict[str, SessionFileState]` 按 session_id 隔离）
2. **共享**：同一 session 的所有 turn/tool call 共享同一实例
3. **压缩后清空**：`AgentRuntime._compact_session()` 成功执行后，清空 `self._session_file_states[session_id]`。原因：compaction 删除了历史 Read 消息，模型不再能看到文件内容，此时必须强制重新 Read
4. **销毁**：session 结束时随 GC 释放，不持久化

```python
# AgentRuntime
self._session_file_states: dict[str, SessionFileState] = {}

# _execute_loop 中获取（不存在则新建）
session_file_state = self._session_file_states.setdefault(session_id, SessionFileState())

# _compact_session 成功后清空
self._session_file_states.pop(session_id, None)
```

---

## 6. 错误码体系

| errorCode | 含义 | 触发条件 |
|-----------|------|----------|
| 6 | 文件尚未读取 | Write/Edit 覆盖现有文件时，`session_file_state` 无该文件记录，或 stat 失败 |
| 7 | 文件已过时 (stale) | Write/Edit 覆盖现有文件时，文件 mtime_ns 或 size 与记录不一致 |

**携带方式**：`ToolError(details={"errorCode": 6|7, "filePath": ...})`
- 纯文本错误消息返回给 LLM（通过 `serialize_result` 的 `error` 参数）
- `errorCode` 留在 `details` 中供框架/ UI 层程序化处理
- 不设置 `is_error` API 标记

---

## 7. 与工具的集成

### 7.1 Read 工具

**改动点**：
1. **去重检查**：用 `session_file_state.check_unchanged()` 替代 `read_file_state.get()`
2. **命中后**：直接返回 `file_unchanged`，**不更新状态**（因为没有真正读取）
3. **实际读取后**：调用 `session_file_state.record_read()` 更新最后读取范围

```python
def run(self, args, ctx):
    raw_path = str(args["path"])
    file_path = ctx.safety.resolve_read_path(raw_path, cwd=ctx.cwd, tool_name=self.name)

    if not file_path.exists() or not file_path.is_file():
        raise ToolError("file does not exist", tool_name=self.name, details={"path": raw_path})

    offset = int(args.get("offset", 1))
    if offset < 1:
        raise ToolError("offset must be >= 1", tool_name=self.name)

    limit = args.get("limit")
    if limit is not None:
        limit = int(limit)
        if limit < 1:
            raise ToolError("limit must be >= 1", tool_name=self.name)

    display_path = _display_path(file_path, ctx.repo_root)

    # -- 去重检查（取代 FileStateCache）--
    if ctx.session_file_state is not None:
        try:
            normalized_offset = offset if offset > 1 else None
            if ctx.session_file_state.check_unchanged(str(file_path.resolve()),
                                                       normalized_offset, limit):
                return {"type": "file_unchanged", "file": {"filePath": display_path}}
        except (OSError, ValueError):
            pass

    # ... 现有读取逻辑（文本/图像）...

    # -- 读取后更新状态 --
    if ctx.session_file_state is not None:
        try:
            stat = file_path.stat()
            ctx.session_file_state.record_read(
                file_path=str(file_path.resolve()),
                mtime_ns=stat.st_mtime_ns,
                size=stat.st_size,
                offset=normalized_offset,
                limit=limit,
            )
        except (OSError, ValueError):
            pass

    return response
```

### 7.2 Write 工具

**规则**：
- **创建新文件**（`file_exists=False`）：不检查，直接创建
- **覆盖现有文件**（`file_exists=True`）：强制检查 Read-Before-Write

```python
def run(self, args, ctx):
    raw_path = str(args["path"])
    content = str(args["content"])
    file_path = ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)
    file_exists = file_path.exists()
    display_path = _display_path(file_path, ctx.repo_root)

    # -- Read-Before-Write 校验（仅覆盖现有文件时）--
    if file_exists and ctx.session_file_state is not None:
        can_write, error_code = ctx.session_file_state.can_write(str(file_path.resolve()))
        if not can_write:
            if error_code == 6:
                raise ToolError(
                    f"Cannot overwrite {display_path} because it has not been read yet. "
                    "Please read the file first to ensure you are aware of its current contents.",
                    tool_name=self.name,
                    details={"errorCode": 6, "filePath": display_path},
                )
            elif error_code == 7:
                raise ToolError(
                    f"Cannot overwrite {display_path} because it was modified externally "
                    "since it was last read. Please re-read the file to get the latest contents.",
                    tool_name=self.name,
                    details={"errorCode": 7, "filePath": display_path},
                )

    # -- 执行写入 --
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    # -- 更新 session_file_state --
    # 目的：消除自我编辑导致的 stale 误报。
    # 如果 Write 后不更新，下一次对同一文件的 Edit/Write 会把自己刚写的
    # 内容误判为"外部修改"而拒绝。
    if ctx.session_file_state is not None:
        try:
            stat = file_path.stat()
            ctx.session_file_state.record_write(
                file_path=str(file_path.resolve()),
                mtime_ns=stat.st_mtime_ns,
                size=stat.st_size,
            )
        except (OSError, ValueError):
            pass

    return {
        "type": "update" if file_exists else "create",
        "filePath": str(file_path),
        "displayPath": display_path,
    }
```

### 7.3 Edit 工具

Edit 只操作现有文件，**始终检查 Read-Before-Write**。

```python
def run(self, args, ctx):
    # ... 解析路径 ...
    file_path = ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)

    if not file_path.exists() or not file_path.is_file():
        raise ToolError("file does not exist", tool_name=self.name, details={"path": raw_path})

    display_path = _display_path(file_path, ctx.repo_root)

    # -- Read-Before-Write 校验 --
    if ctx.session_file_state is not None:
        can_write, error_code = ctx.session_file_state.can_write(str(file_path.resolve()))
        if not can_write:
            if error_code == 6:
                raise ToolError(
                    f"Cannot edit {display_path} because it has not been read yet. "
                    "Please read the file first to ensure you are aware of its current contents.",
                    tool_name=self.name,
                    details={"errorCode": 6, "filePath": display_path},
                )
            elif error_code == 7:
                raise ToolError(
                    f"Cannot edit {display_path} because it was modified externally "
                    "since it was last read. Please re-read the file to get the latest contents.",
                    tool_name=self.name,
                    details={"errorCode": 7, "filePath": display_path},
                )

    # ... 执行编辑 ...

    # -- 更新 session_file_state --
    # 目的同 Write：消除自我编辑导致的 stale 误报
    if ctx.session_file_state is not None:
        try:
            stat = file_path.stat()
            ctx.session_file_state.record_write(
                file_path=str(file_path.resolve()),
                mtime_ns=stat.st_mtime_ns,
                size=stat.st_size,
            )
        except (OSError, ValueError):
            pass

    return {
        "filePath": str(file_path),
        "displayPath": display_path,
        # ...
    }
```

### 7.4 Bash 工具

**当前不做集成**。Bash 可能通过 `sed -i`、`echo > file` 等间接修改文件，检测这种修改需要命令 AST 分析或执行后扫描，超出本次范围。未来可通过 Hook 机制在 Bash 执行后扫描受影响文件并更新 `SessionFileState`。

---

## 8. 与 claude-code 的对照

| 维度 | claude-code | nano-multiagent (本设计) |
|------|-------------|--------------------------|
| **状态容器** | 一个 `readFileState` | **一个 `SessionFileState`** |
| **Read-Before-Write** | 强制拒绝 | **强制拒绝** |
| **Staleness 处理** | 拒绝（errorCode 7） | **拒绝（errorCode 7）** |
| **错误码** | errorCode 6/7 | **errorCode 6/7** |
| **is_error 标记** | 设置 `is_error: true` | **不设置** |
| **去重粒度** | 文件级（不区分 offset/limit） | **文件级（匹配最后读取范围）** |
| **指纹策略** | mtime + size + 内容 fallback | **mtime_ns + size** |
| **状态持久化** | 不持久化 | **不持久化** |
| **压缩后行为** | `readFileState` 保留（存 content 但 LLM 看不到） | **清空 `SessionFileState`**（LLM 实际看不到 = 视为未读） |

---

## 9. 实施计划

### Phase 1：基础设施

| 文件 | 动作 | 说明 |
|------|------|------|
| `src/agent/core/tools/session_file_state.py` | 新增 | `FileReadState` + `SessionFileState`，取代现有 `file_state_cache.py` |
| `src/agent/core/tools/base.py` | 修改 | `ToolContext`：`read_file_state` 字段改为 `session_file_state` |
| `src/agent/core/tools/file_state_cache.py` | 删除 | `FileStateCache` + `SessionFileReadCache` 废弃 |
| `src/agent/core/agent/runtime.py` | 修改 | `AgentRuntime` 维护 `dict[str, SessionFileState]`；`_execute_loop` 时按 session_id 获取/新建；`_compact_session` 成功后清空 |

### Phase 2：Read 工具集成

| 文件 | 动作 | 说明 |
|------|------|------|
| `src/agent/platform/tools/builtins/read.py` | 修改 | 去重逻辑改用 `session_file_state.check_unchanged()`；读取后调用 `record_read()` |

### Phase 3：Write / Edit 强制校验

| 文件 | 动作 | 说明 |
|------|------|------|
| `src/agent/platform/tools/builtins/write.py` | 修改 | 覆盖前调用 `can_write()`；写入后调用 `record_write()` |
| `src/agent/platform/tools/builtins/edit.py` | 修改 | 编辑前调用 `can_write()`；编辑后调用 `record_write()` |

### Phase 4：测试与文档

| 文件 | 动作 | 说明 |
|------|------|------|
| `tests/unit/test_session_file_state.py` | 新增 | 统一容器的单元测试（check_unchanged、record_read、can_write、record_write、LRU） |
| `tests/unit/test_tools_builtins.py` | 修改 | 补充 Read 去重、Write/Edit Read-Before-Write 拒绝测试 |
| `docs/tools-diff-cc/session-file-state-design.md` | 新增 | 本文档 |

---

## 10. 风险与回退策略

1. **压缩后需要重新 Read**：compaction 清空 state 后，之前读过的文件都需要重新 Read 才能 Edit。这是有意为之，确保模型确实知道自己在改什么
2. **stat() 失败**：文件被删除/权限变更 → `can_write()` 返回 errorCode 6（按未读处理，安全降级：宁可拒绝也不误放行）
2. **纳秒精度不足**：某些文件系统（FAT32）无纳秒 mtime → 可能误报 stale。这是可接受的权衡，不引入内容哈希
3. **Bash 间接修改漏检**：`bash: sed -i file` 不更新 state → 下次 Edit/Write 正确报 stale（模型需要 re-read）
4. **首次 Write 覆盖空文件**：空文件已存在但从未被 Read → 拒绝。这是预期行为，强制模型先了解现有内容
5. **分页去重粒度降级**：同一文件不同范围不会触发去重。典型工作流中极少发生，claude-code 也采用此粒度
6. **大文件 stat 开销**：`stat()` 是 O(1)，无实际开销

---

## 11. 后续演进

1. **Hook 系统集成**：Bash 执行后自动扫描修改的文件并更新 `SessionFileState`
2. **增量续读**：利用 `offset + limit + total_lines` 自动计算 `next_offset`
3. **"ask" 行为升级**：框架层识别 errorCode 6/7，弹窗让用户确认"仍然覆盖"，而非直接拒绝
