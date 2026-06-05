# R2D1：Planning 阶段的 Harness 模式

> **研究维度**：P0-1 —— 真实 agent 产品在"需求→spec→design"这种开放式规划阶段用什么 harness/架构
> **一手来源**：claude-code、opencode、codex、openclaw、hermes-agent 本地源码 + 工程博客
> **标注规范**：🟢 SHIPPED = 真在生产产品/开源 harness 被采用；🟡 RESEARCH = 论文/benchmark

---

## 1. 关键发现

### 1.1 Orchestrator-Worker 分层：planning 阶段的主流拓扑

🟢 **SHIPPED — Claude Code（Anthropic）**

Claude Code 的 coordinator/worker 模式直接内置于产品，文件路径：
- `src/coordinator/coordinatorMode.ts`
- `src/commands/coordinator.ts`
- `packages/builtin-tools/src/tools/AgentTool/runAgent.ts`

关键设计：

```typescript
// src/commands/coordinator.ts
// 当启用 coordinator mode，CLI 变为只持有 Agent/SendMessage/TaskStop 三个工具的编排器
process.env.CLAUDE_CODE_COORDINATOR_MODE = '1'
```

Coordinator 的系统提示明确划分四个阶段（出自 `coordinatorMode.ts`）：

| Phase | Who | Purpose |
|-------|-----|---------|
| Research | Workers (parallel) | 并行侦察，读文件/理解问题 |
| **Synthesis** | **You (coordinator)** | 读 findings，**自己理解**，写 implementation spec |
| Implementation | Workers | 按 spec 作修改 |
| Verification | Workers | 测试变更 |

对 planning 场景的直接启示：Synthesis（即 spec/design 阶段）强制由 coordinator 自己做，**禁止**把理解委托给 worker——源码注释："Never write 'based on your findings'—that delegates understanding to the worker."

---

### 1.2 Subagent 独立 context 窗口隔离

🟢 **SHIPPED — Claude Code**

每个 subagent 启动时创建**新的** `initialMessages` 数组，与 parent context 完全隔离：

```typescript
// runAgent.ts L382
const initialMessages: Message[] = [...contextMessages, ...promptMessages]
// contextMessages 来自 forkContextMessages（可选注入父 context 片段）
// 默认是 []，即 fresh window
```

Async agent（planning 阶段常用）得到 unlinked AbortController，完全独立运行：

```typescript
// runAgent.ts L531-537
const agentAbortController = override?.abortController
  ? override.abortController
  : isAsync
    ? new AbortController()           // 完全独立
    : toolUseContext.abortController  // 与父共享（sync）
```

CLAUDE.md 是否注入给 subagent 也被精细控制：

```typescript
// runAgent.ts
const shouldOmitClaudeMd =
  agentDefinition.omitClaudeMd &&
  !override?.userContext &&
  getFeatureValue_CACHED_MAY_BE_STALE('tengu_slim_subagent_claudemd', true)
```

Plan/Explore agent 因为是只读角色，默认**不注入** CLAUDE.md（节省 token），而 implementation worker 则继承完整 context。这体现了按角色精细控制 context 的工程实践。

---

### 1.3 角色化 subagent + 工具集限制：不同阶段用不同角色

🟢 **SHIPPED — Claude Code**

内置 agent 定义（`packages/builtin-tools/src/tools/AgentTool/built-in/`）：

| Agent 角色 | 文件 | disallowedTools | 本质 |
|-----------|------|-----------------|------|
| `Plan` | `planAgent.ts` | AgentTool, FileEdit, FileWrite | 只读规划，READ-ONLY MODE |
| `Explore` | `exploreAgent.ts` | AgentTool, FileEdit, FileWrite | 只读探索 |
| `Verification` | `verificationAgent.ts` | FileEdit, FileWrite | 只测试，不改代码 |

Plan agent 的系统提示（`planAgent.ts`）中有硬规则：

```
=== CRITICAL: READ-ONLY MODE - NO FILE MODIFICATIONS ===
You are STRICTLY PROHIBITED from:
- Creating new files
- Modifying existing files
```

