# 上下文管理 —— nano-multiagent vs Claude Code

> 对比维度：prompt caching、context compaction、token tracking、context injection

---

## 1. Prompt Caching

### Claude Code —— 完整实现

Prompt Caching 是 CC 降低 API 成本的核心机制。

**缓存策略**（`src/services/api/claude.ts:333-502`）：

```ts
// 默认 ephemeral，5 分钟 TTL
cache_control: { type: 'ephemeral' }
// 订阅用户/Ant 内部，1 小时 TTL
cache_control: { type: 'ephemeral', ttl: '1h' }
// 跨会话共享（无 MCP 工具时）
cache_control: { type: 'ephemeral', scope: 'global' }
```

**自动添加缓存断点**：

```ts
// userMessageToMessageParam / assistantMessageToMessageParam
// 最后一个 content block 添加 cache_control
addCacheBreakpoints(messagesForAPI, ...)
```

**禁用条件**：
- `DISABLE_PROMPT_CACHING` 环境变量
- `DISABLE_PROMPT_CACHING_HAIKU`（仅 Haiku）
- `DISABLE_PROMPT_CACHING_SONNET`（仅 Sonnet）

**成本追踪**：分开统计 `cache_read_input_tokens` 和 `cache_creation_input_tokens`（`src/cost-tracker.ts`）

### nano-multiagent —— 完全缺失

- `LLMGenerateRequest` 无 cache 相关字段
- `AnthropicClient` 的 HTTP 请求不设置 `cache_control`
- `LLMMessage` 的 `content: str | list[dict[str, Any]]` 理论上可以支持，但没有任何地方构建带 cache 标记的 content blocks
- 成本追踪只有 `TokenUsage(prompt_tokens, completion_tokens, total_tokens)`，无 cache 分项

**缺陷**：
1. 每次请求都要重新计费系统提示和历史消息
2. 在同一会话的多次 turn 中，大量 token 被重复计费
3. 长会话成本呈线性增长，而非利用 cache 后的次线性增长

---

## 2. Context Compaction

### Claude Code —— 多层压缩

CC 有 3 层压缩机制（后两层被 feature flag 关闭，但架构存在）：

#### 2.1 Autocompact（实际启用）

```ts
// src/query.ts:454-543
autocompact 流程:
  ├── 检查 token 数量是否超过阈值
  ├── 超过 → 调用 compact API（用 Haiku 总结历史）
  │   ├── yield compactBoundaryMessage  ← 标记压缩边界
  │   └── 更新 messages 为压缩后的版本
  └── 未超过 → 继续
```

- 在 `queryLoop()` 每次迭代开头执行
- 使用 Haiku 模型进行总结（低成本）
- yield `compact_boundary` 消息给 UI/SDK
- 被压缩的旧消息从 context 中移除

#### 2.2 Microcompact（feature flag 关闭）

更细粒度的压缩，在 autocompact 之前执行。

#### 2.3 Context Collapse（feature flag 关闭）

上下文折叠，drain 旧消息。

### nano-multiagent —— 单层压缩

**三层触发时机**：

```python
# 1. 预检压缩（turn 开始前）
AgentRuntime._preflight_compaction()
  └── should_compact(context_tokens, context_window, reserve_tokens)

# 2. 溢出后压缩（turn 失败后）
AgentRuntime._post_turn_check_overflow()
  └── 检测到 context overflow error → _compact_session()

# 3. 手动压缩
AgentRuntime.compact(session_id)
```

**压缩实现**：

```python
# CompactionPlanner.plan() —— 选择安全切点
# CompactionSummarizer.summarize() —— LLM 生成总结
# CompactionApplier.apply() —— 应用压缩到 session
```

- `CompactionPlanner` 保证不分割 tool call/result 对
- `CompactionSummarizer` 用固定 system prompt 生成中文总结
- 被压缩的历史替换为一条 system message 插入 context
- **不自动**：仅在预检触发阈值、手动调用、或溢出后触发

**与 CC 的差异**：

| 特性 | Claude Code | nano-multiagent |
|------|------------|-----------------|
| 自动触发 | 每轮迭代前自动检测 | 仅 turn 开始前预检 + 溢出后 |
| 压缩模型 | Haiku（低成本） | 使用当前模型或配置的 summary_model |
| 压缩边界标记 | yield compact_boundary 事件 | 插入 system message 到 history |
| 旧消息 GC | QueryEngine 在 compact_boundary 后释放 | SessionManager 保留所有 events |
| 微压缩 | 有（feature flag） | 无 |
| 上下文折叠 | 有（feature flag） | 无 |

