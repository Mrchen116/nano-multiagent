# Session File State — 需求&设计文档

> 本文档定义 nano-multiagent 的**跨工具会话级文件状态基础设施**。核心决策：**强制 Read-Before-Write** —— Edit/Write 覆盖现有文件前，必须已读取过该文件且文件未被外部修改。

---

## 1. 背景与动机

### 1.1 当前问题

- **Write/Edit 直接覆盖**：模型可能在不知情的情况下覆盖用户最新修改或 linter 自动修复后的内容
- **无 staleness 感知**：文件被外部修改后，模型仍基于过时的内存副本做编辑
- **工具间状态断裂**：Read 的去重缓存 (`FileStateCache`) 只服务于 Read 自身，Write/Edit 无法消费

### 1.2 claude-code 的参照

claude-code 的 `readFileState` 是跨工具的会话级状态机：
- Read 后记录文件指纹（mtime + size + 读取范围）
- Write/Edit 覆盖前检查：未读 → errorCode 6 拒绝；读取后外部修改 → errorCode 7 拒绝
- 重复读取且 mtime 未变 → `file_unchanged` stub

**我们的策略**：与 claude-code 对齐，**强制 Read-Before-Write**，用 `ToolError` 拒绝违规操作。

---

## 2. 设计目标与非目标

### 2.1 目标 (In Scope)

1. **强制 Read-Before-Write**：Edit/Write 覆盖现有文件时，若文件未被当前 session 读取过，或读取后被修改，则拒绝操作
2. **file_unchanged 去重**：保留现有 `FileStateCache` 机制，重复读取未变更文件返回 stub
3. **会话级文件状态跟踪**：记录每个已读文件的 `(mtime_ns, size, offset, limit)`
4. **状态自动更新**：Edit/Write 成功后更新指纹，消除自我编辑导致的 stale 误报
5. **错误码体系**：为 Read-Before-Write 违规定义结构化错误码，供框架层决策（如未来 UI 弹窗）

### 2.2 非目标 (Out of Scope)

1. **内容级缓存**：不存储文件内容，只存元数据指纹
2. **增量续读 (next_offset)**：本次不自动推断续读范围
3. **外部进程实时监听**：不做 inotify/fs-watch，staleness 只在工具执行时检测
4. **is_error API 标记**：`tool_result` 中不设置 Anthropic/OpenAI 的 `is_error` 字段（保持纯文本错误）
5. **Bash 工具的间接修改检测**：Bash 通过 `sed -i` 等命令修改文件，不在本次检测范围内

---

## 3. 数据模型

### 3.1 FileReadState

```python
@dataclass(frozen=True, slots=True)
class FileReadState:
    file_path: str      # 绝对路径，规范化后存储
    mtime_ns: int       # 上次读取时的 st_mtime_ns
    size: int           # 上次读取时的 st_size
    offset: int | None  # 1-indexed，None 表示从第 1 行开始
    limit: int | None   # None 表示读到文件末尾
```

**设计决策**：
- `mtime_ns`（纳秒）精度高于 `mtime_ms`
- 不存 `was_full_read`：`offset` 和 `limit` 同时为 None/默认值即表示 full read

### 3.2 SessionFileState（容器）

```python
class SessionFileState:
    def __init__(self, capacity: int = 128) -> None: ...
    def get(self, file_path: str) -> FileReadState | None: ...
    def set(self, state: FileReadState) -> None: ...
    def is_stale(self, file_path: str) -> bool | None: ...
    def remove(self, file_path: str) -> None: ...
```

**与现有 FileStateCache 的关系**：
- `FileStateCache`（key=`(Path, offset, limit)`）继续负责 **Read 的分页级去重**
- `SessionFileState`（key=`str(规范化绝对路径)`）负责 **跨工具的 Read-Before-Write 校验**
- 两者共存，职责分离

---

## 4. 归属与生命周期

挂接在 `ToolContext` 上：

```python
@dataclass(frozen=True, slots=True)
class ToolContext:
    repo_root: Path
    cwd: Path
    safety: ToolSafetyLike
    read_file_state: FileStateCache | None      # 现有：分页级去重
    session_file_state: SessionFileState | None  # 新增：文件级状态
```

- **创建**：`AgentRuntime` 在每个 session 启动时创建 `SessionFileState`
- **共享**：同一 session 的所有 tool call 共享同一实例
- **销毁**：session 结束时随 GC 释放，不持久化

