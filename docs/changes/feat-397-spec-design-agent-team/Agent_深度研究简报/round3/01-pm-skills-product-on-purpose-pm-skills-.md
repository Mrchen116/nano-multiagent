# 第三轮深度研究：pm-skills 代码库解析

> **来源**：https://github.com/product-on-purpose/pm-skills（`/tmp/claude-feat397-r3/01-pm-skills-product-on-purpose-pm-skills-`，`--depth 1` 克隆，2026-06-04）
> **标注**：🟢 SHIPPED（代码库已发布，v2.24.0，Apache 2.0）
> **服务目标**：feat-397 unit 实施设计

---

## 0. 核心结论（先读这里）

pm-skills 是目前公开代码库中对"spec/design 多 agent 结构"研究价值最高的一手源码。它解决的问题域是 **PM artifact（PRD/OKR/Persona/Lean Canvas）的生产-审核循环**，与本项目 spec/design 对齐的结构性问题高度同构。

它提供了三个对 feat-397 直接可搬的工程机制：

1. **强制上下文隔离**：写 artifact 的 agent 与审 artifact 的 agent **分别在独立上下文窗口运行**，通过文件（artifact 落盘）而非共享 context 传递状态——这在代码中有强制执行路径。
2. **adversarial framing 作为系统设计决策**：`pm-critic` 的 system prompt 里明确写"You never validate; you stress-test"，通过 `tools: Read, Grep, Glob`（无写权限）在架构层而非提示层保证独立性。
3. **orchestrator 不 spawn 子 agent、改用 leaf-inlining**：`pm-workflow-orchestrator` 的 `tools` 列表里没有 `Agent` 工具，Category 2 dispatch skill（会 spawn sub-agent）通过"读 agents/pm-critic.md + 在自己的 context 内 inline 执行"的方式处理，保证 chain depth = 2 max。

---

## 1. 针对 spec/design 单 agent 的哪个失败模式，用什么 multi-agent 结构补

### 1.1 失败模式：自我审核的感知性偏见（自圆其说）

> "A skill that self-reviews has a perverse incentive (pretend the output is good). A separate sub-agent does not."  
> — `docs/internal/release-plans/v2.16.0/spec_pm-critic.md` L31-32

**pm-skills 的结构性补法**：`pm-critic` 是专职 critic sub-agent，`description` 字段中写 `"use proactively after any PM-artifact-producing skill completes"`，由 Claude 的 intent classifier 自动在每次 artifact 生成后触发派发，不需要人或 orchestrator 显式调用。

关键约束落在 **工具层**（不是提示层）：

```yaml
# agents/pm-critic.md frontmatter
tools: Read, Grep, Glob
```

无 `Write` 工具 = 物理上无法修改 artifact。无 `Agent` 工具 = 无法再派发子 agent，chain depth 天然封顶在 1。`memory: none` = 每次调用是独立 context，不会被之前会话的"看法"污染。

### 1.2 失败模式：generator 与 reviewer 共享 context，形成信息茧房

**pm-skills 的结构性补法**：两层 context 隔离。

第一层：`pm-critic` 是 Claude Code plugin sub-agent，Claude Code 的 sub-agent 机制保证它在独立上下文窗口内运行（和主线程 context 物理分离）。

第二层：critic 读的是落盘文件（`agents/pm-critic.md` system prompt 说"Read the target artifact"，即从磁盘读），而非从主线程 context 窗口继承内容。这意味着 critic 看不到 generator agent 的内部推理过程，只看到最终产物。

```
[spec-author/main thread]
    → 写 artifact 到 disk
    → pm-critic auto-delegates
    
[pm-critic, 独立 context 窗口]
    → Read artifact from disk
    → Read canonical SKILL.md（standards doc）
    → 返回 findings（不写文件）
```

这个结构在 `spec_pm-critic.md` L123-130 的 lifecycle 图里有明确的 sequenceDiagram 描述，说明这是刻意设计而非偶然。

### 1.3 失败模式：reviews 没有结构化质量 grammar，人无法高效处置

**pm-skills 的结构性补法**：P0/P1/P2/P3 severity grammar（D15 master plan）。