**缺陷**：
1. 无每轮自动检测，容易在 turn 中间超出 context window
2. 压缩使用当前模型而非低成本模型，成本高
3. 无微压缩和上下文折叠等细粒度机制

---

## 3. Token Tracking & Context Window

### Claude Code

**Token 计数**：
- 使用 SDK 返回的 `usage` 字段（`message_start`, `message_delta` 事件中获取）
- 精确的 prompt/completion/cache read/cache creation 统计

**Context Window 管理**：
- `getContextWindowForModel(model, betas)` —— 按模型获取上下文窗口大小
- `getModelMaxOutputTokens(model)` —— 按模型获取最大输出 token
- 在 `paramsFromContext()` 中动态设置 `max_tokens`

**Task Budget**：
- `taskBudget: { total: number; remaining?: number }`
- 在 API 请求参数中传递

### nano-multiagent

**Token 计数**：
- `TokenUsage(prompt_tokens, completion_tokens, total_tokens)`
- 仅在 `LLMGenerateResponse.usage` 中返回
- 无 cache 分项

**Context Window 管理**：
- `CompactionSettings.context_window` —— 配置项
- `_estimate_context_tokens()` —— 简单估算（字符数/8）
- 无按模型的动态窗口管理
- 无 `max_tokens` 配置（`LLMGenerateRequest.max_tokens` 存在但可能未充分利用）

**缺陷**：
1. 无精确的按模型上下文窗口管理
2. token 估算粗糙（字符/8），可能不准确
3. 无 task budget 限制
4. 无 max_tokens 动态配置

---

## 4. Context Injection

### Claude Code

三层上下文注入：

```ts
// 1. System Context（git 状态等）
getSystemContext() → { gitStatus, cacheBreaker }
// 2. User Context（CLAUDE.md 等）
getUserContext() → { claudeMd, currentDate }
// 3. 系统提示注入
buildEffectiveSystemPrompt() → 合并 systemPrompt + systemContext
```

- `getSystemContext` 和 `getUserContext` 都是 `memoize` 缓存的
- 用户上下文通过 `prependUserContext(messagesForQuery, userContext)` 注入到消息数组最前面
- 支持 `systemPromptInjection`（cache breaker）

### nano-multiagent

通过 prompt 模板中的占位符注入：

```python
# src/agent/core/agent/prompting.py
LOCAL_CODING_SYSTEM_PROMPT = """
Available tools: <RUNTIME_FILL:AVAILABLE_TOOLS>
<RUNTIME_FILL:SKILLS_SECTION>
Current date and time: <RUNTIME_FILL:CURRENT_DATETIME>
Current working directory: <RUNTIME_FILL:CURRENT_WORKING_DIRECTORY>
"""
```

- `_fill_runtime_placeholders()` 做简单的字符串替换
- 无 `memoize` 缓存
- 无 git status 注入
- 无 CLAUDE.md 自动发现
- `current_datetime` 可以配置为固定值（用于测试）

**缺陷**：
1. 无 git 状态上下文
2. 无 CLAUDE.md 自动发现和注入
3. 无缓存，每次 turn 都重新构建
4. 上下文信息较单薄

---

## 5. 关键差距总结

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| Prompt Caching | 完整实现，自动断点，多 TTL 策略 | 完全缺失 | 🔴 高 |
| Autocompact | 每轮自动检测，Haiku 总结 | turn 前预检 + 溢出后 | 🟡 中 |
| Microcompact | 有（架构存在） | 无 | 🟢 低 |
| Context Collapse | 有（架构存在） | 无 | 🟢 低 |
| Token 精确统计 | SDK 精确返回 | 仅基本三项 | 🟡 中 |
| Cache 成本分项 | read/write 分开统计 | 无 | 🟡 中 |
| 按模型窗口管理 | 动态获取 | 配置项 | 🟡 中 |
| Task Budget | 有 | 无 | 🟢 低 |
| Git Status 注入 | 有 | 无 | 🟡 中 |
| CLAUDE.md 注入 | 有 | 无 | 🟡 中 |
