# Autocompact 实现对比 —— nano-multiagent vs Claude Code

> 对比边界：仅聚焦 **Autocompact** 的实现细节（压缩 prompt、模型选择、结果处理、触发机制），不包含 Microcompact、Context Collapse 等更宏观的上下文管理机制。

---

## 1. 压缩 Prompt 设计

| 维度 | Claude Code | nano-multiagent |
|------|------------|-----------------|
| **Prompt 长度** | ~300 行，工程级详细英文 prompt | 1 行中文 prompt |
| **章节要求** | 9 个固定章节：Primary Request、Key Technical Concepts、Files & Code、Errors & Fixes、Problem Solving、All User Messages、Pending Tasks、Current Work、Optional Next Step | 6 个固定章节：目标、约束、进展、决策、下一步、关键上下文 |
| **输出格式** | 要求 `<analysis>` 草稿区 + `<summary>` 结构化块；`formatCompactSummary()` 会剥离 `<analysis>` 只保留 `<summary>` | 无结构化输出要求，直接返回纯文本 |
| **工具调用限制** | `NO_TOOLS_PREAMBLE` + `NO_TOOLS_TRAILER` 双重约束，禁止任何 tool call；还有 `createCompactCanUseTool()` 兜底拒绝 | 无工具调用限制 |
| **定制化** | 支持 `customInstructions` 追加额外指令（用户或 hook 提供） | 无自定义指令支持 |

### CC 的 Prompt 文件

`src/services/compact/prompt.ts` 包含三种变体：
- `BASE_COMPACT_PROMPT` — 完整压缩
- `PARTIAL_COMPACT_PROMPT` — 部分压缩（保留前缀）
- `PARTIAL_COMPACT_UP_TO_PROMPT` — 部分压缩（保留后缀）

每种变体都包含：
1. `NO_TOOLS_PREAMBLE` — 强制禁止工具调用
2. `DETAILED_ANALYSIS_INSTRUCTION_*` — 要求按时间线逐条分析
3. 9 个结构化章节要求
4. 完整示例输出格式
5. `NO_TOOLS_TRAILER` — 再次提醒禁止工具调用

### nano 的 Prompt

`src/agent/core/agent/compaction/summarizer.py:8-11`

```python
SUMMARY_SYSTEM_PROMPT = (
    "Summarize conversation context with fixed sections: "
    "目标, 约束, 进展, 决策, 下一步, 关键上下文. Keep it concise."
)
```

只有 system prompt，没有 user prompt 模板。`summarize()` 方法直接把消息拼接成字符串丢给 LLM：

```python
transcript_lines = [
    f"- {message.role}: {message.content}"
    for message in dropped_messages
]
prompt = "Conversation slice:\n" + "\n".join(transcript_lines)
```

---

## 2. 压缩模型 & 成本优化

| 维度 | Claude Code | nano-multiagent |
|------|------------|-----------------|
| **模型选择** | 复用主 loop 模型（Sonnet/Opus），但通过 **forked agent + prompt cache sharing** 大幅降低输入成本（cache hit） | 使用当前模型或配置的 `summary_model` |
| **低成本 fallback** | 无显式低成本模型，但 cache sharing 使输入成本接近零 | 无低成本优化 |
| **输出 token 限制** | `MAX_OUTPUT_TOKENS_FOR_SUMMARY = 20_000`（基于 p99.99 统计为 17,387 tokens） | 无限制 |

### CC 的 Cache Sharing 机制

`src/services/compact/compact.ts:1180-1250`

```ts
const promptCacheSharingEnabled = getFeatureValue_CACHED_MAY_BE_STALE(
  'tengu_compact_cache_prefix',
  true,
)

if (promptCacheSharingEnabled) {
  const result = await runForkedAgent({
    promptMessages: [summaryRequest],
    cacheSafeParams,  // 复用主会话的 cache key
    canUseTool: createCompactCanUseTool(),
    querySource: 'compact',
    forkLabel: 'compact',
    maxTurns: 1,
    skipCacheWrite: true,
  })
}
```

