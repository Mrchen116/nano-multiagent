# Agent 内核功能缺陷总结 —— nano-multiagent vs Claude Code

> 本文档汇总所有模块的对比结果，按严重程度排序，给出修复优先级建议。

---

## 严重程度图例

- 🔴 **高**：严重影响用户体验或功能可用性
- 🟡 **中**：影响效率或功能丰富度
- 🟢 **低**：优化项或锦上添花

---

## 🔴 高优先级缺陷

### 1. 流式处理完全缺失

| 项目 | 说明 |
|------|------|
| **问题** | `stream=False` 硬编码，完全无流式能力 |
| **CC 实现** | AsyncGenerator 全链路流式，6 种事件类型，StreamingToolExecutor |
| **影响** | 大响应无反馈、工具执行延迟、无实时思考展示 |
| **修复建议** | 1) LLM 客户端支持 `stream=True`；2) `AgentLoop` 改为 AsyncGenerator；3) REPL 层消费流式事件；4) 实现 StreamingToolExecutor |
| **关键文件** | `src/agent/platform/llm/providers/anthropic/client.py`, `src/agent/core/agent/loop.py`, `src/coding_cli/render/repl_render.py` |

### 2. Prompt Caching 完全缺失

| 项目 | 说明 |
|------|------|
| **问题** | 无 `cache_control` 实现 |
| **CC 实现** | 自动添加 cache breakpoints，支持 ephemeral/1h/global 策略 |
| **影响** | API 成本高，重复上下文重复计费 |
| **修复建议** | 1) `LLMMessage` 支持 content blocks；2) `AnthropicMapper` 添加 cache_control；3) 自动在消息边界添加 breakpoints；4) 成本追踪增加 cache 分项 |
| **关键文件** | `src/agent/core/llm/interfaces.py`, `src/agent/platform/llm/providers/anthropic/mapper.py`, `src/agent/core/agent/prompting.py` |

### 3. Thinking Mode 缺失

| 项目 | 说明 |
|------|------|
| **问题** | 不支持 Claude extended thinking |
| **CC 实现** | `adaptive` 和 `enabled + budget_tokens` 两种模式 |
| **影响** | 复杂推理任务质量受限 |
| **修复建议** | 1) `LLMGenerateRequest` 增加 thinking 字段；2) `AnthropicMapper` 处理 thinking 参数；3) CLI 增加 `--effort` 参数 |
| **关键文件** | `src/agent/core/llm/interfaces.py`, `src/agent/platform/llm/providers/anthropic/mapper.py`, `src/coding_cli/commands.py` |

### 4. Retry 策略基本缺失

| 项目 | 说明 |
|------|------|
| **问题** | 429/529/500 错误直接失败 |
| **CC 实现** | withRetry：429 退避、529 fallback、500 指数退避 |
| **影响** | 服务波动时用户体验极差 |
| **修复建议** | 1) `AnthropicClient` 增加 withRetry 包装；2) 配置 fallback model；3) 实现退避策略 |
| **关键文件** | `src/agent/platform/llm/providers/anthropic/client.py`, `src/agent/core/llm/factory.py` |

### 5. MCP 集成完全缺失

| 项目 | 说明 |
|------|------|
| **问题** | 无 MCP 服务器支持 |
| **CC 实现** | MCP 工具、资源读取、健康监控、三级配置 |
| **影响** | 工具生态封闭，无法扩展 |
| **修复建议** | 1) 引入 MCP Python SDK；2) 实现 MCPTool；3) 添加 `mcp` CLI 命令；4) 配置解析 |
| **关键文件** | 新增 `src/agent/platform/mcp/` 模块 |

### 6. 工具权限系统缺失

| 项目 | 说明 |
|------|------|
| **问题** | 无权限模式，所有工具默认可用 |
| **CC 实现** | suggestive/auto-edit/auto-everything 三级权限 |
| **影响** | 安全性控制不足，用户无法感知工具调用 |
| **修复建议** | 1) 定义 `PermissionMode` 和 `ToolPermissionContext`；2) 在 `AgentLoop` 前检查 `canUseTool`；3) REPL 层增加权限请求 UI |
| **关键文件** | `src/agent/core/agent/loop.py`, `src/coding_cli/render/repl_render.py` |

### 7. Agent 定义系统缺失

| 项目 | 说明 |
|------|------|
| **问题** | 无 AgentDefinition，无法定义子 agent |
| **CC 实现** | 内置 agents + 文件系统加载 + fork/in-process 执行 |
| **影响** | 无法使用子 agent 分解复杂任务 |
| **修复建议** | 1) 定义 `AgentDefinition` 模型；2) 实现 `AgentTool`；3) 支持 `.claude/agents/` 加载；4) 实现 fork/in-process 执行器 |
| **关键文件** | 新增 `src/agent/core/agents/` 模块 |