这是 planning 阶段 harness 的关键机制：**通过 disallowedTools 白名单强制角色只读**，不靠提示遵从，而是机制保证。

Agent 定义用 Markdown frontmatter 格式存储在 `.claude/agents/` 目录，便于组合：

```yaml
---
name: spec-author
description: Spec authoring agent
disallowedTools: Bash, FileEdit, FileWrite
---
You are a spec author...
```

---

### 1.4 文件即记忆 / Artifact 传递

🟢 **SHIPPED — Claude Code**

两种 artifact 传递机制：

**A. Scratchpad 目录（跨 worker 共享）**

```typescript
// coordinatorMode.ts L104-106
if (scratchpadDir && isScratchpadGateEnabled()) {
  content += `Scratchpad directory: ${scratchpadDir}
Workers can read and write here without permission prompts. 
Use this for durable cross-worker knowledge — structure files however fits the work.`
}
```

Coordinator 告知所有 workers scratchpad 路径，workers 读写文件作为跨 agent 通信媒介。

**B. Task 结果注入父 context**

Worker 完成时，result 以 `<result>...</result>` 标签写入 output file，coordinator 通过 task-notification 消息接收：

```
<task-notification>
  <task-id>agent-a1b</task-id>
  <status>completed</status>
  <result>Found null pointer in src/auth/validate.ts:42...</result>
</task-notification>
```

这是**结构化文本协议**，不是函数调用——artifact 内容是字符串，coordinator 解析后进入自己的理解层再写下一个 worker 的 spec。

**C. Workflow run 状态文件（顺序流水线）**

`WorkflowTool.ts` 把每步状态持久化到 `.claude/workflow-runs/<runId>.json`：

```typescript
type WorkflowRun = {
  runId: string
  workflow: string
  status: 'running' | 'completed' | 'cancelled'
  currentStepIndex: number
  steps: WorkflowStep[]
}
```

每步完成后调用 `action="advance"` 推进，状态文件是唯一的 artifact store，agent 在跨步骤时通过读文件恢复上下文。

---

### 1.5 确定性门控（Deterministic Gate）

🟢 **SHIPPED — Claude Code**

**Plan Mode + ExitPlanMode tool** 是 planning 阶段最直接的确定性门控：

```typescript
// ExitPlanModeTool/prompt.ts
`Use this tool when you are in plan mode and have finished writing 
your plan to the plan file and are ready for user approval.
This tool simply signals that you're done planning and ready for 
the user to review and approve.`
```

机制：agent 只能通过 `ExitPlanMode` tool 退出 plan mode，该 tool 会触发 human approval dialog——这是硬门控，不是 prompt 层面的约定。在 in-process teammate 场景中，`plan_approval_request` 消息被发送给 team leader（另一个 agent 或人类）：

```typescript
// ExitPlanModeV2Tool.ts L274-291
const approvalRequest = {
  type: 'plan_approval_request',
  ...
}
// Sends as message to team leader
```

对于 non-teammate 场景（用户直接使用），弹出确认对话框等待人类点击。

**AskUserQuestion tool** 是轻量级 choke point，用于在 plan mode 内的澄清问题（不是 approval，是单问单答）。

🟢 **SHIPPED — opencode**

opencode 用 permission 系统控制 plan 门控：

```typescript
// opencode/packages/opencode/src/config/agent.ts
defaults = Permission.fromConfig({
  "*": "allow",
  plan_enter: "deny",
  plan_exit: "deny",
  question: "deny",
  ...
})
```

`plan_enter`/`plan_exit` 作为 permission 节点，可在 config 层面打开/关闭，确保 planning 阶段的进出有显式权限。

---

### 1.6 Human-Approval Choke Point

🟢 **SHIPPED — Claude Code**

Plan Mode 的 ExitPlanMode 是产品层面已落地的 human-approval choke point，工作流：

