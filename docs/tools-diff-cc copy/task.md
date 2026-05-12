# nano-multiagent `task` vs claude-code `AgentTool` 对比分析

## 1. Interface & Schema（接口与参数）

### nano-multiagent `task`
- **参数结构**：基于手写 JSON Schema（`input_schema`），无运行时类型校验库
- **必填字段**：`load_skills`, `description`, `prompt`
- **可选字段**：`run_in_background`（默认阻塞），`session_id`（续会话），`category` / `subagent_type`（二选一，新建任务时必填）
- **核心字段**：
  - `load_skills`：字符串数组，必须至少传一个 skill 名（可传 `[]`）
  - `category` / `subagent_type`：二选一，用于选择代理类型（续会话时可选）
  - `session_id`：用于续会话，保留完整上下文
  - `command`：触发该 task 的命令（可选，用于 slash command 追踪）
  - `idempotency_key`：幂等键，缓存结果
  - `timeout_seconds`：超时时间，默认 30 秒
- **模式**：`run_in_background` 为 `true` 时非阻塞，否则阻塞

### claude-code `AgentTool`
- **参数结构**：使用 Zod（`z.object`）做懒加载 schema（`lazySchema`），带完整类型推导
- **必填字段**：`description`, `prompt`
- **核心字段**：
  - `subagent_type`：选择预定义代理类型；在 fork 实验开启时可省略
  - `model`：可选模型覆盖（`'sonnet' | 'opus' | 'haiku'`）
  - `run_in_background`：是否后台运行（可选布尔值）
  - `name` / `team_name` / `mode`：多代理团队相关参数
  - `isolation`：隔离模式，`'worktree'` 或 `'remote'`（Ant 内部）
  - `cwd`：覆盖工作目录（与 `isolation: worktree` 互斥）
- **动态裁剪**：根据 feature gate（如 `KAIROS`、`FORK_SUBAGENT`）动态 `.omit()` 字段，避免模型看到未启用参数

### 关键差异
- nano-multiagent 强制要求 `load_skills`，claude-code 无此概念，工具池由运行时根据权限上下文自动组装
- claude-code 支持更丰富的调度语义：团队名、隔离模式、远程执行、模型覆盖
- claude-code 用 Zod 做 schema 定义和类型安全，nano-multiagent 是手写 JSON Schema

---

## 2. Core Implementation Details（核心实现）

### nano-multiagent `task`
- **执行模型**：单文件 Python 类 `TaskTool`，内部维护一个 `ThreadPoolExecutor(max_workers=4)`
- **阻塞模式**（`_run_blocking`）：
  - 向线程池提交 `_execute_turn`，调用 `future.result(timeout=timeout_seconds)` 等待
  - 超时返回字符串形式的错误信息（非异常抛出）
- **非阻塞模式**（`_run_non_blocking`）：
  - 同样提交线程池，但立即返回 receipt（含 `task_id`）
  - 后台 worker（`_run_non_blocking_worker`）在完成后把结果写入 `_task_results` 字典
- **续会话**：
  - 通过 `session_id` 调用 `runtime.continue_turn()` 或 `runtime.run()`
  - 若 `session_id` 不存在且未提供 `prompt`，则报错
- **上下文继承**：子会话元数据仅继承 `workspace_root`（来自 `ctx.cwd`）

### claude-code `AgentTool`
- **执行模型**：React/TypeScript 生态中的 `buildTool` 工具定义，核心逻辑分散在多个文件中
- **runAgent.ts**：子代理的实际执行器，返回 `AsyncGenerator<Message, void>`
  - 支持消息 fork（`forkContextMessages`）以共享父上下文
  - 处理 MCP 服务器初始化与清理
  - 处理 skill 预加载、frontmatter hooks、SubagentStart hooks
  - 构建子代理专属的 `ToolUseContext`（`createSubagentContext`）