Forked agent 复用主会话的 prompt cache prefix（system prompt、tools、历史消息前缀），使 compact 请求的输入 token 几乎全部为 cache read，成本极低。失败时才 fallback 到常规 streaming 路径。

### nano 的成本问题

`CompactionSummarizer` 直接调用 `llm_client.generate()`，无 cache 复用机制。每次压缩都是全价 API 调用，且使用的可能不是低成本模型。

---

## 3. 压缩结果插入方式

| 维度 | Claude Code | nano-multiagent |
|------|------------|-----------------|
| **插入位置** | User message（`isCompactSummary: true`），前带 "This session is being continued..." 前缀 | System message |
| **边界标记** | `SystemCompactBoundaryMessage`（compact boundary），含 `preCompactTokenCount`、`preCompactDiscoveredTools` 等元数据 | 无显式边界标记 |
| **保留消息** | 支持 `messagesToKeep`（partial compact 时保留最近消息） | 无此机制 |

### CC 的续接指令

`src/services/compact/prompt.ts:358-370`

当 `suppressFollowUpQuestions = true`（autocompact 时）时，会在 summary 后追加：

```
Continue the conversation from where it left off without asking the user any further questions.
Resume directly — do not acknowledge the summary, do not recap what was happening,
do not preface with "I'll continue" or similar.
```

对于 proactive/KAIROS 模式还会额外强调：

```
You are running in autonomous/proactive mode. This is NOT a first wake-up —
you were already working autonomously before compaction.
```

### nano 的结果处理

```python
response = self._llm_client.generate(...)
summary = response.message.content.strip()
return summary or _fallback_summary()
```

直接将 summary 文本返回，由调用方（`CompactionApplier`）插入为 system message。

---

## 4. Post-Compact 状态恢复

CC 在压缩后会重建大量上下文附件，nano 完全没有这些机制。

| 恢复项 | CC 实现 | nano |
|--------|---------|------|
| **最近读取的文件** | `createPostCompactFileAttachments()`（最多 5 个文件，50K token budget，每文件 5K cap） | 无 |
| **技能内容** | `createSkillAttachmentIfNeeded()`（按时间排序，25K budget，每技能 5K cap，头部保留） | 无 |
| **Plan 模式** | `createPlanModeAttachmentIfNeeded()` | 无 |
| **异步 Agent** | `createAsyncAgentAttachmentsIfNeeded()` | 无 |
| **MCP/Deferred 工具** | 重新注入 delta attachments（`getDeferredToolsDeltaAttachment` 等） | 无 |
| **文件状态缓存** | `readFileState.clear()` 后通过附件恢复 | 无 |
| **Session 元数据** | `reAppendSessionMetadata()` 保证 resume 时显示自定义标题 | 无 |
| **Transcript 分段** | `writeSessionTranscriptSegment()`（KAIROS 模式） | 无 |

### CC 的状态恢复流程

`src/services/compact/compact.ts:519-588`

```ts
// 1. 清空缓存
context.readFileState.clear()
context.loadedNestedMemoryPaths?.clear()

// 2. 并行生成附件
const [fileAttachments, asyncAgentAttachments] = await Promise.all([
  createPostCompactFileAttachments(preCompactReadFileState, context, 5),
  createAsyncAgentAttachmentsIfNeeded(context),
])

// 3. 追加 plan、plan mode、skill 附件
// 4. 重新注入工具 delta attachments
// 5. 执行 SessionStart hooks
// 6. 创建 compact boundary + summary messages
```

---

## 5. 触发时机 & 容错

| 维度 | Claude Code | nano-multiagent |
|------|------------|-----------------|
| **自动检测** | 每轮 `queryLoop` 迭代前 `shouldAutoCompact()` | 仅 turn 开始前 `_preflight_compaction()` + 溢出后 `_post_turn_check_overflow()` |
| **阈值计算** | `effectiveWindow - 13K` buffer（`AUTOCOMPACT_BUFFER_TOKENS`），支持 `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` 环境变量覆盖 | 配置的 `CompactionSettings.context_window` + `reserve_tokens` |
| **Circuit Breaker** | 连续 3 次失败后停止（`MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3`），避免对不可恢复的超限上下文反复浪费 API 调用 | 无 |
| **PTL Retry** | `truncateHeadForPTLRetry()` — compact 请求本身超限时自动截断最旧消息重试，最多 3 次 | 无，直接 fallback summary |
| **流式容错** | `MAX_COMPACT_STREAMING_RETRIES = 2` 次重试 | 无 |
| **Session Memory 优先** | `trySessionMemoryCompaction()` 在 legacy compact 之前尝试，可能更轻量 | 无 |

