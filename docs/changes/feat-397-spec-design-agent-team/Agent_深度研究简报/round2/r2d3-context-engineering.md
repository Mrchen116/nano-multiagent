# R2D3：Context Engineering——长规划链的非 ML drift 防控与 context 管理

> **调研维度**：P0-3，context engineering  
> **来源优先级**：一手工程源码 > 生产 postmortem > 工程博客 > arXiv  
> **黑盒约束**：纯文本进文本出，零 logit 访问，零训练  
> **完成日期**：2026-06-04

---

## 0. 核心结论（先读）

**防 drift / 控 context 的工程主流做法是四层叠加，不是单一技术。** 按重要性排序：

1. **结构化 artifact（文件即记忆）** — spec/design 写成文件，每次 agent turn 重新读入，而非靠 token 历史传递意图。这是防 drift 最廉价、最 SHIPPED 的手段。
2. **Compaction/Summary** — 超过 context 阈值时用专用 agent 将历史对话压缩为结构化摘要，保留 intent + key decisions，丢弃执行细节。Claude Code 有完整生产实现可直接参考。
3. **Sub-agent 隔离（独立 context 窗口）** — 每个 worker/reviewer 从干净 context 启动，只注入它需要的 artifact，防止上游噪声污染下游推理。
4. **Constitution/Rules 按需加载** — CLAUDE.md / AGENTS.md 类文件在 system prompt 固定位置注入，优先级稳定；不在历史消息里"聊"规则。

黑盒 **CAN**（纯 prompt 工程可做）：所有四层均可落地。  
黑盒 **CANNOT**：logit-based context collapse 检测（需 token probability）、基于熵的自动 truncation 策略（需解码层访问）。

---

## 1. Compaction / Summary：主流 harness 的实现方式

### 1.1 Claude Code 的 Compaction 实现（🟢 SHIPPED · Anthropic 生产）

**一手证据来源**：`~/Repos/opensource-hub/claude-code/src/services/compact/`

Claude Code 的 compaction 是目前最完整的公开生产实现，包含以下关键工程决策，每一条都有源码支撑：

#### （1）触发机制：阈值驱动 + 响应式双路

```
autoCompact.ts:
  getAutoCompactThreshold(model) = effectiveContextWindow - autocompactBuffer
  
  buffer 按 context 窗口大小分级：
    >= 800K token 窗口 → 预留 50K buffer
    >= 400K           → 预留 30K buffer
    其他              → 预留 13K buffer
  
  此外还保留 20K 给 output（p99.99 摘要输出 = 17,387 tokens）
```

**设计理由**：预留 buffer 而非 "满了才压" 是为了给当前 turn 的工具调用结果留空间（grep/bash 单次结果可达 20K tokens）。单 turn 增长估算 = `maxOutput + 15K（工具结果增量）`。

**响应式兜底**（`reactiveCompact.ts`）：当 API 返回 `prompt_too_long` 错误时，即使未触发主动 compact 阈值，也立即执行 reactive compact。这是防止 agent 彻底卡死的最后防线。

#### （2）Compaction prompt：结构化 9 节摘要

`compact/prompt.ts` 的 `BASE_COMPACT_PROMPT` 要求输出 9 个固定节：

```
1. Primary Request and Intent（用户意图，关键防 drift 段）
2. Key Technical Concepts
3. Files and Code Sections（含完整代码片段）
4. Errors and fixes
5. Problem Solving
6. All user messages（**所有用户消息原文**，防止意图稀释）
7. Pending Tasks
8. Current Work
9. Optional Next Step（直接引用最近对话原文，防止 task 解读漂移）
```

关键设计：**节 6 要求列出所有用户消息原文**，这是防 intent drift 的直接手段——不是 agent 对意图的"理解"，而是原话。节 9 要求"直接引用原文"才能写 next step，强制 grounding。

#### （3）Compaction agent 隔离

压缩过程在 forked agent（独立 context）中执行：

```typescript
// compact.ts → streamCompactSummary()
const result = await runForkedAgent({
  promptMessages: [summaryRequest],
  cacheSafeParams,
  canUseTool: createCompactCanUseTool(), // 拒绝所有工具调用
  querySource: 'compact',
  maxTurns: 1,
  skipCacheWrite: true,
})
```