```
P0: Blocks ship. 必须在下次 review 前修复
P1: Fix before next major review. 在 artifact 进入下一工作流阶段前修复
P2: Consider. 作者自行判断
P3: Nit. 时间紧时可跳过
```

每条 finding 必须包含 **concrete fix suggestion**（"This is unclear 不是 finding；Rewrite as X to address Y 才是"）。这个约束既在 system prompt 里，也在 spec doc 里，作为接受标准的一部分。

实际影响：人类审视 findings 时可以按 P0/P1 优先处置，而不是面对一堆"这里写得不好"的泛化意见。

### 1.4 失败模式：standards drift（critic 基于的标准随时间漂移）

**pm-skills 的结构性补法**：**referential discipline（D12）**。

`pm-critic` 的 system prompt **不嵌入** standards 内容，而是指令 agent 在每次调用时**实时读取**对应的 canonical 文档：

```
# 来自 agents/pm-critic.md（实际代码）
## Standards Consultation (Referential)

At invocation time, read the canonical contract docs for the artifact type.
- OKR sets: read `skills/foundation-okr-writer/SKILL.md` sections on...
- PRDs: read `skills/deliver-prd/SKILL.md` for success-metric testability...
```

这样，OKR 写作规范更新后，critic 下次调用时自动使用最新版本，不会出现 critic 的判断标准和实际规范脱节的问题。

### 1.5 失败模式：orchestrator 自身也做 author，角色混淆

**pm-skills 的结构性补法**：orchestrator (`pm-workflow-orchestrator`) 的工具列表里明确没有 `Agent`：

```yaml
# agents/pm-workflow-orchestrator.md frontmatter
tools: Skill, Read, Grep, Glob, Bash, Edit
# 注意：明确无 Agent 工具
```

注释里有明确声明：`"Agent is deliberately ABSENT: you spawn zero sub-agents, so you need no agents/_chain-permitted.yaml entry and add zero chain depth. A future editor must NOT add Agent to this line."`

Orchestrator 负责的是**走 step list + 状态持久化 + 通过 Skill tool 派发**，不直接生产 artifact，也不直接做 review（category 2 dispatch skill 走 leaf-inlining 而非链式调用）。

---

## 2. 人留在哪（哪些决策升级给人）

### 2.1 结构化的人工 checkpoint

`pm-workflow-orchestrator` 的两种运行模式：

**CHECKPOINTED（默认）**：每个 OK step 后暂停，等待人的 go/no-go。per-step actions: approve / edit / skip / redo。

**GUARDED AUTO（`--auto` flag opt-in）**：OK 的 step 自动推进，但 FAILED 或 EMPTY step **无条件停下**，等人处置。`--force-auto` 也无法 bypass 这两个触发条件。

```
stop-on-failed/empty 是无条件的，outranks --force-auto in all domains
```

### 2.2 Cynefin 域控人工强制介入

`pm-workflow-orchestrator` 读 action plan 的 domain 标签（Clear/Complicated/Complex/Chaotic），对 Complex/Chaotic 计划**强制 CHECKPOINTED**，即使用户传了 `--auto`。只有 `--force-auto` 可以覆盖，而且 `--force-auto` 本身不 bypass stop-on-failed/empty。

这意味着：**高不确定性的 spec/design 工作天然需要人在每步确认**，系统不允许在这类任务上全自动跑完。

### 2.3 pm-critic 的 P0/P1 findings 升级

`pm-critic` 发现 P0 findings 后，workflow 设计要求返回 artifact 给 author 修改（`spec_pm-critic.md` L261-276 描述的 `deliver-prd → pm-critic → 修改 → pm-critic 再审` 循环）。P0 是强制人工修改（阻断 ship），P2/P3 是人工判断是否接受。

### 2.4 refusal → 升级给人

pm-critic 有四种 refusal protocol（输入不完整、artifact 类型越界、draft 低于 review 阈值、无法识别 standards），refusal 以 P0 finding 格式返回，让人提供缺失的上下文或修正输入。

---

## 3. 黑盒 LLM 下 CAN/CANNOT

