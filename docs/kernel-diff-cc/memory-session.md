# 记忆与会话持久化 —— nano-multiagent vs Claude Code

> 对比维度：session 持久化、记忆系统、跨会话状态、resume/continue

---

## 1. Session 持久化

### Claude Code

**两种持久化路径**：

#### 1.1 REPL 模式 —— useLogMessages

```ts
// src/hooks/useLogMessages.ts
```

- 消息实时写入 JSONL 文件
- 路径：`~/.claude/projects/<cwd>/<sessionId>.jsonl`
- 包含完整的消息历史

#### 1.2 SDK/Print 模式 —— QueryEngine

```ts
// src/QueryEngine.ts
recordTranscript(messages)  // fire-and-forget 写入 JSONL
```

#### 1.3 Session Resume

```bash
claude -c          # 继续最近对话
claude -r <id>     # 恢复指定对话
```

恢复时：
1. 加载 JSONL → messages[]
2. 恢复文件历史快照（`fileHistorySnapshots`）
3. 恢复成本状态（`restoreCostStateForSession`）
4. 重建 initialState

### nano-multiagent

**事件溯源架构**：

```python
# SessionStore (抽象)
#   ├── append_event(session_id, entry)
#   ├── load_session(session_id) → LoadedSession
#   └── save_snapshot(session_id, snapshot)
#
# SessionManager (业务逻辑)
#   ├── create_session() → 生成 SessionCreated event + snapshot
#   ├── append_turn_message() → 生成 TurnAppended event
#   ├── append_compaction() → 生成 Compaction event
#   └── list_turn_messages() → 重放 events
```

**实现存储**：
- `JSONLStore`：JSONL 文件存储
- `SQLiteStore`：SQLite 数据库存储

**与 CC 的差异**：

| 特性 | Claude Code | nano-multiagent |
|------|------------|-----------------|
| 持久化格式 | JSONL | JSONL + SQLite |
| 架构模式 | 直接消息写入 | 事件溯源 |
| Snapshot | 文件历史快照 | Session snapshot |
| Resume 命令 | `-c`, `-r` | 无 CLI 命令 |
| 成本恢复 | 恢复成本状态 | 无成本状态 |
| 文件快照 | 有 | 无 |

**缺陷**：
1. 无 `-c`/`-r` 命令行恢复机制
2. 无文件历史快照，恢复时文件状态可能不一致
3. 无成本状态恢复

---

## 2. 记忆系统 (Memdir)

### Claude Code —— 完整记忆系统

```ts
// src/memdir/
memdir.ts           // 核心记忆目录管理
memoryTypes.ts      // 记忆类型定义
memoryAge.ts        // 记忆年龄管理
memoryScan.ts       // 记忆扫描
findRelevantMemories.ts  // 相关记忆查找
paths.ts            // 记忆路径
```

**记忆类型**：
- 用户记忆：`~/.claude/memory/`
- 项目记忆：`.claude/memory/`
- 团队记忆：`src/memdir/teamMemPaths.ts`

**记忆功能**：
- 自动扫描和索引记忆文件
- 根据上下文查找相关记忆
- 记忆年龄管理（自动清理旧记忆）
- 记忆形状遥测

**在对话中的使用**：
- `getMemoryFiles()` → `filterInjectedMemoryFiles()` → 注入到 user context
- 模型可以读取记忆文件来了解用户偏好和项目上下文

### nano-multiagent —— 无记忆系统

- 无 `memdir` 概念
- 无持久化用户/项目记忆
- `~/.claude/projects/.../memory/` 目录未使用
- 跨会话只有 session 持久化，没有记忆层

**缺陷**：
1. 每次新会话都是"白板"，无法继承用户偏好
2. 无法记住跨项目的常用命令或配置
3. 无用户画像积累

---

## 3. CLAUDE.md / 项目上下文

### Claude Code

**自动发现**：

```ts
// src/utils/claudemd.ts
getClaudeMds()  // 自动发现 CLAUDE.md 文件
getMemoryFiles()  // 自动发现记忆文件
```

发现路径：
- 当前目录
- 父目录（向上递归）
- `--add-dir` 指定的额外目录

**注入方式**：
- CLAUDE.md 内容通过 `getUserContext()` 注入
- 缓存在 `getUserContext.cache` 中
- 可以通过 `--system-prompt` 追加

### nano-multiagent

- 无 CLAUDE.md 自动发现
- 系统提示通过 `system_prompt` 参数传入
- 产品层的 `prompts.py` 定义了静态系统提示

**缺陷**：
1. 无项目级上下文自动加载
2. 无用户级全局配置
3. 系统提示完全静态，无法根据项目自适应

---

## 4. 跨会话状态

### Claude Code

- **Session 成本**：`saveCurrentSessionCosts()` / `restoreCostStateForSession()`
- **Session 历史**：`loadConversationForResume()`
- **文件快照**：`initialFileHistorySnapshots`
- **Agent 名称**：`initialAgentName`
- **记忆**：跨会话持久化的记忆文件

### nano-multiagent

- **Session 事件**：通过 `SessionStore` 持久化
- **Snapshot**：每次 session 创建时保存 snapshot
- 无成本状态、无文件快照、无记忆

---

## 5. 关键差距总结

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| Session 恢复命令 | `-c`, `-r` | 无 | 🟡 中 |
| 文件历史快照 | 有 | 无 | 🟡 中 |
| 成本状态恢复 | 有 | 无 | 🟢 低 |
| 记忆系统 (memdir) | 完整 | 无 | 🔴 高 |
| 用户记忆 | `~/.claude/memory/` | 无 | 🔴 高 |
| 项目记忆 | `.claude/memory/` | 无 | 🟡 中 |
| 团队记忆 | 有 | 无 | 🟢 低 |
| CLAUDE.md 自动发现 | 有 | 无 | 🟡 中 |
| 上下文记忆注入 | 有 | 无 | 🟡 中 |
| 记忆年龄管理 | 有 | 无 | 🟢 低 |