---

## 5. 错误码体系

| errorCode | 含义 | 触发条件 |
|-----------|------|----------|
| 6 | 文件尚未读取 | Write/Edit 覆盖现有文件时，`session_file_state` 无该文件记录 |
| 7 | 文件已过时 (stale) | Write/Edit 覆盖现有文件时，文件自上次读取后被修改 |

**携带方式**：`ToolError(details={"errorCode": 6|7, "filePath": ...})`
- 纯文本错误消息返回给 LLM（通过 `serialize_result` 的 `error` 参数）
- `errorCode` 留在 `details` 中供框架/ UI 层程序化处理
- 不设置 `is_error` API 标记

---

## 6. 与工具的集成

### 6.1 Read 工具

**file_unchanged 短路**（现有 `FileStateCache` 命中）：直接返回 stub，**跳过读取，不更新 `session_file_state`**。

**实际读取后**：更新 `session_file_state`。

```python
def run(self, args, ctx):
    # ... 现有 FileStateCache 检查（可能直接返回 file_unchanged）...

    # 实际读取完成后
    if ctx.session_file_state is not None:
        try:
            stat = file_path.stat()
            ctx.session_file_state.set(FileReadState(
                file_path=str(file_path.resolve()),
                mtime_ns=stat.st_mtime_ns,
                size=stat.st_size,
                offset=offset if offset > 1 else None,
                limit=limit,
            ))
        except (OSError, ValueError):
            pass

    return response
```

### 6.2 Write 工具

**规则**：
- **创建新文件**（`file_exists=False`）：不检查 Read-Before-Write，直接创建
- **覆盖现有文件**（`file_exists=True`）：强制检查

```python
def run(self, args, ctx):
    raw_path = str(args["path"])
    content = str(args["content"])
    file_path = ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)
    file_exists = file_path.exists()
    display_path = _display_path(file_path, ctx.repo_root)

    # -- Read-Before-Write 校验（仅覆盖现有文件时）--
    if file_exists and ctx.session_file_state is not None:
        file_path_str = str(file_path.resolve())
        state = ctx.session_file_state.get(file_path_str)

        if state is None:
            raise ToolError(
                f"Cannot overwrite {display_path} because it has not been read yet. "
                "Please read the file first to ensure you are aware of its current contents.",
                tool_name=self.name,
                details={"errorCode": 6, "filePath": display_path},
            )

        if ctx.session_file_state.is_stale(file_path_str) is True:
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
            ctx.session_file_state.set(FileReadState(
                file_path=str(file_path.resolve()),
                mtime_ns=stat.st_mtime_ns,
                size=stat.st_size,
                offset=None,
                limit=None,
            ))
        except (OSError, ValueError):
            pass

    return {
        "type": "update" if file_exists else "create",
        "filePath": str(file_path),
        "displayPath": display_path,
    }
```

### 6.3 Edit 工具

Edit 只操作现有文件，**始终检查 Read-Before-Write**。

```python
def run(self, args, ctx):
    # ... 解析路径 ...
    file_path = ctx.safety.resolve_path(raw_path, cwd=ctx.cwd, tool_name=self.name)

    if not file_path.exists() or not file_path.is_file():
        raise ToolError("file does not exist", tool_name=self.name, details={"path": raw_path})

    # -- Read-Before-Write 校验 --
    if ctx.session_file_state is not None:
        file_path_str = str(file_path.resolve())
        state = ctx.session_file_state.get(file_path_str)

        if state is None:
            raise ToolError(
                f"Cannot edit {display_path} because it has not been read yet. "
                "Please read the file first to ensure you are aware of its current contents.",
                tool_name=self.name,
                details={"errorCode": 6, "filePath": display_path},
            )

        if ctx.session_file_state.is_stale(file_path_str) is True:
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
            ctx.session_file_state.set(FileReadState(
                file_path=str(file_path.resolve()),
                mtime_ns=stat.st_mtime_ns,
                size=stat.st_size,
                offset=None,
                limit=None,
            ))
        except (OSError, ValueError):
            pass

    return {
        "filePath": str(file_path),
        "displayPath": display_path,
        # ...
    }
```

### 6.4 Bash 工具

**当前不做集成**。Bash 可能通过 `sed -i`、`echo > file` 等间接修改文件，检测这种修改需要命令 AST 分析或执行后扫描，超出本次范围。未来可通过 Hook 机制在 Bash 执行后扫描受影响文件并更新 `SessionFileState`。