```
agent 探索 → agent 写 plan 文件 → agent 调 ExitPlanMode
→ [human 看 plan 文件内容] → [approve/reject]
→ approve: agent 继续执行 | reject: agent 修改 plan
```

注意：**plan 内容通过文件传递**（agent 先写文件，ExitPlanMode 从文件读取展示给人类），不是作为 tool 参数。这保证了 human 看到的是 artifact，不是 agent 的口头描述。

🟢 **SHIPPED — 本项目现有基础设施**

本项目已有的"门禁"（gate 1/2/3）和"一轮一问澄清"机制，与 CC 的 ExitPlanMode 在结构上等价——spec artifact 写入文件，human 异步 review，review 通过后才推进。这说明当前 SDD 流水线已经具备 planning harness 的核心模式，缺的是把"前两环"的 spec/design agent 接进来。

---

### 1.7 Role-Structured 顺序流水线

🟢 **SHIPPED — BMAD（开源 SDD 框架）**

BMAD（Business Methodology for Agile Development）采用严格的角色顺序流水线：

```
Analyst (requirements)
  → PM (feature spec)
    → Architect (system design)
      → SM (stories/tasks)
        → Dev (implementation)
```

每个角色是独立 agent，有专属 system prompt，下一个角色只能读上一个角色的 output artifact（Markdown 文件），不能跳过。这是 planning 阶段角色化流水线的典型实现。

🟢 **SHIPPED — AWS Kiro（2025 年 7 月发布）**

Kiro 将 planning 阶段结构化为三个 spec 文档：

```
Requirements.md → Design.md → Tasks.md
```

每个文档对应一个 agent 角色（Requirements Analyst → System Architect → Task Planner），且 Kiro 将这些文档称为"spec files"，作为 immutable contract 在后续实施阶段只读引用。人类在每份文档完成后 review 并 approve，才触发下一阶段。

🟡 **RESEARCH — MetaGPT（角色数量研究）**

MetaGPT 消融实验证明 4 角色（PM/Architect/Engineer/QA）是有效下限：从 4 降到 1 时代码可执行性从 4.0 降到 1.0（完全失败）。但超过 4 角色后边际收益递减，协调开销呈指数增长。这对 spec/design 阶段的结论是：2-3 个专门化角色（Spec Author / Design Reviewer / Critic）比单 agent 或 5+ 角色都更优。

---

### 1.8 Context Engineering：防止 drift 的主流工程做法

🟢 **SHIPPED — Claude Code：autoCompact + microCompact**

长规划链的 context 管理在 CC 中有多层机制（`src/services/compact/`）：

- **autoCompact**：context 窗口超过阈值自动触发，调用 LLM 对历史对话做结构化摘要，保留：任务意图、技术决策、文件修改、用户反馈原话（源码强调：**exact quotes from user**）
- **microCompact**：更细粒度的局部压缩，用于单轮 token 过长
- **sessionMemoryCompact**：把 session 关键信息持久化到 memory 文件，跨 compact 保留

`compact/prompt.ts` 中的摘要 prompt 明确要求保留：
```
6. All user messages: List ALL user messages that are not tool results. 
   These are critical for understanding the users' feedback and changing intent.
7. Pending Tasks
8. Current Work: ...paying special attention to the most recent messages
9. Optional Next Step: ...IMPORTANT: ensure that this step is DIRECTLY 
   in line with the user's most recent explicit requests
```

这体现了**摘要不能丢失意图**的核心约束——compact 的目的是压缩 token，不是压缩信息。

🟢 **SHIPPED — Claude Code：omitClaudeMd per subagent**

Planning/Explore agents 省略 CLAUDE.md（因为不需要 commit/PR/lint 规则），节省 token 的同时保持 context clean。这是**按角色精细控制 context 注入**的工程实践，而非一刀切。

🟢 **SHIPPED — openclaw：bootstrap file 体系**

openclaw 的 workspace 在每次 run 开始时注入一组 bootstrap 文件（`src/agents/workspace.ts`）：

