# Spec: Session Context Storage 改造（参考 Claude Code）

## 背景

当前系统使用 SQLite 事件源存储会话历史，`AgentRuntime` 每次 `run()` 调用都从数据库重新加载完整消息历史。这种架构简洁、无状态、易于水平扩展，但随着会话消息增长，存在以下问题：

1. **重复 I/O**：每次 turn 调用 `list_turn_messages()` 两次（run 入口 + append 后重新加载）
2. **Close 语义缺失**：`:close` 只能 archive session，没有可释放的内存上下文
3. **对话结构局限**：线性事件序列不支持从中间某条消息分叉或回溯
4. **恢复效率**：大 session 的 SQLite replay 代价随消息量线性增长

Claude Code 采用 JSONL 链式结构 + 进程内状态持有的模式，在语义丰富性和恢复效率上有显著优势。本 feature 旨在参考 claude-code 的上下文存储设计，补齐我们的架构短板。

---

## Claude Code 上下文存储架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Claude Code 架构                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐     ┌──────────────────┐                             │
│   │  AppStateStore   │◄────│  sessionState.ts  │  ← 进程内持有完整 reactive 状态 │
│   │  (in-memory)     │     │  idle|running|requires_action                  │
│   │  tasks, messages │     └──────────────────┘                             │
│   │  permissions     │                                                     │
│   └────────┬────────┘                                                     │
│            │                                                                │
│   ┌────────▼────────┐     ┌─────────────────────────────────────────────┐ │
│   │ sessionStorage.ts │     │  JSONL Transcript File (~/.claude/projects/)│ │
│   │ writeQueues (Map) │────►│  {parentUuid, role, content, ...} 追加写    │ │
│   │ 100ms batch flush │     │  链式结构：支持对话树/分叉                    │ │
│   └──────────────────┘     └─────────────────────────────────────────────┘ │
│            │                                                                │
│            ▼                                                                │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │  restoreSessionStateFromLog() / buildConversationChain()             │ │
│   │  从 JSONL 重建对话树，从最新 leaf 回溯到 root                          │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│   Close: gracefulShutdown() → cleanupRegistry (5s timeout) → process.exit  │
│   语义：进程退出，内存状态自然释放                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 关键模块作用

**AppStateStore** (`src/state/AppStateStore.ts`)
- 进程内的唯一状态中心，以 reactive 方式持有当前 session 的全部上下文：消息列表、任务状态、权限请求、UI 状态等。
- 所有业务逻辑（发送消息、工具调用、AI 响应）都直接读写 AppStateStore，**不经过任何 cache 层**——因为状态本身就在内存里。
- 对比我们的架构：这相当于我们把 `SessionContextCache` 提升到"主数据源"的位置，而非 cache。

**sessionState.ts** (`src/utils/sessionState.ts`)
- 轻量级状态机，只跟踪 session 的三种宏观状态：`idle` | `running` | `requires_action`。
- 不持有消息内容，只控制交互流程（比如 `requires_action` 时阻断新的用户输入）。
- 对比我们的架构：类似 `RunsRegistry` 的 RUNNING/CANCELLED 状态，但粒度更粗。

**sessionStorage.ts** (`src/utils/sessionStorage.ts`)
- 持久化层，负责把 AppStateStore 中的变更异步写入 JSONL 文件。
- 使用 `writeQueues: Map<string, Array<...>>` 按 session 隔离写队列，默认 100ms 批量 flush，远程模式压缩到 10ms。
- **关键设计**：写操作是异步后台的，业务逻辑写完 AppStateStore 就认为"已持久化"，不等待磁盘 I/O。
- 对比我们的架构：类似 `SessionManager` 的 `append_turn_message()`，但我们是同步 SQLite 写入。

**JSONL Transcript File**
- 每条消息是一个 JSON 行，包含 `parentUuid` 字段指向父消息，形成**链式结构**。
- 这条链支持从任意节点回溯到根，因此可以：
  - 显示对话树（某条消息有多个子回复时）
  - 从中间某条消息"重新生成"（fork 出新的分支）
  - 实现类似 git 的 history 导航
- 对比我们的架构：我们的 entries 表是线性序列，只能顺序 replay，不支持分叉。

**restoreSessionStateFromLog() / buildConversationChain()** (`src/utils/sessionRestore.ts`)
- 启动或恢复时，读取 JSONL 文件，用 `parentUuid` 重建完整的对话树。
- 优化：大文件时使用 `pre-compact skip`，跳过已经被 compact 掉的早期消息，直接从 compact summary 之后开始重建。
- 对比我们的架构：类似 `SessionManager.get_session()`（snapshot + replay events），但 claude-code 是文件顺序读，我们是 SQLite 索引读。

**gracefulShutdown.ts** (`src/utils/gracefulShutdown.ts`)
- 退出时依次调用 `cleanupRegistry` 中的 hook（flush 写队列、保存 analytics、重置终端模式）。
- 总超时 5s，其中 cleanup hook 预算 1.5s，analytics flush 预算 500ms，剩余时间用于终端重置。
- 对比我们的架构：我们的 `:close` 是 session 粒度（archive 一个 session），claude-code 的 shutdown 是进程粒度（退出整个 CLI）。