compaction agent 被 `createCompactCanUseTool()` 强制设为只输出文本，不能调工具。系统 prompt 是 `"You are a helpful AI assistant tasked with summarizing conversations."`，极简角色设定，防止 compaction 本身引入新的推理偏差。

#### （4）Post-compact 状态重注入

压缩后，harness 会主动重注入以下内容（`compact.ts:556-605`）：

- 最近读取过的文件（最多 5 个，token budget = 50K，每文件 ≤ 5K tokens）
- plan mode 状态（保持工作模式连续性）
- 已调用的 skills（含截断，每 skill ≤ 5K tokens）
- MCP tool 声明（delta 形式）
- session start hooks 输出

**这个"重注入"逻辑是防 post-compact drift 的核心**：摘要本身不携带工具状态，重注入补全了 agent 继续工作所需的 context。

#### （5）PTL retry：compaction 本身失败时的降级路径

`truncateHeadForPTLRetry()`：如果 compaction 请求本身因 prompt too long 失败，按 API round 分组，从最老的 round 开始丢弃（不是随机丢），直到请求可以成功。最多重试 3 次，超过后抛出错误。

#### （6）Circuit breaker：防止无效重试

```typescript
const MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3
// 连续失败 3 次后停止重试，避免每轮都尝试注定失败的 compact
```

**来源**：`autoCompact.ts:99`，注释写明："BQ 2026-03-10: 1,279 sessions had 50+ consecutive failures (up to 3,272) in a single session, wasting ~250K API calls/day globally."——这是典型的从生产 postmortem 倒逼出来的工程设计。

### 1.2 hermes-agent 的 Trajectory Compressor（🟢 SHIPPED · 开源自进化 agent）

**来源**：`~/Repos/opensource-hub/self-evolution/hermes-agent/trajectory_compressor.py`

hermes-agent 用于压缩训练轨迹，设计模式与 Claude Code 相似但侧重点不同：

```python
# 保护策略：首尾不压缩，只压缩中间
protect_first_system: bool = True
protect_first_human: bool = True
protect_first_gpt: bool = True
protect_first_tool: bool = True
protect_last_n_turns: int = 4

# 压缩目标
target_max_tokens: int = 15250
summary_target_tokens: int = 750  # 摘要本身的 token 预算
```

**关键模式**："保护首尾，压缩中间"——首轮包含原始意图，尾部包含最近决策，这两段不压缩。中间的执行细节被替换为一条 summary message。这与 Claude Code compaction 的"preserve recent messages"原则同构。

### 1.3 opencode 的 Compaction（🟢 SHIPPED · 开源 coding agent）

**来源**：`~/Repos/opensource-hub/opencode/packages/opencode/src/session/message-v2.ts`

opencode 用 `CompactionPart`（type: "compaction"）作为消息类型，支持 `tail_start_id` 字段——允许保留最近的 N 条消息不压缩（类似 hermes 的 `protect_last_n_turns`）。compaction 边界通过 `compactionIndex` 确定，边界前的消息被 summary 替换，边界后的消息保留原文。

---

## 2. 结构化 Artifact：文件即记忆，防 drift 最强手段

### 2.1 CLAUDE.md / AGENTS.md 作为 context 锚点（🟢 SHIPPED · Claude Code / GitHub Copilot）

**来源**：`~/Repos/opensource-hub/claude-code/src/utils/claudemd.ts`

Claude Code 的 CLAUDE.md 加载逻辑揭示了 context engineering 的核心设计：

```
加载顺序（优先级递增）：
1. Managed memory (/etc/claude-code/CLAUDE.md) — 全局规则
2. User memory (~/.claude/CLAUDE.md) — 用户私有规则
3. Project memory (CLAUDE.md, .claude/CLAUDE.md, .claude/rules/*.md) — 项目规则
4. Local memory (CLAUDE.local.md) — 私有项目规则
```

