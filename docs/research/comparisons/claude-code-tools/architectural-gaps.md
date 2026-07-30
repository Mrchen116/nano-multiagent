# nano-multiagent vs claude-code：跨工具的共性架构差距

> 本文件汇总 5 个工具对比分析（read / write / edit / bash / task）后发现的**共性问题**——这些问题无法通过逐个工具单点修补解决，而需要在**工具框架层、运行时层或会话层**进行系统性重构。

---

## 1. 缺失统一的 Schema 与类型系统层

### 问题描述
nano-multiagent 的每个工具都使用手写 JSON Schema（Python dict），没有运行时校验库，也没有输出 Schema 定义。这导致：
- 模型可能传入未定义的参数（`additionalProperties: False` 只是静态声明）
- 工具开发者重复手写相似的类型约束
- 输出格式完全由各个工具自行决定，无统一契约
- 无法根据 feature gate 动态裁剪字段

### claude-code 的做法
- 全栈使用 **Zod v4** 定义 `lazySchema`、`strictObject`、输出 Schema（`outputSchema`）
- `semanticBoolean` / `semanticNumber` 等增强 LLM 对语义的理解
- 根据功能开关（如 `FORK_SUBAGENT`）动态 `.omit()` 字段，避免模型看到未启用的参数
- 所有工具输出都经过统一的 `mapToolResultToToolResultBlockParam` 映射为 LLM 可见的文本块

### 架构改造方向
引入一个 **Tool Definition Framework**：
1. 统一的输入/输出 Schema 定义层（推荐 Pydantic 或类似 Zod 的库）
2. 框架级参数校验与错误格式化
3. 输出类型强制契约：每个工具必须返回结构化对象，再由框架层渲染为 LLM 文本
4. 支持基于功能开关的字段动态裁剪

---

## 2. "字符串即结果" vs "结构化生命周期 + 渲染层分离"（部分解决）

### 当前状态：PARTIALLY RESOLVED

**已完成**：
- 全部 5 个内置工具（`read`、`write`、`edit`、`bash`、`task`）的 `run()` 已改为返回结构化 dict，`serialize_result()` 负责渲染为 LLM 文本
- `Tool.serialize_result` 签名从 `-> str` 升级到 `-> str | list[dict[str, Any]]`（`agent/core/tools/base.py`）
- `ReadTool` 支持多模态：图片返回 `[{"type": "text"}, {"type": "image", ...}]`，直接流入 mapper，无需 JSON 往返
- `ToolResult.content` 和 `LLMMessage.content` 类型已扩展为接受 `str | list[dict]`
- Anthropic 和 OpenAI mapper 均已支持 `str | list` 的 `_map_tool_result_content`
- `task` 工具已区分 `completed` / `async_launched` / `failed` 三种状态，并在 `serialize_result` 中按状态分支渲染

**仍然缺失**：
- 统一的 `ToolResult` Model + Renderer 框架：目前各工具自行实现 `_format_*`，无基类约束
- 错误码体系（`errorCode`）和元数据（`meta`）字段
- 部分结果回退机制（partial result finalize）：同步子代理中途报错时无法返回已收集内容
- 后台任务完整状态机：目前只有 `completed` / `failed` / `async_launched`，缺少 `killed`、进度事件、通知机制
- 无统一的零输出保护、usage 统计、one-shot 优化等策略

### claude-code 的做法
- 每个工具都有强类型的**结构化输出**：`FileEditOutput`、`agentToolResultSchema`、`BashTool` 返回 `{ stdout?, stderr?, backgroundTaskId?, ... }`
- **渲染层独立**：`mapToolResultToToolResultBlockParam` 负责把结构化数据转成对 LLM 友好的文本表示
- 同步子代理支持 "部分结果 finalize"：若已产出 assistant 消息，即使后续报错也能返回已收集内容
- 后台任务有完整的状态机（`completed` / `failed` / `killed` / `async_launched`）

### 架构改造方向
继续推进 **Tool Result Model + Presentation Layer** 两层架构：
1. 定义统一的 `ToolResult` 基类/协议，明确状态字段（`status`、`content`、`metadata`、`errorCode`）
2. 所有工具只负责生成 `ToolResult`，不直接拼接自然语言字符串
3. 由框架级 `Renderer` 根据结果状态、代理模式、UI 上下文决定如何呈现
4. 补充错误码体系、partial result 协议、后台任务状态机

---

## 3. 安全与权限：从"工具各自为政"到"统一安全栈"