### 关于 "Cache"

**Claude Code 没有 LRU cache。**

它的架构是"进程内始终持有完整状态"——`AppStateStore` 本身就是主数据源，不是 cache。我们之前对比表中写的 "memoized dedup + metadata cache" 指的是：
- `getSessionMessages()` 在同一轮渲染中做 memoization，防止重复去重计算
- 退出前 `reAppendSessionMetadata()` 把 session 元数据（title、tag 等）刷新到 transcript tail

这些都不构成一个可逐出的 cache 层。`SessionContextCache` 是我们为了弥合"stateless HTTP server"与"stateful CLI 进程"之间的架构差异而**新增**的组件，在 claude-code 架构中没有直接对应物。

---

## Nano-MultiAgent 当前架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Nano-MultiAgent 架构（当前）                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │  AgentRuntime (stateless per-turn)                                   │ │
│   │                                                                      │ │
│   │   ┌─────────────────────┐    ┌─────────────────────┐                │ │
│   │   │ SessionContextCache │    │ _session_file_states │                │ │
│   │   │ (设计中: LRU+idle)  │    │ (已有: 文件追踪)      │                │ │
│   │   │ max=200, ttl=30min  │    │                     │                │ │
│   │   └─────────────────────┘    └─────────────────────┘                │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│            │                                                                │
│            │ 每次 run() 调用时:                                             │
│            │   1. cache.get(session_id) → 命中则跳过 SQLite 读              │
│            │   2. 未命中 → list_turn_messages() → SQLite 查询              │
│            │   3. run 结束 → cache.set(session_id, final_history)          │
│            ▼                                                                │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │  SessionManager                                                       │ │
│   │    get_session()     → snapshot + replay events                     │ │
│   │    list_turn_messages() → 处理 compaction 语义                       │ │
│   │    archive_session() → append SESSION_ARCHIVED entry                │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│            │                                                                │
│            ▼                                                                │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │  SQLite (event-sourced)                                               │ │
│   │    entries 表: {entry_id, session_id, kind, data, created_at}       │ │
│   │    追加写，无更新/删除                                                  │ │
│   │    线性序列（无 parentUuid 链）                                        │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│   Close: archive → cancel active run → cache.evict() → SESSION_SHUTDOWN    │
│   语义：封闭入口 + 释放内存缓存 + 通知下游                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 架构对比

| 维度 | Claude Code | Nano-MultiAgent (当前 + 设计) |
|---|---|---|
| **持久化格式** | JSONL 文件（链式，`parentUuid`） | SQLite（事件源，线性序列） |
| **链式结构** | 支持对话树/多分支（parentUuid 回溯） | 线性序列，不支持分叉对话树 |
| **内存持有** | 进程内始终持有完整 `AppState` | stateless，每次 run 重建（+ cache 优化） |
| **Close 语义** | `gracefulShutdown()` → 进程退出，内存自然释放 | `archive()` + `cache.evict()`，进程不退出 |
| **Resume 方式** | 从 JSONL 重建完整对话树（`buildConversationChain`） | SQLite replay 事件（`get_session()`） |
| **Compaction** | 预跳过优化（`pre-compact skip`） | summary entry 替换原始消息 |
| **并发模型** | 单进程单用户（本地 CLI） | 多 session HTTP server（ThreadPool） |
| **缓存层** | 无独立 cache 层（AppStateStore 本身就是主数据源） | `SessionContextCache`（LRU + idle timeout，stateless 架构的补偿） |

---

## 设计决策（已定）

| 问题 | 决策 |
|------|------|
| 持久化格式 | 纯 JSONL，SQLite 完全废弃；不考虑旧数据兼容（开发态） |
| 文件位置 | `{workspace_root}/.nano/sessions/{session_id}.jsonl` |
| 链式结构 | 引入 `parent_uuid`；正常对话为线性链，rewind 后形成 DAG |
| 进程内持有 | `AgentRuntime._session_histories: dict[str, list[Message]]`，主数据源，非 cache |
| 逐出策略 | 仅 `:close` 时 evict，无 LRU / idle timeout |
| Close 语义 | cancel run → flush JSONL → evict 内存 → notify；不封闭 session，close 后可继续 resume |
| compact_boundary | 保留，用于大文件跳读优化；compaction 不修改已写 JSONL 行 |
| Rewind 触发机制 | 本 feature 不实现（数据结构支持 DAG，UI 触发留后续） |
| system_prompt 存储 | 存模板字符串到 `session_created` 行；渲染结果不存（每次 turn 动态 build） |
| RUN_STATUS | 不写 JSONL，运行时内存持有足够 |
| gitBranch | 不写（无 git 感知，无 session listing UI） |
| Session listing | 文件系统扫描 + mtime 排序，读首行取 config |
| 异步写 | background thread + queue.Queue |
| is_meta / is_compact_summary | 两者都要；存于 Message.metadata dict，JSONL 序列化时展平到顶层 |
| session config 中途变更 | `config_update` 元数据行追加到 JSONL；`PUT /v1/sessions/{id}/config` 触发 |

详见 `design.md`。