关键工程细节：
- 每个 CLAUDE.md 文件上限 `MAX_MEMORY_CHARACTER_COUNT = 40,000 chars`
- 支持 `@include` 指令，允许模块化引用（`@./path`、`@~/home/path`）
- **加载在 system prompt，不在 user turn**——这保证了它始终在 context 最前面，不会被 attention dilution
- Compaction 后不需要重注入（memory 文件在 system prompt，compaction 不动 system prompt）

**这个设计对 spec/design 流水线的直接含义**：将 spec、design 约束、品味规则都以文件形式管理，然后在 system prompt 里 `@include`，比在对话里"聊"规则有更稳定的 attention 优先级。

### 2.2 spec 作为不可变合约（🟢 SHIPPED · hermes/BMAD/Kiro 均有类似模式）

第一轮报告已证明 OpenEvolve 实验：允许 agent 自行修改 spec 时，验证 agent 被完全移除，成功率从 53% 暴跌至 30%。

工程结论：spec 文件在 worker context 里只读注入，不允许 worker 修改。若需修改，必须走 human-approval gate。这不是过度保守，是防止系统规避质量检查的必要约束。

**实现方式**：在 worker system prompt 里声明 `spec.md 为只读参考，不允许修改`；通过 orchestrator 在 sub-agent 调用前注入 spec 副本，而不是暴露文件写权限。

### 2.3 Artifact 传递代替消息传递（🟢 SHIPPED · Claude Code / nano-multiagent 现有）

Claude Code 的 attachment 机制（`utils/attachments.ts`）是 artifact 传递的典型实现：
- 文件读取状态（readFileState）在 compaction 后重注入最近的 5 个文件
- skill 内容作为 attachment 注入，不放进消息历史
- MCP 工具声明作为 delta attachment，只在变化时重注入

**对本场景的启示**：spec.md / design.md 应以 attachment 形式注入 worker context，而不是让 worker 在对话里读。这样 compaction 后 harness 会主动重注入，不会因 compaction 丢失 spec 锚点。

---

## 3. Sub-agent 隔离：独立 context 窗口

### 3.1 Claude Code 的 createSubagentContext（🟢 SHIPPED · Anthropic 生产）

**来源**：`~/Repos/opensource-hub/claude-code/src/utils/forkedAgent.ts:309-400`

```typescript
/**
 * By default, ALL mutable state is isolated to prevent interference:
 * - readFileState: cloned from parent
 * - abortController: new controller linked to parent (parent abort propagates)
 * - getAppState: wrapped to set shouldAvoidPermissionPrompts
 * - All mutation callbacks (setAppState, etc.): no-op
 * - Fresh collections: nestedMemoryAttachmentTriggers, toolDecisions
 */
export function createSubagentContext(
  parentContext: ToolUseContext,
  overrides?: SubagentContextOverrides,
): ToolUseContext
```

关键设计原则：**默认全隔离，显式 opt-in 共享**。每个 sub-agent 有自己的：
- `readFileState`（文件状态缓存，克隆自 parent 保证 cache 命中，但写入不影响 parent）
- `abortController`（子 abort 不影响父，父 abort 会传播给子）
- `agentId`（独立 ID 用于独立 transcript 记录）
- `toolDecisions`（工具调用决策隔离）

这种设计让每个 worker 运行在干净的 context 里，不会继承上游 agent 的工具调用历史噪声。

### 3.2 forkedAgent 与 prompt cache 共享（🟢 SHIPPED · Anthropic 生产）

一个关键的工程优化：sub-agent 调用时，可以通过 `cacheSafeParams`（system prompt + tools + model 必须完全一致）共享 parent 的 prompt cache，节省 token 开销：

```typescript
type CacheSafeParams = {
  systemPrompt: SystemPrompt       // 必须与 parent 完全相同
  userContext: { [k: string]: string }
  systemContext: { [k: string]: string }
  toolUseContext: ToolUseContext
  forkContextMessages: Message[]   // parent 的消息前缀
}
```

**对 spec/design 流水线的意义**：orchestrator 可以把 spec.md 内容放进 system prompt（所有 agent 共享），这样 spec 只需要上传一次，后续的每个 sub-agent（spec-author / design-author / critic）都命中 cache，不重复计费。

