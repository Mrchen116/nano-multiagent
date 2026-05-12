# Hooks 系统 —— nano-multiagent vs Claude Code

> 对比维度：hook 事件类型、执行模型、post-sampling hooks、session hooks、隔离语义

---

## 1. 架构概览

### nano-multiagent —— 双轨拦截/观察

```python
# src/agent/core/hooks/
runner.py      # HookRunner：dispatch_intercept() + dispatch_observe()
registry.py    # HookRegistry：按事件名存储 HandlerRegistration
context.py     # HookContext：不可变上下文容器
types.py       # 事件类型枚举
```

**两类 hook**：

1. **Intercept**（拦截）：可改写 payload、可短路（stop）
   - `input`：用户输入预处理（改写 text/images、handled 短路）
   - `before_agent_start`：改写 message/system_prompt
   - `tool_call`：改写 args、block 短路
   - `tool_result`：改写 output/content/error

2. **Observe**（观察）：只读通知，不可改写
   - `session_start`, `session_compact`, `session_shutdown`
   - `agent_start`, `agent_end`
   - `turn_start`, `turn_end`
   - `message_start`, `message_update`, `message_end`
   - `tool_call`, `tool_result`
   - `run_error`, `run_timeout`, `run_abort`

**执行语义**：
- `dispatch_intercept`：串行执行，每个 handler 收到 payload 的独立 copy
- `dispatch_observe`：串行执行，不可改写
- `_execute_handler`：`asyncio.wait_for` 超时保护，超时/错误不中断 dispatch
- 失败隔离：单个 hook 失败只记录 diagnostics，不影响其他 hook

### Claude Code —— 多轨多阶段

**核心文件**：`src/utils/hooks.ts`（~3500 行），`src/utils/hooks/postSamplingHooks.ts`，`src/utils/hooks/sessionHooks.ts`

**Hook 类型**：

```typescript
// 6 种 hook 类型
command    // shell 命令
prompt     // 提示注入
agent      // agent 执行
http       // HTTP 端点
callback   // 回调注册
function   // 函数注册（内部）
```

**Hook 事件（丰富得多）**：

```typescript
PreToolUse           // 工具调用前
PostToolUse          // 工具调用后
PostToolUseFailure   // 工具调用失败
PermissionDenied     // 权限被拒绝
SessionStart         // 会话开始
SessionEnd           // 会话结束
SubagentStart        // 子 agent 开始
SubagentStop         // 子 agent 停止
TeammateIdle         // 队友空闲
TaskCreated          // 任务创建
TaskCompleted        // 任务完成
ConfigChange         // 配置变更
CwdChanged           // 工作目录变更
FileChanged          // 文件变更
InstructionsLoaded   // 指令加载
UserPromptSubmit     // 用户提交
PermissionRequest    // 权限请求
Elicitation          // 引导提问
ElicitationResult    // 引导结果
Stop                 // 停止
StopFailure          // 停止失败
```

**执行模型**：

```typescript
// executeHooks() 是 async generator，支持并行执行
async function* executeHooks(hooks, event, context)
```

- 匹配的 hooks **并行**执行（`Promise.all`）
- 通过 async generator yield 中间结果
- JSON protocol：exit code 0=success, 2=blocking error, other=non-blocking error
- `hookJSONOutputSchema` 规范输出格式

---

## 2. Post-Sampling Hooks

### Claude Code —— 内部后采样钩子

```ts
// src/utils/hooks/postSamplingHooks.ts
registerPostSamplingHook(definition)
executePostSamplingHooks(messages, toolUses)
```

- 在模型采样**之后**执行
- 用于内部功能（不暴露给用户）
- 可以修改消息和工具调用
- 类似 "middleware after model output"

### nano-multiagent —— 无

- 无 post-sampling 概念
- 所有 hooks 在采样前或并行执行

**缺陷**：无法对模型输出做后处理修正。

---

## 3. Session Hooks

### Claude Code —— 会话级钩子

```ts
// src/utils/hooks/sessionHooks.ts
getSessionHooks()
getSessionFunctionHooks()
getSessionHookCallback()
clearSessionHooks()
```

- 支持会话级别的 hook 注册和清除
- 函数回调形式的 hook（非外部命令）
- 会话结束时自动清理

### nano-multiagent —— 无

- hooks 是全局注册的，无会话级生命周期
- 无函数回调 hook（只有 Python callable）

---

## 4. Hook 事件丰富度对比

| 事件 | Claude Code | nano-multiagent |
|------|------------|-----------------|
| 输入拦截 | `UserPromptSubmit`, `Elicitation` | `input` |
| 会话生命周期 | `SessionStart`, `SessionEnd` | `session_start`, `session_shutdown` |
| Agent 生命周期 | `SubagentStart`, `SubagentStop`, `TeammateIdle` | 无 |
| 任务生命周期 | `TaskCreated`, `TaskCompleted` | 无 |
| 工具调用前 | `PreToolUse` | `tool_call` (intercept) |
| 工具调用后 | `PostToolUse`, `PostToolUseFailure` | `tool_result` (observe) |
| 权限 | `PermissionDenied`, `PermissionRequest` | 无 |
| 文件变更 | `FileChanged`, `CwdChanged` | 无 |
| 配置变更 | `ConfigChange`, `InstructionsLoaded` | 无 |
| 停止 | `Stop`, `StopFailure` | 无 |
| 消息流 | 无（集成在 UI 层） | `message_start`, `message_update`, `message_end` |
| 运行错误 | 无 | `run_error`, `run_timeout`, `run_abort` |

---

## 5. 执行模型差异

| 特性 | Claude Code | nano-multiagent |
|------|------------|-----------------|
| 执行方式 | 并行（Promise.all） | 串行（for loop） |
| 输出协议 | JSON + exit code | Python return value |
| 超时保护 | 有（外部命令超时） | 有（asyncio.wait_for） |
| 失败隔离 | exit code 语义区分 blocking/non-blocking | 全部记录 diagnostics，dispatch 继续 |
| payload copy | 无（依赖进程隔离） | 有（每个 handler 收到 dict copy） |
| async generator | executeHooks() 是 generator | 普通 async 函数 |
| post-sampling | 有 | 无 |
| session 生命周期 | 有（get/clear session hooks） | 无 |

---

## 6. 关键差距

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| 事件丰富度 | 20+ 事件 | 12 个事件 | 🟡 中 |
| 并行执行 | Promise.all | 串行 | 🟡 中 |
| Post-sampling hooks | 有 | 无 | 🟡 中 |
| Session hooks | 有 | 无 | 🟢 低 |
| Agent/Subagent 事件 | 有 | 无 | 🟡 中 |
| 权限事件 | 有 | 无 | 🟡 中 |
| 文件/配置变更事件 | 有 | 无 | 🟢 低 |
| Elicitation 流程 | 有 | 无 | 🟢 低 |