### 问题描述
nano-multiagent 的安全逻辑分散且不一致：
- Bash：前缀白名单 + 按 `&&` 拆分，无 AST 分析
- Read/Write/Edit：仅依赖 `ctx.safety.resolve_path()`，但无设备文件黑名单、无二进制扩展名检查、无 UNC 防护
- Task：无权限模式、无 MCP 隔离
- 各工具错误形式不统一：有的抛 `ToolError`，有的返回字符串

### claude-code 的做法
构建了一个 **Multi-Layer Security Stack**：
- **Mode Validation**：不同代理模式（`acceptEdits`、`plan`、`bubble`）自动放宽/收紧权限
- **User Rule Engine**：支持 `exact` / `prefix` / `wildcard` 规则，可配置 `allow` / `ask` / `deny`
- **AST Analysis**：tree-sitter 解析 bash，检测命令替换、进程替换、IFS 注入、混淆标志等 20+ 项
- **Path Validation**：对 ~30 个常用命令提取路径，分类校验读写权限，阻止危险删除
- **Permission Result 对象**：`{ result, behavior, errorCode, decisionReason, meta }`，上层 UI 可据此弹窗或拒绝

### 架构改造方向
将安全逻辑从各工具中剥离，升级为 **Security Framework**：
1. 统一的输入预处理层（路径展开、环境变量剥离、UNC 延迟检查）
2. 可插拔的校验器管道（Validator Pipeline）：AST、路径、规则引擎、模式权限
3. 统一的 `PermissionResult` 返回契约，支持 `ask` 行为
4. 危险操作分类器（destructive command warning），用于 UI 提示而非直接拦截

---

## 4. 会话级状态管理：缺失 Read-Before-Write 与去重机制

### 问题描述
claude-code 的 `readFileState` 是一个**跨工具的会话级状态机**，但 nano-multiagent 完全没有这一层：
- Edit/Write 覆盖现有文件前无需先 Read，导致模型可能在不知情的情况下覆盖用户最新修改
- 没有 staleness 检查：linter 或用户手动修改文件后，模型编辑会静默覆盖
- 同一轮对话中重复 `read` 同一个文件会造成大量冗余 token
- 无 `file_unchanged` 占位机制

### claude-code 的做法
- **ReadFileState**：跟踪每个文件的最后读取时间戳和内容摘要
- **强制先读**：Edit/Write 覆盖现有文件时，若 `readFileState` 无记录则拒绝（errorCode 6）
- **Staleness 检查**：对比 mtime，Windows 上还做内容回退比对（errorCode 7）
- **去重**：再次读取同一文件时，若 mtime 未变则返回 `file_unchanged`，节省 token

### 架构改造方向
在 **Runtime / Session** 层引入统一的文件状态跟踪器：
1. `SessionFileState`：记录已读文件的内容哈希、时间戳、读取范围
2. 工具框架在 Edit/Write 调用前自动校验 `readFileState`
3. 提供 `file_unchanged` 等标准化占位返回类型
4. 支持 staleness 检测的原子性读取-修改-写入临界区

---

## 5. 错误处理：从单一异常到"结构化校验 + 行为策略"

### 问题描述
nano-multiagent 所有错误都走同一个 `ToolError`，没有错误码，没有行为策略：
- 校验阶段错误和运行时错误没有区分
- 没有 `ask` 机制：遇到边界情况只能直接拒绝或静默吞掉错误
- Task 工具甚至把超时和异常都变成字符串返回，主代理可能误判为正常结果

### claude-code 的做法
- **校验阶段**：返回 `{ result: false, behavior: 'ask'|'deny', message, errorCode, meta }`
- **运行时阶段**：使用专用 Error 子类（`FileTooLargeError`、`MaxFileReadTokenExceededError` 等）
- **部分结果回退**：同步子代理运行时，若已收集 assistant 消息则尝试 `finalizeAgentTool`
- **后台任务状态机**：明确区分 `AbortError`（用户 kill）、普通错误、超时

### 架构改造方向
重构 **Error Framework**：
1. 将"输入校验错误"与"运行时错误"分离
2. 引入错误码体系（errorCode）和元数据（meta）
3. 支持 `behavior: 'ask'`，允许框架在拒绝前弹出确认层
4. 定义 `PartialResult` 协议，支持"已产出的部分内容 + 最终错误"的组合返回

---

## 6. 事件流与生命周期：缺失统一的 Async + Background 基础设施

### 问题描述
nano-multiagent 各工具的生命周期管理非常原始：
- Bash：阻塞式 `subprocess.Popen`，超时用 `threading.Timer`
- Task：线程池 `Future.result()`，后台任务只写内存字典，无通知机制
- 无统一的进度事件流、无前台转后台的动态切换、无 `AbortSignal`