---

## 4. Context 窗口预算管理

### 4.1 多级阈值设计（🟢 SHIPPED · Claude Code 生产）

**来源**：`autoCompact.ts:64-66`

```typescript
export const AUTOCOMPACT_BUFFER_TOKENS = 13_000
export const WARNING_THRESHOLD_BUFFER_TOKENS = 20_000   // UI 警告阈值
export const ERROR_THRESHOLD_BUFFER_TOKENS = 20_000     // UI 错误阈值
export const MANUAL_COMPACT_BUFFER_TOKENS = 3_000       // blocking limit
```

三级状态：warning（预警）→ error（显红）→ blocking limit（彻底卡住）。在 blocking limit 之前 compact，保留 3K buffer 给手动 compact。

**对 spec/design pipeline 的启示**：每个 sub-agent 启动时注入一个 `context_budget` 估算，在 system prompt 告知 agent 大约有多少 token 可用，让 agent 自主控制输出详细程度。这是纯 prompt 层的 budget awareness，不依赖 logit 访问。

### 4.2 Output token 预留策略（🟢 SHIPPED · Claude Code 生产）

```typescript
// autoCompact.ts:29-32
// Reserve this many tokens for output during compaction
// Based on p99.99 of compact summary output being 17,387 tokens.
const MAX_OUTPUT_TOKENS_FOR_SUMMARY = 20_000

getEffectiveContextWindowSize(model) = contextWindow - MAX_OUTPUT_TOKENS_FOR_SUMMARY
```

**工程原则**：在计算"可用 input context"时，先减去 output 预留。spec/design agent 的输出通常比代码生成更长（大量文字分析），应预留更多 output budget（建议 30K-50K）。

### 4.3 Per-turn token growth 估算（🟢 SHIPPED · Claude Code 生产）

```typescript
// autoCompact.ts:88-94
export function estimateMaxTurnGrowth(model: string): number {
  const maxOutput = Math.min(
    getMaxOutputTokensForModel(model),
    MAX_OUTPUT_TOKENS_FOR_SUMMARY,
  )
  return maxOutput + TOOL_RESULT_GROWTH_ESTIMATE  // TOOL_RESULT_GROWTH_ESTIMATE = 15K
}
```

**含义**：每 turn 最多增长 = `maxOutput + 15K（工具结果）`。在 spec/design 阶段，工具调用少（主要是读文件），per-turn growth 主要来自 LLM output。估算 context 消耗时可以用这个上界。

---

## 5. Constitution/Rules 按需加载

### 5.1 Claude Code 的 systemPromptSection 注册机制（🟢 SHIPPED · Anthropic 生产）

**来源**：`constants/prompts.ts`

Claude Code 用注册表模式管理 system prompt 各节：

```typescript
systemPromptSection('memory', () => loadMemoryPrompt()),
systemPromptSection('language', () => getLanguageSection(settings.language)),
DANGEROUS_uncachedSystemPromptSection(
  'mcp_instructions',
  () => isMcpInstructionsDeltaEnabled() ? null : getMcpInstructionsSection(mcpClients),
  'MCP servers connect/disconnect between turns',
)
```

两类节：
- `systemPromptSection`：**缓存**，只在首次计算，之后 prompt cache 命中
- `DANGEROUS_uncachedSystemPromptSection`：**每 turn 重算**，仅用于真正动态内容（如 MCP 连接状态）

**工程原则**：越稳定的内容越应该放进缓存型 system prompt section。spec/design 约束（constitution）一旦定稿就不变，应放 cached section；当前 session 的动态状态（如"正在等待 human review"）如果要注入，用 uncached section 或 attachment。

### 5.2 规则文件的注意力稳定性

**关键发现（来自第一轮报告）**：constitution 文件面临"Curse of Instructions"——当单条 system prompt 中指令超过约 20 条时，后半部分的遵守率约 50%。

**工程对策**：
- constitution 控制在 20 条以内，每条对应一个"不可违反的硬约束"
- 把"软指导"（如偏好性风格）移到 few-shot examples 而不是 constitution
- 每个 agent role 只注入**该角色需要的**约束，不要把全部 constitution 注入所有 agent（spec-author 不需要 coding style 规则）