### CC 的触发阈值

`src/services/compact/autoCompact.ts:62-91`

```ts
const AUTOCOMPACT_BUFFER_TOKENS = 13_000
const WARNING_THRESHOLD_BUFFER_TOKENS = 20_000
const ERROR_THRESHOLD_BUFFER_TOKENS = 20_000
const MANUAL_COMPACT_BUFFER_TOKENS = 3_000

export function getAutoCompactThreshold(model: string): number {
  const effectiveContextWindow = getEffectiveContextWindowSize(model)
  return effectiveContextWindow - AUTOCOMPACT_BUFFER_TOKENS
}
```

`getEffectiveContextWindowSize()` 还会预留 `MAX_OUTPUT_TOKENS_FOR_SUMMARY = 20_000` 给 summary 输出。

### CC 的 Query Source 防护

```ts
if (querySource === 'session_memory' || querySource === 'compact') {
  return false  // 避免递归死锁
}
if (feature('CONTEXT_COLLAPSE') && querySource === 'marble_origami') {
  return false  // 避免破坏 ctx-agent 的 committed log
}
if (feature('REACTIVE_COMPACT') && isReactiveOnly()) {
  return false  // reactive-only 模式抑制 proactive compact
}
```

### nano 的触发

`src/agent/core/agent/runtime.py`（推测，基于 `context-management.md` 描述）

```python
# 1. 预检压缩（turn 开始前）
AgentRuntime._preflight_compaction()
  └── should_compact(context_tokens, context_window, reserve_tokens)

# 2. 溢出后压缩（turn 失败后）
AgentRuntime._post_turn_check_overflow()
  └── 检测到 context overflow error → _compact_session()
```

---

## 6. 压缩前预处理

| 预处理 | CC | nano |
|--------|-----|------|
| **图片剥离** | `stripImagesFromMessages()` — 将 image/document 替换为 `[image]`/`[document]` 文本标记 | 无 |
| **附件过滤** | `stripReinjectedAttachments()` — 移除 skill_discovery/skill_listing 等会被重新注入的附件 | 无 |
| **消息分组** | `groupMessagesByApiRound()` — 按 API round 分组，用于 PTL retry 时按组丢弃 | `CompactionPlanner` 保证不分割 tool call/result 对 |

---

## 7. 关键差距总结

| 能力 | Claude Code | nano-multiagent | 严重程度 |
|------|------------|-----------------|---------|
| Prompt 质量 | 工程级 300 行结构化 prompt，9 章节，防工具调用，可定制 | 1 行中文 prompt，6 章节 | 🔴 高 |
| Prompt Cache 复用 | Forked agent 复用主会话 cache，输入成本接近零 | 完全缺失 | 🔴 高 |
| Post-Compact 状态恢复 | 文件、技能、plan、async agent、工具 delta 等全面恢复 | 无 | 🔴 高 |
| 续接指令 | 精确的 "resume directly" 指令，防止模型重复寒暄 | 无 | 🟡 中 |
| PTL Retry | 自动截断最旧消息重试（最多 3 次） | 无 | 🟡 中 |
| Circuit Breaker | 连续 3 次失败后停止，避免浪费 API 调用 | 无 | 🟡 中 |
| 流式重试 | 2 次 streaming retry | 无 | 🟢 低 |
| Session Memory 优先 | `trySessionMemoryCompaction()` 在 legacy 之前尝试 | 无 | 🟢 低 |
| 压缩边界元数据 | `SystemCompactBoundaryMessage` 含 preCompactTokenCount、preCompactDiscoveredTools 等 | 无 | 🟢 低 |