```typescript
export const DEFAULT_AGENTS_FILENAME = "AGENTS.md";   // 操作约束
export const DEFAULT_SOUL_FILENAME = "SOUL.md";        // agent persona/品味
export const DEFAULT_IDENTITY_FILENAME = "IDENTITY.md"; // agent 身份
// + MEMORY.md：向量化的长期记忆
// + HEARTBEAT.md：定时任务上下文（仅 heartbeat 模式）
```

在 lightweight heartbeat 模式下，只注入 `HEARTBEAT.md`，排除 `SOUL.md` 等——这是**按运行模式过滤 context** 的实现。这对 spec/design harness 的启示是：不同阶段（比较分析 vs 写 spec vs 审查）应注入不同的 context 子集。

🟢 **SHIPPED — codex：结构化 compact**

codex（`codex-rs/core/src/compact.rs`）的 compact 机制明确区分 pre-turn/manual compaction（用 `DoNotInject`）和 mid-turn compaction（用 `BeforeLastUserMessage`），后者保证 summary 之后还能看到真正的 user message。两种注入策略确保 model 不会在 compact 后"失去目标"。

---

## 2. 黑盒 CAN / CANNOT 分析

| 技法 | 黑盒 CAN | CANNOT | 最佳黑盒替代 |
|------|---------|--------|------------|
| Orchestrator-Worker 分层 | ✅ 完全可用，只需 prompt + tool call | — | — |
| Subagent 独立 context 窗口 | ✅ 新 API 调用即独立 context | — | — |
| Scratchpad/artifact 文件传递 | ✅ 文件系统读写 | — | — |
| Plan Mode + ExitPlanMode choke point | ✅ 用 AskUserQuestion tool 模拟 | — | — |
| 按角色工具集限制 | ✅ disallowedTools 列表（纯配置） | — | — |
| CLAUDE.md/SOUL.md 类 context 注入 | ✅ 直接拼入 system prompt | — | — |
| AutoCompact（结构化摘要） | ✅ 用 LLM call 做摘要 | — | — |
| Logit-based 置信度 | ❌ 需要白盒 | | sampling-based 一致性（多次采样） |
| 模型训练（RLHF/DPO） | ❌ 不能调模型 | | few-shot 案例库 + prompted critic |
| T-POP/AMULET 解码干预 | ❌ 需要解码层访问 | | prompted self-consistency 检测 |

---

## 3. 对本 unit 实现的可操作建议

### 3.1 架构：在现有 orchestrator/worker 之上加两个角色

当前流水线：`[手动] brief → (门禁1) → spec → (门禁2) → design → (门禁3) → 实施`

前两环需要的 agent 拓扑（最小可用配置）：

```
SpecAuthor agent         → spec.md artifact
    ↓ (gate 1: human review)
DesignEngineer agent     → design.md artifact
    ↓ (gate 2: human review)
→ 现有 change-orchestrator
```

每个 agent：
- 独立 context 窗口（新 LLM 调用）
- 专属 system prompt（role = "spec author" / "design engineer"）
- disallowedTools 按阶段限制（spec author 不能写代码，只能写文档）
- 产出写到文件（`docs/changes/<unit>/spec.md`），gate 通过后才推进

### 3.2 Artifact 传递：文件即记忆

```python
# SpecAuthor 产出写文件
write("docs/changes/{unit}/spec.md", spec_content)

# DesignEngineer 读文件作为 context
context = read("docs/changes/{unit}/spec.md")
# 加进自己的 initialMessages，不是 parent context
```

不要把 spec 内容拼进 parent agent 的对话历史——让 DesignEngineer 作为独立 subagent，只把 spec 文件路径告诉它，它自己读文件。这样 context 隔离，避免 parent context 污染。

### 3.3 Human-Approval Choke Point 的工程实现

两种实现路径（都已 SHIPPED）：

**A. 现有 IM 通道（已有基础设施）**

spec.md 写完后，发 IM 消息给用户：
```
spec draft 已写入 docs/changes/feat-XXX/spec.md
请 review 后回复：approve / reject + 反馈意见
```
用户回复 approve 才推进 DesignEngineer。这是 async escalation 模式。