| 机制 | 黑盒 CAN/CANNOT | 说明 |
|---|---|---|
| pm-critic 独立上下文（sub-agent 机制） | **CAN** | Claude Code plugin 原生支持，纯配置 |
| adversarial framing（Read-only tools） | **CAN** | frontmatter 工具列表配置，纯声明式 |
| referential discipline（调用时读 SKILL.md） | **CAN** | LLM 读文件能力，无需 logit 访问 |
| P0/P1/P2/P3 severity grammar | **CAN** | prompt 级约束，黑盒 LLM 遵循 |
| concrete fix requirement（finding 必须含修复建议） | **CAN** | prompt 级规则 |
| stop-on-failed/empty 门控 | **CAN** | orchestrator 层确定性检查（文件存在 + 结构完整性） |
| CHECKPOINTED 模式（每步 human go/no-go） | **CAN** | 异步等待用户回复，通过 IM 通道 |
| Cynefin 域解析 → 降级到 CHECKPOINTED | **CAN** | 正则 + first-whole-word-token，确定性 |
| leaf-inlining（depth=2 约束） | **CAN** | 纯架构约束，文件读 + inline 执行 |
| `--chain-permitted.yaml` allowlist | **CAN** | YAML 配置，validator 脚本检查 |
| proactive auto-delegation（description 触发） | **CAN**（Claude Code 原生） | 其他客户端走 dispatch skill inline path |
| memory: none（每次调用独立） | **CAN** | frontmatter 声明 |
| dispatch skill 跨客户端兼容 | **CAN**（条件） | 非 Claude 客户端 inline 执行 pm-critic.md；Gate B 已验证 Codex CLI |
| 多 reviewer 并行 critique board | **CANNOT**（非 v2.16 范围） | 作者明确标为 v2.18+ exploration |
| hook-triggered sub-agent（PostToolUse） | **CAN** 机制，但 plugin sub-agent 有 security ceiling | sub-agent 无法 self-set hooks，需 user copy-out |

---

## 4. 🟢 SHIPPED 证据

**谁**：product-on-purpose，单人维护者项目（个人 PM/PM tools 开发者）

**在哪**：https://github.com/product-on-purpose/pm-skills，Apache 2.0

**版本**：v2.24.0（截至研究日 2026-06-04）；pm-critic + pm-workflow-orchestrator 分别在 v2.16.0 和 v2.24.0 发布

**实际验证记录**（来自 `subagents-integration-plan.md` Phase 7+8）：

- GATE B（dispatch skill 在非 Claude 客户端的可靠性）：**VALIDATED on Codex CLI 0.128.0 2026-05-17**。3 个 dispatch skill（pm-critic / pm-skill-auditor / pm-changelog-curator）全部 PASSED，含 layered envelope output、refusal protocols 触发。
- GATE C（conductor 的 chain composition 通过 "reference + execute inline" 模式）：**VALIDATED on Codex CLI 0.128.0 2026-05-17**，全部 6 个 gate 跑通。
- validate-agents-md.sh：PASS 59 skill paths
- validate-commands.sh：PASS 全部 4 个新 sub-agent 命令

---

## 5. 代码层关键路径：强制分离如何落地

### 5.1 "写 artifact 的 agent 不做 reviewer" 的代码层执行

**在 spec**（`spec_pm-critic.md` L30-32）：

> "The defining property: pm-critic is invoked after an artifact exists. It is not a co-author; it is a reviewer with adversarial framing. A skill that self-reviews has a perverse incentive (pretend the output is good). A separate sub-agent does not."

**在 frontmatter**（`agents/pm-critic.md`，L1-15）：

```yaml
---
name: pm-critic
description: |
  Use proactively after any PM-artifact-producing skill completes (deliver-prd,
  foundation-meeting-recap, foundation-okr-writer, ...)
tools: Read, Grep, Glob      # 无 Write 工具
model: sonnet
memory: none                  # 独立调用，无状态
---
```

**在 system prompt**（`agents/pm-critic.md` L17）：

```
You are pm-critic. You read PM artifacts adversarially and return structured findings.
You never validate; you stress-test.
```

**What You Do NOT Do**（`agents/pm-critic.md` L45-53）：

```
- Do NOT rewrite the artifact (you are a critic, not an author)
- Do NOT validate that the artifact is good (no "looks great" outputs)
- Do NOT write to files
```