---

## 7. Staleness 检测

```python
def is_stale(self, file_path: str) -> bool | None:
    normalized = str(Path(file_path).resolve())
    state = self._states.get(normalized)
    if state is None:
        return None
    try:
        stat = Path(file_path).stat()
        return stat.st_mtime_ns != state.mtime_ns or stat.st_size != state.size
    except (OSError, ValueError):
        return None
```

**指纹策略**：`mtime_ns + size` 双指纹。
- 不引入内容哈希（成本 O(n)，与 Read 相当）
- 若后续发现 mtime 不可靠（如 FAT32），再引入 SHA-256 fallback

---

## 8. 与 claude-code 的对照

| 维度 | claude-code | nano-multiagent (本设计) |
|------|-------------|--------------------------|
| **Read-Before-Write** | 强制：未读/stale 均拒绝 | **强制**：未读/stale 均拒绝 |
| **Staleness 处理** | 拒绝写入（errorCode 7） | **拒绝写入**（errorCode 7） |
| **错误码** | errorCode 6/7 | **errorCode 6/7** |
| **is_error 标记** | 设置 `is_error: true` | **不设置** |
| **错误呈现** | 结构化错误 + UI 弹窗 | **纯文本错误消息** |
| **状态粒度** | 文件级 | **文件级** |
| **去重粒度** | 文件级 | **分页级** `(path, offset, limit)` + 文件级 |
| **指纹策略** | mtime + size + 内容 fallback | **mtime_ns + size** |
| **状态持久化** | 不持久化 | **不持久化** |

---

## 9. 实施计划

### Phase 1：基础设施

| 文件 | 动作 | 说明 |
|------|------|------|
| `src/agent/core/tools/session_file_state.py` | 新增 | `FileReadState` + `SessionFileState` |
| `src/agent/core/tools/base.py` | 修改 | `ToolContext` 增加 `session_file_state` |
| `src/agent/core/agent/runtime.py` | 修改 | session 启动时创建 `SessionFileState` 并注入 |

### Phase 2：Read 工具集成

| 文件 | 动作 | 说明 |
|------|------|------|
| `src/agent/platform/tools/builtins/read.py` | 修改 | 实际读取后更新 `session_file_state` |

### Phase 3：Write / Edit 强制校验

| 文件 | 动作 | 说明 |
|------|------|------|
| `src/agent/platform/tools/builtins/write.py` | 修改 | 覆盖现有文件前检查 Read-Before-Write；写入后更新状态 |
| `src/agent/platform/tools/builtins/edit.py` | 修改 | 编辑前检查 Read-Before-Write；编辑后更新状态 |

### Phase 4：测试与文档

| 文件 | 动作 | 说明 |
|------|------|------|
| `tests/unit/test_session_file_state.py` | 新增 | LRU、get/set/is_stale/remove 单元测试 |
| `tests/unit/test_tools_builtins.py` | 修改 | 补充 Write/Edit 的 Read-Before-Write 拒绝测试 |
| `docs/tools-diff-cc/session-file-state-design.md` | 新增 | 本文档 |

---

## 10. 风险与回退策略

1. **stat() 失败**：文件被删除/权限变更等导致 `stat()` 失败 → `is_stale()` 返回 `None`，按"未知"处理，不拒绝（安全降级：宁可放行也不误杀）
2. **纳秒精度不足**：某些文件系统（FAT32）无纳秒 mtime → 可能误报 stale。发现后引入内容哈希 fallback
3. **Bash 间接修改漏检**：`bash: sed -i file` 不更新 state → 下次 Edit/Write 正确报 stale（模型需要 re-read）
4. **首次 Write 覆盖空文件**：空文件已存在但从未被 Read → 拒绝。这是预期行为，强制模型先了解现有内容
5. **大文件 stat 开销**：`stat()` 是 O(1)，无实际开销

---

## 11. 后续演进

1. **Hook 系统集成**：Bash 执行后自动扫描修改的文件并更新 `SessionFileState`
2. **内容哈希 fallback**：在 mtime 不可靠的文件系统上启用 SHA-256
3. **增量续读**：利用 `offset + limit + total_lines` 自动计算 `next_offset`
4. **"ask" 行为升级**：框架层识别 errorCode 6/7，弹窗让用户确认"仍然覆盖"，而非直接拒绝