### 8. 记忆系统缺失

| 项目 | 说明 |
|------|------|
| **问题** | 无 memdir，跨会话无记忆 |
| **CC 实现** | 用户记忆 + 项目记忆 + 团队记忆 + 自动发现 |
| **影响** | 每次会话都是白板，无法继承偏好 |
| **修复建议** | 1) 创建 `~/.claude/memory/` 和项目级记忆目录；2) 实现记忆扫描和注入；3) 支持记忆读写工具 |
| **关键文件** | 新增 `src/agent/platform/memory/` 模块 |

---

## 🟡 中优先级缺陷

### 9. 模型降级缺失

- 529 过载时无 fallback model 切换
- 修复：配置 fallback model，在 `ModelError` 时切换

### 10. Max Output Tokens 恢复缺失

- 长输出被截断时无法自动恢复
- 修复：检测截断，升级 max_tokens，注入恢复消息

### 11. Autocompact 不够自动

- 仅在 turn 前预检 + 溢出后触发，CC 是每轮迭代前
- 修复：在 `AgentLoop` 每次迭代前检查并触发

### 12. Cost Tracking 不完整

- 无 USD 成本计算、无按模型统计、无 cache 分项
- 修复：增加成本计算、按模型累积、session 恢复

### 13. 快捷键系统缺失

- 无全局快捷键，影响交互效率
- 修复：引入终端键盘事件处理

### 14. @ 提及功能缺失

- 无文件/目录提及补全
- 修复：输入时检测 `@` 并提供补全

### 15. Bundled Skills 缺失

- 无内嵌技能，所有技能必须文件系统
- 修复：实现 `register_bundled_skill` 机制

### 16. Provider 支持不足

- 仅 Anthropic + OpenAI-compat，无 Bedrock/Vertex/Azure
- 修复：增加 provider SDK 或 HTTP 适配器

### 17. 斜杠命令系统薄弱

- 只是文本替换，无法改变模型/工具
- 修复：实现完整 Command 类型系统

### 18. Git Status 注入缺失

- 无 git 状态上下文
- 修复：在 prompt 构建时注入 git status

### 19. CLAUDE.md 自动发现缺失

- 无项目上下文自动加载
- 修复：扫描 `CLAUDE.md` 并注入

### 20. Session Resume 命令缺失

- 无 `-c`/`-r` 命令
- 修复：实现会话列表和恢复

---

## 🟢 低优先级缺陷

### 21. 语音输入缺失
- CC 有完整的 push-to-talk + native audio capture (cpal) + voice_stream STT
- nano 完全无语音能力

### 22. Message Normalization 薄弱
- CC 有复杂多通道归一化（attachment reordering、tool reference stripping、error sanitization、message merging、system reminder smooshing、tool result hoisting）
- nano 基本无，仅简单拼接 LLMMessage

### 23. Tool Result Budget 缺失
- CC 有 `applyToolResultBudget()` 限制 tool result 大小
- nano 无限制，大文件读取可能撑爆 context

### 24. Citations 缺失
- CC 有 API streaming 中的 `citations_delta` 事件（TODO 占位）
- nano 完全无

### 25. Telemetry / OpenTelemetry 缺失
- CC 有完整的 OpenTelemetry spans + instrumentation
- nano 只有基本 console tracer

### 26. Post-sampling Hooks 缺失
- CC 有 `registerPostSamplingHook()` 对模型输出后处理
- nano 无

### 27. Agent Permission Rules 缺失
- CC 有 `filterDeniedAgents()`、`getDenyRuleForAgent()`
- nano 无

### 28. Swarm Coordination 缺失
- CC 有 InProcessBackend、TmuxBackend、ITermBackend 多后端
- nano 无 teammate/swarm 概念

### 29. UI 框架差异
- React/Ink vs Rich，不影响功能核心

### 30. 工具搜索
- Deferred tool discovery

### 31. Advisor 系统
- 内部 beta 功能

### 32. FPS 追踪
- 性能分析

### 33. 非流式降级
- N/A（本来就不支持流式）

### 34. Withheld 消息
- 错误处理优化

### 35. Transition 字段
- 调试便利

### 36. 团队记忆
- 多用户场景

### 37. 技能别名
- 便利性

### 38. 动画效果
- 视觉体验

---

## 修复路线图建议

### Phase 1（核心功能）
1. 流式处理
2. Prompt Caching
3. Retry 策略 + Fallback Model
4. Thinking Mode

### Phase 2（生态扩展）
5. MCP 集成
6. Agent 定义系统
7. 工具权限系统

### Phase 3（体验优化）
8. 记忆系统
9. Cost Tracking 完善
10. UI 增强（快捷键、@提及）

### Phase 4（进阶功能）
11. Skills 系统完善
12. Provider 扩展
13. 其他优化项