三重保障：description 触发时机（after production）+ 工具列表（无写权限）+ system prompt 指令（never validate）。

### 5.2 pm-workflow-orchestrator 的 artifact routing 逻辑

Orchestrator 的核心路由逻辑（`agents/pm-workflow-orchestrator.md` L184-196）把 step 分为三类：

```
Category 1 - content skills（30 个 phase skills）：
    → 通过 Skill tool 派发，直接执行

Category 2 - DISPATCH skills（会 spawn sub-agent 的，如 utility-pm-critic）：
    → 不走 Skill tool！
    → 读 agents/pm-critic.md，在自己的 context 里 inline 执行 leaf agent 的 flow
    → 原因：防止 depth-3 hop（已在 sub-agent 内再 spawn 会触发 chain depth 限制）

Category 3 - workflow/composite skills（workflow-* commands）：
    → 作为 MANUAL step 输出给用户，不自动执行
    → 防止 nested orchestration
```

关键原文（L192-196）：

> "you MUST NOT invoke these as a native skill. Instead INLINE the leaf agent - read agents/pm-critic.md and execute its flow inline in your OWN context... This preserves depth-2 (you spawn zero sub-agents, directly or transitively)"

这是 artifact routing 的核心决策：**orchestrator 知道哪些下游 skill 会 spawn sub-agent，并用 inlining 代替链式调用**，从而保证整个系统的 chain depth 不超过 2。

### 5.3 chain-permitted allowlist 的代码层执行

`agents/_chain-permitted.yaml`（完整内容）：

```yaml
chain_permitted:
  - pm-release-conductor     # 唯一被允许持有 Agent 工具的 sub-agent
```

注释说明（L9-16）：未在此列表中的 sub-agent，在 frontmatter 里写 `Agent` 工具是 violation，v2.17.0 会通过 CI 自动检查（v2.16.0 是 manual pre-tag check）。

实际效果：`pm-critic` / `pm-skill-auditor` / `pm-changelog-curator` / `pm-workflow-orchestrator` **均不在列表中**，这意味着它们无法 spawn 任何 sub-agent，chain depth 天然为 1（当从主线程调用时）或 2（当从 conductor 链式调用时）。

### 5.4 pm-workflow-orchestrator 的 stop-on-failed/empty 门控

PRODUCED / EMPTY / FAILED 的判断是 orchestrator 自己做的，不依赖下游 skill 的 status 字段（因为 content skills 不输出机器可读 status）：

```
FAILED: 下游调用出错 OR 返回文本是明确的 refusal/error string
EMPTY: 没有 artifact 返回 OR artifact 是纯占位符（template sections 未填充）
PRODUCED: 非 trivial artifact，填充了 target skill 预期的结构
```

EMPTY != PASS。在 GUARDED AUTO 模式下，EMPTY 触发强制 checkpoint pause（不 auto-advance，不 hard halt，但必须等人确认）。这个逻辑是 orchestrator 的**自主判断**，不依赖下游 LLM 的 confidence 分数——在黑盒 LLM 下完全可行。

---

## 6. 对 feat-397 实现直接可搬的内容

### 6.1 可直接搬的机制（6 个）

**M1：spec-reviewer 独立上下文 + 只读工具**

```yaml
# spec-reviewer agent frontmatter（可直接仿写）
tools: Read, Grep, Glob   # 无 Write
model: sonnet
memory: none
```

spec-reviewer 的 system prompt 中明确声明"You never validate; you stress-test"，并列出 "What You Do NOT Do" 清单。找出 spec/design 里的"假设未被挑战"和"成功标准不可测"比写出好的 spec 更难，这是单 agent 的最大失效点。

**M2：adversarial framing + severity grammar**

P0/P1/P2/P3 grammar 对 feat-397 直接适用：

```
P0: 阻断进入 design 阶段（spec 有根本性问题）
P1: 在 design 开始前修复（spec 有重大 gap）
P2: 作者判断（质量提升机会）
P3: Nit（不影响 design 可行性）
```

每条 finding 必须含 concrete fix suggestion。这比"写 spec 的 agent 自我批评"要可靠得多，原因是 critic 没有"我花了很多时间写这个"的沉没成本偏见。