---

## 6. 黑盒 CAN / CANNOT 表

| 技术 | 黑盒 CAN/CANNOT | 说明 | 最佳黑盒替代 |
|------|----------------|------|-------------|
| LLM compaction/summary | 🟢 CAN | 纯 prompt，forked agent 生成摘要 | — |
| 结构化 artifact（spec 文件） | 🟢 CAN | 文件读入，system prompt 注入 | — |
| Sub-agent 独立 context | 🟢 CAN | 每个 worker 新建 context，只注入所需 artifact | — |
| Constitution 文件 | 🟢 CAN | system prompt 固定位置注入 | — |
| Token budget prompt awareness | 🟢 CAN | 在 prompt 中告知 agent 当前 token 使用量 | — |
| Attention 可视化 / logit 读取 | 🔴 CANNOT | 需解码层访问 | 结构化 artifact 重注入替代 |
| Entropy-based auto-truncation | 🔴 CANNOT | 需 token probability | threshold-based 触发 compaction |
| Adaptive thinking budget（API层） | 🔴 CANNOT（直接控制） | 需原生 API 支持 | prompt 中声明思考详细程度 |
| Verbalized confidence（自报置信） | 🟡 有限 CAN | ECE 高（可达 0.377），不可作为唯一 gate | sampling consistency 替代 |
| Sampling consistency 置信 | 🟢 CAN | 多次采样比一致性，纯黑盒 | — |
| Context collapse / recursive summary | 🟢 CAN | 可 prompt 实现多级摘要 | — |

---

## 7. 对本 unit（feat-397）的可操作建议

### P0：必做（立即）

**1. spec.md / design.md 作为 artifact 锚点，不在消息历史里传递**

每个 sub-agent（spec-author / design-author / critic）的 context 应包含：
```
system_prompt: 
  - agent role 定义（简短）
  - 本 agent 需要的 constitution 条目（≤10 条）
  - @include spec.md（只读）
  - @include design.md（只读，如适用）
  
user_turn_1（由 orchestrator 构造）:
  - 本 milestone 的具体任务描述
  - 上一轮 critic 的反馈（如有）
  - 本 turn 的 context_budget 估算（如："你有约 80K tokens 可用于输出"）
```

不要把 spec 放进消息历史——它会随 compaction 丢失或被 attention 稀释。

**2. Orchestrator 持有 spec immutability 门控**

Worker 只能读 spec，不能写。Orchestrator 在每次 worker turn 前重新注入 spec 副本。任何 spec 变更必须走 human-approval gate（通过 IM 通知用户）。

**3. 每个 worker 独立 context 启动**

spec-author、design-author、critic 各自启动干净 context，只注入它们的 artifact。这防止了"上游 worker 的工具调用历史污染下游推理"的问题。

**4. Compaction 触发策略**

对于可能跑多轮的 spec-author（用户反馈→修改→再反馈），在 context 用量达到 `window * 0.75` 时主动触发 compaction。摘要 prompt 应包含节 1（用户意图原文）和节 6（所有用户消息原文）——这两节是防 intent drift 最关键的部分，直接借鉴 Claude Code 的 9 节结构。

### P1：建议（1-4 周内）

**5. Context budget 提示注入**

每个 sub-agent 的第一条 user message 注入当前 context 使用量：
```
[Context Budget] 当前 context 已用约 Xk tokens，窗口 200k，请控制输出在 YY 节以内。
```
这是纯 prompt 层的 budget awareness，让 agent 自主控制输出详细度，防止 spec-author 写出 20 页不必要的分析。

**6. Compaction 摘要 prompt 加"用户意图保护节"**

在标准 compaction prompt 基础上加一条 custom instruction：
```
特别注意：第 1 节（Primary Request and Intent）和第 6 节（All user messages）必须完整保留用户原话，不要意译或提炼。intent drift 在多轮规划中会累积放大。
```

**7. Constitution 分层注入**