**B. ExitPlanMode-style tool**

给 SpecAuthor 和 DesignEngineer 各加一个 `RequestApproval` tool，调用时：
1. 把 artifact 路径和摘要包进工具结果
2. agent loop 检测到 tool call 后 pause，等待 human 输入
3. human approve 后继续

对于本项目已有的 IM 异步通道，A 方案更自然，B 方案则在 coding CLI 环境下更适用。

### 3.4 Context Engineering：三层注入

每个 planning agent 启动时注入以下 context（优先级从高到低）：

1. **constitution（硬约束）**：`AGENTS.md` 中的架构/产品偏好，不超过 20 条
2. **few-shot 案例**：来自 `docs/changes/*/spec.md` 历史决策中用户原话，5-7 个最相关案例（按当前 brief 相似度检索）
3. **当前任务 brief**：用户轻 brief + 本次变更目标

CLAUDE.md 等项目操作约束对 spec author **不需要**注入（类似 CC 的 `omitClaudeMd`），节省 token 且避免噪声。

### 3.5 防 drift：spec 为 immutable contract

spec.md 一旦人类 approve，对后续 design/实施阶段是只读的——这是 Claude Code plan mode 和 Kiro spec files 共同验证的做法。

实现：

```python
# design agent 的 system prompt 中写明
DESIGN_SYSTEM_PROMPT = """
You are a design engineer. Your job is to create a detailed technical design.

## Constraints
- spec.md is your input, treat it as immutable requirement contract
- Do NOT change requirements in spec.md
- If spec is ambiguous, use AskUserQuestion tool to clarify, do NOT invent
"""
```

对 spec 的任何变更必须走 human approval，而不是 design agent 自行修改。

### 3.6 先做 vs 先别做

**先做（立即可落地）**：
1. 给 change-spec-author skill 加 ExitPlanMode-style approval choke point
2. spec.md / design.md 写入文件，作为 artifact 传递而非对话传递
3. DesignEngineer 独立 context 窗口（不继承 spec author 的对话历史）
4. 按阶段注入 context（spec 阶段不注入代码相关规则）

**先别做**：
- 多个 spec authors 并行 debate（开放式 planning 阶段，debate 容易 drift，单 agent + 强 context engineering 更可靠）
- Memory 自动更新（procedural memory 有 drift 风险，手动维护 constitution 更安全）
- 置信度数值化 escalation（planning 阶段的不确定性多是 value fork，用 prompted 检测 + 强制 human review 更可靠）

---

## 4. 主表：模式 × SHIPPED/RESEARCH × 可迁移性

| 架构模式 | 标注 | 谁在用 | 源码路径 | 本场景可迁移性 |
|---------|------|--------|---------|-------------|
| Orchestrator-Worker 分层 | 🟢 SHIPPED | Claude Code | `src/coordinator/coordinatorMode.ts` | ⭐⭐⭐⭐⭐ 直接可用 |
| Subagent 独立 context 窗口 | 🟢 SHIPPED | Claude Code | `AgentTool/runAgent.ts L382, L531` | ⭐⭐⭐⭐⭐ 直接可用 |
| disallowedTools 角色工具限制 | 🟢 SHIPPED | Claude Code | `built-in/planAgent.ts` | ⭐⭐⭐⭐⭐ 直接可用 |
| 文件 artifact 传递 | 🟢 SHIPPED | Claude Code / openclaw | `coordinatorMode.ts` scratchpad | ⭐⭐⭐⭐⭐ 已有基础 |
| ExitPlanMode human choke point | 🟢 SHIPPED | Claude Code | `ExitPlanModeTool/` | ⭐⭐⭐⭐ 需适配 |
| AutoCompact 结构化摘要 | 🟢 SHIPPED | Claude Code / codex | `services/compact/prompt.ts` | ⭐⭐⭐⭐ 已有 compact |
| Bootstrap 文件按阶段过滤 | 🟢 SHIPPED | openclaw | `src/agents/workspace.ts` | ⭐⭐⭐⭐ 参考实现 |
| Role-Structured 顺序流水线 | 🟢 SHIPPED | BMAD / Kiro | — | ⭐⭐⭐⭐ 本场景适配 |
| Workflow Tool 顺序步骤状态机 | 🟢 SHIPPED | Claude Code | `WorkflowTool/WorkflowTool.ts` | ⭐⭐⭐ 可参考 |
| SOUL.md / constitution 文件 | 🟢 SHIPPED | openclaw | `src/agents/workspace.ts L20` | ⭐⭐⭐⭐ 建议采用 |
| MetaGPT 4 角色最优规模 | 🟡 RESEARCH | — | 消融实验 | ⭐⭐⭐ 验证了 2-3 角色方案 |
| omitClaudeMd per subagent | 🟢 SHIPPED | Claude Code | `runAgent.ts L395-407` | ⭐⭐⭐⭐⭐ 直接可用 |