**M3：referential discipline（调用时读 SKILL.md/spec 规范）**

spec-reviewer 的 system prompt 不嵌入 spec 编写规范的内容，而是在每次调用时读 `docs/specs/kernel/spec.md`、`change-spec-author/SKILL.md` 等 canonical docs。当规范更新时，reviewer 自动使用最新版，无需同步更新 reviewer 的 system prompt。

**M4：proactive trigger（每次 spec artifact 产出后自动触发）**

在 `description` 字段加 `"Use proactively after spec artifact is produced"`，让 spec-reviewer 在每次 spec-author 完成后自动被 Claude 的 intent classifier 派发。不需要 orchestrator 显式调用。

opt-out 路径：用户可以把 agent 文件复制到 `.claude/agents/` 并移除 proactive trigger，改为显式调用。

**M5：stop-on-failed/empty 门控（orchestrator 层，不依赖 LLM confidence）**

orchestrator 用**确定性规则**（文件存在 + 必填段落 + GIVEN/WHEN/THEN 格式检查）做 PRODUCED/EMPTY/FAILED 判断，不依赖下游 LLM 返回 status。

在 feat-397 里，这对应：
- spec-reviewer 返回 P0 findings → orchestrator 拒绝进 design
- spec.md 没有 "## 背景" / "## 成功标准" 等必填 section → EMPTY，打回 spec-author
- spec-reviewer refusal（输入不完整）→ FAILED，等人补充

**M6：chain depth = 2 强制约束**

- spec-author（depth 0）→ spec-reviewer（depth 1）：最深 2 层
- design-author（depth 0）→ design-reviewer（depth 1）：最深 2 层
- orchestrator 不持有 Agent 工具，不能 spawn sub-agent（只能通过 Skill tool 委派）

`_chain-permitted.yaml` 白名单只有一个入口（pm-releases-conductor），其余 agent 无权 chain。

### 6.2 需要调整后使用的机制（2 个）

**A1：workflow-triggered（而非 proactive auto-delegation）**

pm-skills 用 description 字段的 `use proactively after` 触发。在 feat-397 里，**orchestrator 显式触发比 proactive auto-delegation 更合适**，因为：
- spec/design 工作比 PM artifact 生产更高风险，不适合"每次写完自动审"（可能噪音过大）
- orchestrator 需要明确知道 reviewer 何时被调用，以便做 checkpoint 决策

实现方式：在 orchestrator 的 step list 里显式把 `spec-reviewer` 作为 Category 2 dispatch step，走 leaf-inlining 方式执行。

**A2：Cynefin 域感知 → 根据 spec 复杂度调整 checkpoint 频率**

pm-skills 从 action plan 的 Section 2 解析 Cynefin 域标签，Complex/Chaotic → 强制 CHECKPOINTED。

feat-397 可以改成：根据 spec 的"不确定性指标"（如 brief 里有多少 open question、有多少 "待调研" 标记）自动调整 checkpoint 频率。但这个解析逻辑需要自己实现，pm-skills 现成的解析器是针对其自己 action plan 格式的。

### 6.3 不要搬的（1 个）

**pm-release-conductor 的 6-gate gated runbook 结构**

这是 maintainer 向的工具（用于 git tag 发布流程），与 feat-397 的 spec/design 对齐问题不同构。feat-397 需要的是"brief → spec 对齐 → design 对齐"的 generator-critic 流水线，而不是发布门控。

---

## 7. 核心失败模式与对应结构总结表