### claude-code 的做法
- 核心执行层基于 **AsyncGenerator**：`runShellCommand()`、`runAgent.ts` 都返回 `AsyncGenerator<Message, void>`
- **前台转后台竞态**：同步代理运行中，用户可手动切后台，`Promise.race` 监听 `backgroundSignal`
- **AbortSignal**：大文件读取、子代理执行都支持取消信号
- **UI 进度渲染**：通过 `setToolJSX` 和 `ProgressTracker` 实时渲染子代理进度

### 架构改造方向
将运行时升级为 **Streaming Runtime**：
1. 所有耗时工具的执行入口统一返回 `AsyncIterator` / `AsyncGenerator`
2. 框架提供 `backgroundSignal` 和 `AbortController` 基础设施
3. 定义 `Task` / `BackgroundTask` 状态机，支持前台运行中途转后台
4. 工具通过标准事件总线（如 `task_progress`、`tool_output_chunk`）上报进度

---

## 7. 工具池组装与上下文继承：从显式加载到自动解析

### 问题描述
nano-multiagent 的 Task 工具强制要求 `load_skills` 参数，由调用者显式决定子代理可用什么工具。这带来几个问题：
- 认知负担高：很多调用只是传 `[]`
- 无法根据代理类型、权限模式、功能开关自动裁剪工具池
- 没有内置代理（如 Explore/Plan）与自定义代理的差异化工具过滤

### claude-code 的做法
- **自动组装**：`assembleToolPool()` + `resolveAgentTools()` 根据代理定义、权限上下文、MCP 服务器自动构建工具池
- **代理级过滤**：异步代理只允许白名单工具；不同代理类型有不同的禁用列表
- **Fork 机制**：未指定 `subagent_type` 时，子代理继承父代理的完整对话历史和系统提示词，通过占位 `tool_result` 最大化 prompt cache 共享
- **权限模式绑定**：代理可声明 `permissionMode`（`bubble`、`acceptEdits`、`plan`），自动影响工具可用性

### 架构改造方向
建立 **Agent Context & Tool Resolution Framework**：
1. 去除 `load_skills` 的强制要求，改为运行时自动解析
2. 工具池组装逻辑抽离为独立模块，支持基于代理类型、模式、功能开关的过滤
3. 引入 `ForkContext` 机制，让轻量子代理复用父代理的 prompt cache
4. 定义 `AgentDefinition` 协议，内置代理与自定义代理统一注册

---

## 8. 生态系统集成：缺失框架级 Hook 机制

### 问题描述
claude-code 在工具执行后会触发一系列跨工具的生态系统动作，而 nano-multiagent 完全没有框架级 Hook：
- Write/Edit 后：LSP 通知（`didChange` + `didSave`）、VSCode diff 视图更新、文件历史备份、Skill 自动发现
- Bash 后：图片检测、大输出持久化、后台任务注册
- Agent 后：遥测事件（`tengu_agent_tool_completed`）、Perfetto trace 注册、任务状态更新

### 架构改造方向
在工具框架中引入 **Hook System**：
1. `pre_invoke` / `post_invoke` / `on_success` / `on_error` 四个生命周期钩子
2. 插件式注册 LSP、文件历史、遥测、Skill 发现等扩展
3. 大输出、图片、持久化文件等统一走 `ArtifactManager` 管理

---

## 总结：nano-multiagent 若要追赶，最优先的 3 个架构投资

| 优先级 | 架构投资 | 影响范围 | 当前状态 | 预期收益 |
|--------|----------|----------|----------|----------|
| **P0** | **统一 Schema + 结构化结果 + 渲染层分离** | 所有工具 | 部分完成：5 个工具 `run()` 已返回结构化 dict，`serialize_result` 已分离，多模态已打通；缺少统一 `ToolResult` Model、Renderer 框架、错误码、partial result | 消除"字符串误读"、统一 LLM 交互契约 |
| **P0** | **Streaming Runtime + Background 任务状态机** | Bash、Task、长耗时工具 | 未开始：Bash 仍用阻塞 `subprocess.Popen`，Task 仍用线程池 `Future.result()`，无前台转后台、无 `AbortSignal` | 支持可中断、可转后台、可渲染进度的现代 Agent 体验 |
| **P1** | **Security Framework + Session File State** | Read/Write/Edit/Bash | 未开始：安全逻辑仍分散在各工具，无会话级文件状态跟踪 | 从生产安全角度堵住数据覆盖、路径越界、命令注入等核心风险 |

> 单点修修补补可以让某个工具更好用，但上述 8 个问题必须在**框架层**一次性解决，否则随着工具数量增加， inconsistencies 会成倍放大。