- **AgentTool.tsx**：调度入口，负责：
  - 解析代理定义（内置 / 插件 / fork）
  - 处理 worktree / remote / cwd 隔离
  - 区分 sync（阻塞）与 async（后台）路径
  - sync 路径支持“运行中转后台”（foreground → background）的竞态机制
- **forkSubagent.ts**：
  - 当 `subagent_type` 省略且 feature gate 开启时，走 fork 路径
  - 子代理继承父代理的完整对话历史 + 系统提示词
  - 通过 `buildForkedMessages()` 构造占位 tool_result + 子指令，最大化 prompt cache 命中
- **resumeAgent.ts**：
  - 从磁盘读取子代理的 transcript 和 metadata
  - 恢复 worktree、替换状态（`contentReplacementState`）
  - 支持 fork 子代理的恢复（需重建父系统提示词）

### 关键差异
- nano-multiagent 用线程池做简单同步/异步切换；claude-code 用 AsyncGenerator 实现流式、可中断、可前台转后台的复杂生命周期
- claude-code 的 fork 机制是 nano-multiagent 所没有的：它让子代理共享父代理的 prompt cache，显著降低 token 成本
- claude-code 的 sync 代理可在运行中被用户手动转为 background；nano-multiagent 一旦启动模式即固定

---

## 3. Runtime Integration（运行时集成）

### nano-multiagent `task`
- 通过 `TaskRuntime` Protocol 与运行时解耦：
  - `create_session(title, metadata)` → 创建子会话
  - `run(session_id, parts, stream, llm_session_id)` → 执行一轮
  - `continue_turn(session_id, stream, llm_session_id)` → 无新用户输入继续一轮
- 工具本身不直接操作主循环状态，仅返回字符串结果
- 子代理的 `llm_session_id` 与父会话关联，用于 LLM 层面的 session 追踪

### claude-code `AgentTool`
- 深度集成 React 应用状态（`AppState`）和 `ToolUseContext`
- 通过 `rootSetAppState` 注册/更新后台任务状态（`tasks` 字典）
- 使用 `query()` 函数直接驱动 LLM 主循环，子代理与父代理共享同一套消息流基础设施
- 子代理的权限模式、MCP 客户端、工具池、思考配置均可独立覆盖
- 通过 `runWithAgentContext` 设置异步本地存储（ALS）上下文，用于遥测、工作负载追踪和 analytics 归因
- 前台代理支持 `setToolJSX` 渲染进度 UI（如 `BackgroundHint`）

### 关键差异
- nano-multiagent 的集成是“协议边界”式的，较薄；claude-code 是“状态深度共享”式的，较厚
- claude-code 子代理可以修改父应用状态（如任务列表、进度摘要、代理名称注册表），nano-multiagent 无此能力
- claude-code 的 UI 层能实时渲染子代理进度，nano-multiagent 仅返回文本 receipt

---

## 4. Error Handling（错误处理）

### nano-multiagent `task`
- 参数校验失败：抛出 `ToolError`（带 `tool_name` 和 `details`）
- 运行时未绑定：抛出 `ToolError("task runtime is not configured")`
- 阻塞模式超时：`FutureTimeoutError` → 返回字符串格式的 `_error_message`（不抛异常）
- 阻塞模式其他异常：捕获所有 `Exception` → 返回字符串错误信息
- 非阻塞模式异常：写入 `_task_results[task_id]`，不通知调用者
- **特点**：很多错误被“吞掉”并转化为工具返回的文本，主循环不会收到异常

### claude-code `AgentTool`
- 参数/代理查找失败：直接 `throw new Error(...)`，由工具框架捕获并渲染为 tool_result 错误块
- 权限拒绝：通过 `checkPermissions` 返回 `PermissionResult`，在 `auto` 模式下走分类器
- 同步代理异常：
  - `AbortError`：重新抛出，由外层主循环处理中断
  - 其他错误：记录日志，若已收集到 assistant 消息则尝试 `finalizeAgentTool` 返回部分结果；否则重新抛出