| 单 agent 失败模式 | pm-skills 对应结构 | 落地位置 | 黑盒 CAN | feat-397 可搬性 |
|---|---|---|---|---|
| 自我审核的感知性偏见 | pm-critic 独立 context + adversarial framing | `agents/pm-critic.md` frontmatter + system prompt | CAN | ⭐⭐⭐⭐⭐ 直接可搬 |
| generator/reviewer 共享 context | sub-agent 独立 context 窗口 + 文件传递 artifact | Claude Code plugin 机制 | CAN | ⭐⭐⭐⭐⭐ 直接可搬 |
| 无结构化 review output | P0/P1/P2/P3 severity grammar + concrete fix 要求 | system prompt + spec doc + acceptance criteria | CAN | ⭐⭐⭐⭐⭐ 直接可搬 |
| standards drift（reviewer 的判据过时） | referential discipline（每次调用时读 canonical SKILL.md） | system prompt 中 "Standards Consultation" 节 | CAN | ⭐⭐⭐⭐⭐ 直接可搬 |
| orchestrator 角色混淆（既做 author 又做 reviewer） | orchestrator 无 Write/Agent 工具；Category 2 走 leaf-inlining | frontmatter tools 列表 + `_chain-permitted.yaml` | CAN | ⭐⭐⭐⭐ 需调整 |
| 无法可靠检测 EMPTY/FAILED output | orchestrator 层确定性规则判定 PRODUCED/EMPTY/FAILED | orchestrator system prompt L86-94 | CAN | ⭐⭐⭐⭐ 直接可搬 |
| Human checkpoint 缺失 | CHECKPOINTED 默认模式 + Complex 域强制介入 | orchestrator run mode + Cynefin domain parse | CAN | ⭐⭐⭐⭐ 直接可搬 |
| chain depth 爆炸导致 context 失控 | depth=2 硬约束 + `_chain-permitted.yaml` + leaf-inlining | 多处代码共同保证 | CAN | ⭐⭐⭐⭐⭐ 直接可搬 |

---

## 8. 与前两轮报告的新增点（非重复）

第一轮报告建立了"Generator-Critic 顺序对"的总体方向（🟢 SHIPPED，MetaGPT QA role 等）。第二轮报告验证了 Claude Code 的 `disallowedTools` / `omitClaudeMd` 等机制可用。

本轮新增（pm-skills 代码库一手验证，不在前两轮中）：

1. **adversarial framing 是系统级设计决策，而非 prompt 技巧**：tool list 限制（无 Write）比"请你批判性地看"更可靠，因为它在 context 层面而非意图层面保证独立性。

2. **proactive auto-delegation 的落地细节**：`description` 字段的 `"use proactively after X"` 短语是 Claude Code 的 intent classifier 触发机制，而非随机触发。

3. **referential discipline（D12）的具体落地**：不是"在 prompt 里粘贴规范"，而是"在每次调用时读文件"，这样规范更新时 reviewer 自动使用最新版本——这是前两轮没有具体探讨过的机制。

4. **orchestrator leaf-inlining 解决 depth-3 问题**：从 Category 1/2/3 的路由逻辑到 `_chain-permitted.yaml` allowlist，这是一个完整的 depth 控制工程方案，在前两轮的 orchestrator/worker 分层模型中没有展开过。

5. **EMPTY != PASS 的强制语义**：orchestrator 不依赖 LLM 的 status 字段，自主判定 PRODUCED/EMPTY/FAILED，这比"让 LLM 报告自己的输出质量"更可靠。

---

## 附：关键文件路径索引

| 文件 | 内容 | 研究价值 |
|---|---|---|
| `agents/pm-critic.md` | pm-critic sub-agent 完整定义（frontmatter + system prompt）| 核心：adversarial framing + tool restriction |
| `agents/pm-workflow-orchestrator.md` | orchestrator 完整定义，含 leaf-inlining + artifact routing | 核心：orchestrator 角色隔离 + depth 控制 |
| `agents/_chain-permitted.yaml` | Agent 工具使用白名单 | 安全边界的代码化 |
| `docs/internal/release-plans/v2.16.0/spec_pm-critic.md` | pm-critic 的设计 spec（含 rationale）| 设计决策来源 |
| `docs/internal/release-plans/v2.16.0/subagents-integration-plan.md` | 整体实施计划，含 Gate A/B/C 验证记录 | SHIPPED 证据 |
| `docs/internal/_working/subagents/subagent-strategy_2026-05-07.md` | 设计原始策略（含 10 个 cross-cutting insight）| 架构设计思路来源 |
| `skills/utility-pm-critic/SKILL.md` | dispatch skill（跨客户端兼容 path）| 非 Claude 客户端的 inline 执行机制 |
| `_workflows/feature-kickoff.md` | Feature Kickoff 工作流定义（含 skill 序列）| 工作流结构参考 |
