# Agent 与子 Agent 系统 —— nano-multiagent vs Claude Code

> 对比维度：Agent 定义、子 Agent 执行、多 Agent 协作、in-process vs fork

---

## 1. Agent 定义

### Claude Code —— AgentDefinition

```ts
// src/Tool.ts / src/tools/AgentTool/
AgentDefinition = {
  name: string
  description: string
  systemPrompt: string
  tools: string[]           // 允许的工具列表
  model?: string            // 专用模型
  thinkingConfig?: ThinkingConfig
  allowedTools?: string[]
  // ...
}
```

Agent 来源：
1. **Built-in Agents**：代码内嵌（`src/tools/AgentTool/builtInAgents.ts`）
2. **文件系统 Agents**：从 `.claude/agents/` 目录加载（`loadAgentsDir.ts`）
3. **动态 Agents**：通过 API/配置创建

Agent 配置存储：
- 用户级：`~/.claude/agents/`
- 项目级：`.claude/agents/`

### nano-multiagent —— 无 Agent 定义系统

- `AgentLoop` 和 `AgentRuntime` 是单 agent 概念
- 无 `AgentDefinition` 类型
- 无 `.claude/agents/` 加载机制
- 产品层有 `local_coding` 和 `personal_assistant` 两个产品，但这是产品配置而非 agent 定义

```python
# src/agent/products/local_coding/profile.py
# src/agent/products/personal_assistant/profile.py
```

这些 profile 定义了产品的系统提示和默认工具，但没有 agent 定义的概念。

**缺陷**：无法定义和使用多个具有不同能力的 agent。

---

## 2. 子 Agent 执行

### Claude Code —— 多种执行模式

#### 2.1 AgentTool

```ts
// src/tools/AgentTool/
AgentTool.execute()
  ├── forkSubagent()      // fork 子进程执行
  ├── runAgent()          // 运行 agent
  └── resumeAgent()       // 恢复 agent
```

#### 2.2 In-Process Runner

```ts
// src/utils/swarm/inProcessRunner.ts
```

同进程内运行子 agent，避免 fork 开销。

#### 2.3 Spawn Multi-Agent

```ts
// src/tools/shared/spawnMultiAgent.ts
```

多 agent 并行执行。

#### 2.4 Worker Agent

```ts
// src/coordinator/workerAgent.ts
```

协调器模式下的 worker agent。

### nano-multiagent —— Task 工具

子 agent 工作通过 `Task` 工具实现：

```python
# src/agent/platform/tools/builtins/task.py
```

- `Task` 工具允许模型创建子任务
- 但这是**工具层**的实现，不是内核层的 agent 系统
- 子任务通过 `AgentTool`（实际上是外部调用）执行
- 无专门的子 agent 生命周期管理

**关键区别**：
- CC 的 agent 是**内核级**概念，有定义、加载、执行、恢复完整生命周期
- Nano 的 task 是**工具级**概念，通过单一工具调用实现

---

## 3. Agent 上下文隔离

### Claude Code

- `context: 'inline' | 'fork'` —— agent 可以在 inline（同上下文）或 fork（隔离上下文）模式下运行
- Fork 模式使用 `worktree` 隔离文件系统状态
- 每个 agent 有自己的工具列表、系统提示、模型配置

### nano-multiagent

- 无 agent 上下文隔离概念
- `Task` 工具创建的子任务共享父 agent 的会话
- 无 worktree 隔离（虽然有 `worktree_runtime.py`，但不是为 agent 隔离设计的）

---

## 4. Agent 恢复

### Claude Code

```ts
// src/tools/AgentTool/resumeAgent.ts
```

- Agent 可以暂停和恢复
- 恢复时重建 agent 的会话状态
- 支持跨会话的 agent 持久化

### nano-multiagent

- 无 agent 恢复机制
- `RunsRegistry` 跟踪运行状态，但不是 agent 级别的恢复

---

## 5. 关键差距总结

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| Agent 定义 | AgentDefinition + 文件系统加载 | 无 | 🔴 高 |
| 内置 Agents | 有 | 无 | 🟡 中 |
| 用户自定义 Agents | `.claude/agents/` 目录 | 无 | 🟡 中 |
| 子 Agent Fork | 有 | 无 | 🔴 高 |
| In-Process Agent | 有 | 无 | 🟡 中 |
| Agent 恢复 | 有 | 无 | 🟡 中 |
| 上下文隔离 | inline/fork + worktree | 无 | 🔴 高 |
| 多 Agent 并行 | spawnMultiAgent | 无 | 🟡 中 |