给三个 agent role 各自维护精简版 constitution：
- `spec-author.constitution`（≤10 条）：用户意图优先于技术完整性、一次一问、escalate 价值岔路
- `design-author.constitution`（≤10 条）：架构决策原则、技术栈偏好
- `critic.constitution`（≤10 条）：评审标准、escalate 触发条件

不要共享一个大 constitution，每个角色只看自己的部分。

### P2：后续迭代

**8. Session memory compact（hermes 轨迹压缩启示）**

如果 spec/design 迭代超过 10 轮，考虑一个更激进的"session memory"模式：将整个历史用专用 LLM 压缩为一份结构化决策日志（GIVEN/WHEN/THEN 格式），丢弃中间过程，只保留最终决策和理由。这等效于 hermes-agent 的 `trajectory_compressor` 在 spec 阶段的应用。

**9. Partial compact（保留最近 N 轮）**

参考 Claude Code 的 `partialCompactConversation`（`compact.ts:801-1140`），支持"保留最近 3 轮消息原文 + 压缩更早历史"。这在 spec 迭代后期非常有用：最近的 human feedback 不压缩，只压缩前面的探索性讨论。

---

## 8. Reality Check：工程风险

**1. Post-compact drift（最大风险）**  
Compaction 摘要本身可能稀释细节。Claude Code 通过"重注入 5 个最近文件 + plan 状态"来缓解，但 spec/design 场景更依赖用户的**原话意图**，摘要 agent 可能在意译时引入 drift。缓解：custom compact instruction 强制保留用户原话（第 6 节全量保留）。

**2. Artifact 重注入成本**  
每次 compaction 后重注入 spec/design 文件会产生 cache_creation token。如果 spec 内容稳定（compaction 后 spec 不变），下次 turn 会 cache hit，只收一次创建费。但如果每轮 spec 都有修改，每次都是 cache miss。解决方案：把 spec 的"不变核心"（约束/原则）和"变化前缘"（当前讨论的具体条目）分开存储，core 部分长期在 system prompt cache。

**3. Sub-agent context 碎片化**  
如果 worker 之间信息传递完全靠文件，而文件命名或路径约定不统一，orchestrator 管理成本高。建议在本 unit 早期就定义 artifact schema（`spec.md` 固定结构、`design.md` 固定结构），让每个 agent 都知道从哪里读什么。

**4. Compaction 中的工具状态丢失**  
Claude Code 明确在 compaction 后重注入 deferred tools、MCP instructions 等。在 nano-multiagent 的 spec/design 场景里，对应的是"当前讨论的 issue 链接"、"已 approve 的决策列表"等元数据。这些应该也有对应的 post-compact 重注入逻辑，否则 worker 重启后会"失忆"。

---

## 9. 必读一手工程来源

| 来源 | 路径 | 一句话理由 |
|------|------|------------|
| Claude Code compact 实现 | `~/Repos/opensource-hub/claude-code/src/services/compact/` | 目前最完整的生产级 compaction 实现，9 节结构摘要 + post-compact 重注入 + circuit breaker，全部有 BQ 数据支撑的工程决策 |
| Claude Code forkedAgent | `~/Repos/opensource-hub/claude-code/src/utils/forkedAgent.ts` | Sub-agent 隔离的权威实现，"默认全隔离，显式 opt-in 共享"的接口设计模式值得直接复用 |
| Claude Code claudemd.ts | `~/Repos/opensource-hub/claude-code/src/utils/claudemd.ts` | CLAUDE.md 层次加载逻辑，说明如何用文件系统实现 context 锚点，MAX_MEMORY_CHARACTER_COUNT 等约束有实测依据 |
| hermes trajectory_compressor | `~/Repos/opensource-hub/self-evolution/hermes-agent/trajectory_compressor.py` | "保护首尾，压缩中间"策略的开源实现，protect_last_n_turns 模式直接适用于 spec 迭代场景 |
| Anthropic context engineering blog | [https://www.anthropic.com/engineering/building-effective-agents](https://www.anthropic.com/engineering/building-effective-agents) | 官方工程指南，文件即记忆、sub-agent 隔离、artifact 传递三个核心模式的权威出处 |