---

## 5. 推荐的一手工程来源

1. **`~/Repos/opensource-hub/claude-code/src/coordinator/coordinatorMode.ts`**
   — CC coordinator 完整 system prompt，含 4 阶段流水线、并发策略、worker prompt 写法指南。是 orchestrator 设计的最优参考。

2. **`~/Repos/opensource-hub/claude-code/packages/builtin-tools/src/tools/AgentTool/built-in/planAgent.ts`**
   — 只读 planning agent 的完整实现：READ-ONLY MODE 强制、disallowedTools 列表、omitClaudeMd 优化。spec author 可直接参考。

3. **`~/Repos/opensource-hub/claude-code/packages/builtin-tools/src/tools/ExitPlanModeTool/ExitPlanModeV2Tool.ts`**
   — plan approval choke point 的完整实现，含 teammate 向 leader 发 `plan_approval_request` 的协议。

4. **`~/Repos/opensource-hub/claude-code/packages/builtin-tools/src/tools/WorkflowTool/WorkflowTool.ts`**
   — 顺序流水线状态机：YAML/Markdown workflow 文件 → 步骤状态持久化 → advance API。可直接用于 spec/design 阶段顺序编排。

5. **`~/Repos/opensource-hub/openclaw/src/agents/workspace.ts`**
   — SOUL.md/IDENTITY.md/MEMORY.md/AGENTS.md 的 bootstrap file 体系，以及 lightweight 模式下的按需过滤。是"品味注入"的工程参考实现。

---

## 6. Reality Check

**哪些是 hype**：
- "多 agent debate 提高质量"：在开放式 planning 任务上，同质 agents debate 多数情况下产生 Martingale Curse（数学证明无法超越多数投票），同时引入 78% 的 problem drift（MAST）。对 spec 写作任务，**单 agent + 强 context engineering** 比多 agent debate 更可靠。
- "agent 自动更新自己的 constitution"：procedural memory 有 drift 风险，openclaw/LangMem 都需要 audit governance。不建议在 planning 阶段引入。

**哪些被证明帮倒忙**：
- 超过 4 个 agent 角色的流水线（MetaGPT 消融）：协调开销超过收益
- 把 spec 内容通过对话传递而非文件传递：context 污染 + 后续难以 review
- 11 阶段门控流水线（McEntire 对照实验）：28/28 vs 0/28，过度门控反而失败

**最大工程风险**：
1. **意图漂移**：spec author 生成的 spec 可能与用户 brief 意图产生 2% 偏差，到 design 末端累积到 40% 失败率。缓解：spec 写完后人类 review 是必须的，不是可选的。
2. **constitution 被忽略**：长 constitution 文件（>20 条）遵守率急剧下降（"curse of instructions"）。缓解：constitution 控制在 20 条以内，只放不可违反的硬约束。
3. **Spec 变成 design 的对话史包袱**：design agent 继承太多 spec 阶段的对话 → context 过长 → drift。缓解：独立 context 窗口，只注入 spec 文件内容，不注入 spec 阶段的对话过程。