- 后台代理异常：由 `runAsyncAgentLifecycle` 统一捕获，区分 `AbortError`（用户终止）、普通错误，更新任务状态并发送通知
- MCP 连接失败：记录 warn 日志，跳过该服务器，不影响其他工具
- **特点**：错误分层清晰，同步路径保留“部分结果回退”机制，后台路径有状态机（completed / killed / failed）

### 关键差异
- nano-multiagent 倾向于把错误变成字符串返回值，可能让主代理误判为正常结果
- claude-code 区分“可恢复的部分结果”和“致命错误”，且后台任务有完整的生命周期状态通知

---

## 5. Output Format / Return Value Structure（输出格式）

### nano-multiagent `task`
- **`run()` 返回结构化 dict**：所有路径均返回带 `status` 字段的字典，不再是纯文本字符串
  - **阻塞成功**：`{"status": "completed", "content": ..., "sessionId": ..., "durationMs": ..., "agent": ..., "continuation": ..., "taskId": ...}`
  - **阻塞失败/超时**：`{"status": "failed", "title": ..., "error": ..., "sessionId": ..., "agent": ...}`
  - **非阻塞启动**：`{"status": "async_launched", "taskId": ..., "sessionId": ..., "description": ..., "agent": ..., "continuation": ...}`
  - **非阻塞结果**：后台 worker 完成后写入 `_task_results`，格式与阻塞成功/失败相同
- **`serialize_result()` 按状态分支渲染**：接收 `output` 和可选 `error` 参数
  - `error is not None`：错误信息直通返回
  - `status == "completed"`：调用 `_format_completed`，输出含耗时、代理名、content、`session_id`、`task_id`
  - `status == "async_launched"`：调用 `_format_async_launched`，输出 receipt 含 `task_id`、描述、代理名、状态、后续指引
  - `status == "failed"`：调用 `_format_failed`，输出错误标题、错误信息、`session_id`
  - 非 Mapping / 无 recognized status：回退到 `json_serialize`
- **零输出保护**：`_format_completed` 在 content 为空时替换为 `(Subagent completed but returned no output.)`
- **session_id 显性化**：每次返回都给出 `session_id` 和续会话方式（`use task with session_id='...' to continue`）

### claude-code `AgentTool`
- **schema 化输出**：定义了 `agentToolResultSchema`（Zod），包含：
  - `agentId`, `agentType?`
  - `content`: `{ type: 'text', text: string }[]`
  - `totalToolUseCount`, `totalDurationMs`, `totalTokens`
  - `usage`: 详细的 token 统计（含 cache、server tool use、service tier）
- **sync 完成**：返回 `{ status: 'completed', prompt, ...agentResult, ...worktreeResult }`
- **async 启动**：返回 `{ status: 'async_launched', agentId, description, prompt, outputFile, canReadOutputFile }`
- **teammate 启动**：返回 `{ status: 'teammate_spawned', ... }`
- **remote 启动**：返回 `{ status: 'remote_launched', taskId, sessionUrl, ... }`
- **mapToolResultToToolResultBlockParam**：将结构化数据渲染为 LLM 可见的 `tool_result` 文本块，例如：
  - async 启动时提示 `agentId: xxx (use SendMessage with to: 'xxx' to continue)`
  - completed 时追加 `<usage>` 统计块
  - one-shot 内置代理（Explore/Plan）会省略 usage 块以节省 token

### `serialize_result` / `mapToolResultToToolResultBlockParam` 对比

这是工具业务结果 → LLM 可见 `tool_result` 的**转换层**。

#### nano-multiagent (`serialize_result`)
```python
def serialize_result(self, output: Any, error: str | None = None) -> str:
    if error is not None:
        return error
    if not isinstance(output, Mapping):
        if isinstance(output, str):
            return output
        return json_serialize(output)

    status = output.get("status")
    if status == "completed":
        return self._format_completed(output)
    if status == "async_launched":
        return self._format_async_launched(output)
    if status == "failed":
        return self._format_failed(output)
    return json_serialize(output)
```
- **结构化输入**：`run()` 返回 dict 带 `status` 字段，`serialize_result` 按状态分支调用对应格式化方法
- **错误直通**：通过 `error` 参数传入的错误直接返回，不经过状态分支
- **模型看到的**：精简自然语言文本（含耗时、代理名、content、`session_id`、`task_id`），不再是大段 JSON 或原始字符串
- **零输出保护**：子代理无输出时返回 `(Subagent completed but returned no output.)`，防止模型误判

#### claude-code (`mapToolResultToToolResultBlockParam`)
```typescript
mapToolResultToToolResultBlockParam(data, toolUseID) {
  // 1. 多代理 spawn
  if (data.status === 'teammate_spawned') {
    return {
      tool_use_id: toolUseID, type: 'tool_result',
      content: [{
        type: 'text',
        text: `Spawned successfully.\nagent_id: ${data.teammate_id}\nname: ${data.name}\nteam_name: ${data.team_name}\nThe agent is now running and will receive instructions via mailbox.`,
      }],
    }
  }

  // 2. 远程代理启动
  if (data.status === 'remote_launched') {
    return {
      tool_use_id: toolUseID, type: 'tool_result',
      content: [{
        type: 'text',
        text: `Remote agent launched in CCR.\ntaskId: ${data.taskId}\nsession_url: ${data.sessionUrl}\noutput_file: ${data.outputFile}\nThe agent is running remotely. You will be notified automatically when it completes.\nBriefly tell the user what you launched and end your response.`,
      }],
    }
  }

  // 3. 异步（后台）启动
  if (data.status === 'async_launched') {
    const prefix = `Async agent launched successfully.\nagentId: ${data.agentId} (internal ID - do not mention to user. Use SendMessage with to: '${data.agentId}' to continue this agent.)\nThe agent is working in the background. You will be notified automatically when it completes.`
    const instructions = data.canReadOutputFile
      ? `Do not duplicate this agent's work — avoid working with the same files or topics it is using. Work on non-overlapping tasks, or briefly tell the user what you launched and end your response.\noutput_file: ${data.outputFile}\nIf asked, you can check progress before completion by using ${FILE_READ_TOOL_NAME} or ${BASH_TOOL_NAME} tail on the output file.`
      : `Briefly tell the user what you launched and end your response. Do not generate any other text — agent results will arrive in a subsequent message.`
    return {
      tool_use_id: toolUseID, type: 'tool_result',
      content: [{ type: 'text', text: `${prefix}\n${instructions}` }],
    }
  }

  // 4. 同步完成
  if (data.status === 'completed') {
    const worktreeInfoText = data.worktreePath
      ? `\nworktreePath: ${data.worktreePath}\nworktreeBranch: ${data.worktreeBranch}`
      : ''
    // 零输出保护：显式提示模型"无输出"，避免模型误以为"无事可做"而直接结束 turn
    const contentOrMarker = data.content.length > 0
      ? data.content
      : [{ type: 'text', text: '(Subagent completed but returned no output.)' }]

    // One-shot 内置代理（Explore/Plan）省略 usage 块节省 token
    if (data.agentType && ONE_SHOT_BUILTIN_AGENT_TYPES.has(data.agentType) && !worktreeInfoText) {
      return { tool_use_id: toolUseID, type: 'tool_result', content: contentOrMarker }
    }

    return {
      tool_use_id: toolUseID, type: 'tool_result',
      content: [
        ...contentOrMarker,
        {
          type: 'text',
          text: `agentId: ${data.agentId} (use SendMessage with to: '${data.agentId}' to continue this agent)${worktreeInfoText}
<usage>total_tokens: ${data.totalTokens}
tool_uses: ${data.totalToolUseCount}
duration_ms: ${data.totalDurationMs}</usage>`,
        },
      ],
    }
  }
}
```
- **按状态分支**：`teammate_spawned` / `remote_launched` / `async_launched` / `completed` 各自有独立的文本模板
- **agentId 显性化**：每次返回都明确告诉模型 agentId 和续会话方式（`SendMessage with to: 'xxx'`）
- **零输出保护**：子代理无输出时返回 `(Subagent completed but returned no output.)`，防止模型直接结束 turn
- **usage 统计**：completed 时追加 `<usage>` 块（但 one-shot 代理省略以省 token）
- **后台任务指引**：明确告诉模型"不要重复工作"、"可以 tail 输出文件查看进度"

### 关键差异
| 维度 | nano-multiagent | claude-code |
|---|---|---|
| 返回形式 | 结构化 dict + `serialize_result` 按状态渲染为文本 | 按 `status` 分支的精心设计的纯文本 |
| agentId 暴露 | `session_id` 和 `task_id` 显式给出，附带续会话指引 | 每次返回都显式给出 agentId，附带续会话指引 |
| 零输出处理 | 已支持（替换为占位文本） | 显式占位文本，防止模型误判 |
| usage 统计 | 无 | `<usage>` 块含 tokens / tool_uses / duration_ms |
| 后台任务指引 | 基础指引（session_id 续会话） | 明确提示模型"不要重复工作"、"如何查进度" |
| one-shot 优化 | 无 | Explore/Plan 等省略 usage 块节省 token |

---

## 6. Edge Cases Handled（边缘情况）

### nano-multiagent `task`
| 场景 | 处理方式 |
|------|----------|
| 幂等键重复 | 直接返回缓存结果（内存级，非持久化） |
| session_id 不存在 | 若提供了 prompt，则创建新会话；否则抛 `ToolError` |
| 未知 skill | 抛 `ToolError`，列出缺失的 skill |
| category 与 subagent_type 同时存在 | 抛 `ToolError` |
| 运行时未绑定 | 抛 `ToolError` |
| timeout_seconds <= 0 | 抛 `ToolError` |
| 后台任务超时 | 在 worker 中通过耗时比较判断，写入错误结果 |

### 未处理的边缘情况
- 后台任务完成后无通知机制，父代理需主动调用其他工具（如 `background_output`）查询
- 无部分结果保留：后台任务若失败，结果仅写入内存字典，丢失风险高
- 无 MCP / 权限模式 / 工作目录隔离等概念

### claude-code `AgentTool`
| 场景 | 处理方式 |
|------|----------|
| 同步代理运行中用户切后台 | `Promise.race` 监听 background signal，优雅切换为 async 生命周期 |
| 同步代理已产出部分结果后报错 | 若有 assistant 消息则 `finalizeAgentTool` 返回部分结果，否则抛异常 |
| fork 子代理递归 fork | `querySource` 或消息扫描双重守卫，直接抛错拒绝 |
| worktree 无变更 | 自动清理 worktree；有变更则保留并返回路径 |
| MCP 服务器未就绪 | 轮询最多 30 秒，超时后检查是否已失败 |
| 恢复时 worktree 已被外部删除 | 通过 `fsp.stat` 检测，回退到父 cwd |
| 恢复时 transcript 包含未解析 tool_use | `filterUnresolvedToolUses` 清洗消息 |
| 后台代理被用户 kill | `AbortError` 捕获，状态置为 `killed`，发送含 partial result 的通知 |
| 分类器标记 handoff 有风险 | 在最终结果前追加 `SECURITY WARNING` 文本 |
| 零输出完成 | 显式替换为 `(Subagent completed but returned no output.)` |
| 远程代理 bundle 失败 | `onBundleFail` 回调捕获并返回具体错误提示 |

---

## 7. Key Differences & What nano-multiagent Could Learn（关键差异与借鉴点）

### 1. 从“字符串返回值”升级到“结构化生命周期”
- **现状**：nano-multiagent 的 `task` 返回大段文本，主代理难以判断是成功、失败还是超时，且 `session_id` 嵌在 XML 中。
- **借鉴**：引入类似 `AgentToolResult` 的结构化返回类型，明确区分 `completed` / `async_launched` / `failed` / `killed`，并在文本渲染层（`mapToolResultToToolResultBlockParam`）与数据结构层分离。

### 2. 引入 Fork 机制以复用 Prompt Cache
- **现状**：nano-multiagent 每次 spawn 都是全新会话，上下文从零开始，token 成本高。
- **借鉴**：当未指定代理类型时，走 fork 路径，让子代理继承父代理的完整对话历史和系统提示词，通过占位 tool_result 最大化 prompt cache 共享。这对高频子代理调用（如探索、验证）能显著降低 token 消耗。

### 3. 支持 Sync → Background 动态切换
- **现状**：`run_in_background` 在调用时即固定，无法中途切换。
- **借鉴**：前台代理运行超过一定时间后，允许用户或系统自动将其转为后台任务（类似 claude-code 的 `registerAgentForeground` + `backgroundSignal`），避免阻塞主循环。

### 4. 强化续会话（Resume）基础设施
- **现状**：`session_id` 续会话仅支持内存中的会话对象，无持久化恢复能力。
- **借鉴**：将子代理 transcript 持久化到磁盘（`recordSidechainTranscript`），并保存 metadata（`agentType`, `worktreePath`, `description`）。支持从磁盘恢复完整上下文、worktree 和替换状态。

### 5. 工具池与权限的精细化控制
- **现状**：`load_skills` 是简单的字符串列表，工具过滤逻辑在工具内部完成。
- **借鉴**：将工具池组装（`assembleToolPool`）和代理级过滤（`resolveAgentTools`）抽离到独立模块，支持：
  - 内置代理 vs 自定义代理的不同禁用列表
  - 异步代理只允许白名单工具
  - 代理定义自己的 `permissionMode`（如 `bubble`, `acceptEdits`, `plan`）
  - 通过 `allowedAgentTypes` 限制可 spawn 的代理类型

### 6. 错误处理：区分“可恢复部分结果”与“致命错误”
- **现状**：阻塞模式超时或异常都被捕获并变成字符串返回，主代理可能误读。
- **借鉴**：同步执行时保留异常抛出通道，但若子代理已产出 assistant 消息，则尝试 finalize 并返回部分结果；后台任务通过状态机（completed / failed / killed）和通知队列明确告知结果。

### 7. 隔离机制（Worktree / Cwd / Remote）
- **现状**：无文件系统隔离概念，子代理与父代理共享同一工作目录。
- **借鉴**：支持 `isolation: 'worktree'` 创建临时 git worktree，支持 `cwd` 覆盖，支持远程代理执行。这对避免并发文件冲突、保证实验安全性非常重要。

### 8. 进度与遥测集成
- **现状**：无进度追踪，无 analytics。
- **借鉴**：在子代理执行过程中实时更新 `ProgressTracker`， emit `task_progress` 事件，记录 `tengu_agent_tool_completed` 等 analytics 事件，并支持 Perfetto trace 注册。

### 9. 去除 `load_skills` 的强制要求
- **现状**：`load_skills` 是必填字段，但很多时候只是传 `[]`。
- **借鉴**：让工具池由运行时根据代理定义和权限上下文自动决定，减少调用者的认知负担。

### 10. 使用 Schema 校验库
- **现状**：手写 JSON Schema，无运行时校验。
- **借鉴**：采用 Zod 等库定义懒加载 schema，既能获得类型安全，也能根据 feature gate 动态裁剪字段，避免模型误用未启用参数。

---

**总结**：claude-code 的 `AgentTool` 是一个面向生产环境、具备完整生命周期管理、状态隔离、缓存优化和丰富调度语义的子代理系统。nano-multiagent 的 `task` 是一个更轻量、协议边界清晰的实现，但在**结构化输出、fork 缓存共享、动态前后台切换、持久化恢复、隔离机制**等方面有较大提升空间。
