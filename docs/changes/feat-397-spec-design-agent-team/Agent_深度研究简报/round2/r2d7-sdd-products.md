# R2D7：SDD 产品的 Planning 阶段拆解

> **研究维度**：P2-8 —— BMAD-METHOD、AWS Kiro、OpenSpec 前两环的具体编排；哪里要人、哪里自动、artifact 怎么流、怎么防过度产 markdown
> **一手来源**：OpenSpec 本地源码（`~/Repos/opensource-hub/OpenSpec/`）、BMAD 官方文档（docs.bmad-method.org/tutorials/getting-started）、Kiro 官网（kiro.dev/docs/specs/）、nano-multiagent 现有 SDD skill 源码（`.claude/skills/`）
> **标注规范**：🟢 SHIPPED = 真在生产产品/开源 harness 被采用；🟡 RESEARCH = 论文/benchmark
> **前提说明**：r2d1 已覆盖"orchestrator-worker 总拓扑 + 单 agent vs 多 agent 比较 + context compaction"，本维度不重复，专注三个 SDD 产品的前两环设计拆解及可迁移性。

---

## 1. 三产品横向拆解

### 1.1 BMAD-METHOD：角色化流水线 + PRD 门控

🟢 **SHIPPED — BMAD-METHOD（bmadcode 开源，社区 >5k stars，2025 主流）**

一手来源：docs.bmad-method.org/tutorials/getting-started

#### 流程结构

```
Analyst (optional)         PM (required)           Architect            PM           Architect
brainstorming/research  →  bmad-prd  →  human-approve  →  create-architecture  →  create-epics-and-stories  →  check-implementation-readiness  →  human-approve  →  Dev
```

**Phase 1（Analysis，可选）**
- Analyst agent 运行 `bmad-brainstorming`、`bmad-market-research`、`bmad-domain-research` 等工作流
- 产物：研究文档、product-brief、prfaq
- 自动化程度：**全自动**（agent 独立完成）
- 人工介入点：无（可选阶段，若跳过则直接进 PM 阶段）

**Phase 2（PRD，必须）**
- PM agent 运行 `bmad-prd`，通过**对话**从用户处收集需求
- 产物：`prd.md`（产品需求文档）、`addendum.md`（补充）、`decision-log.md`（决策日志）
- 自动化程度：**半自动**——PM agent 主导，但对话驱动，用户逐项确认
- **人工审批门控 ✅**：PRD 完成后有明确 human approval checkpoint，通过后才能进 Phase 3

**Phase 3（Solutioning，企业版）**
- Architect agent：`bmad-create-architecture` → 架构文档
- PM agent：`bmad-create-epics-and-stories`（依赖架构完成后）→ Epic/Story 文件
- Architect agent：`bmad-check-implementation-readiness` → 可实施性校验报告
- **人工审批门控 ✅**：readiness check 通过后才能进实施阶段

#### 关键工程设计

**导航工具 `bmad-help`**：每个工作流完成后自动运行，推荐"下一步应该跑什么"。这是防止 agent 迷失的最小 harness——确定性的 next-action 提示，不依赖模型判断。

🟢 **角色化 agent 隔离**：Analyst/PM/Architect 作为独立 agent persona 运行（通过 system prompt 切换），每个只持有自己阶段相关的工具，防止跨阶段 context 污染。

🟢 **`decision-log.md` 落盘**：决策日志作为独立 artifact，在 PRD 旁边持久化。后续实施阶段读它理解"为什么这样决策"，而不是从 PRD 反推。这是 context 跨阶段传递的关键 artifact。

#### 人工介入点汇总

| 阶段 | 自动化程度 | 人工做什么 |
|------|------------|------------|
| Analysis | 全自动 | 无 |
| PRD | 半自动（对话） | 逐问回答，最终 approve PRD |
| Architecture | 半自动（agent 起草） | 确认大方向，approve readiness check |
| Epic/Story | 半自动 | 轻量审阅 |
| 实施 | 全自动 | 仅 review PR |

---

### 1.2 AWS Kiro：Requirements-First + Quick Plan + Steering Files

🟢 **SHIPPED — AWS Kiro（Amazon 2025 发布，VS Code 插件，beta 公开）**

一手来源：kiro.dev 官网（2026-06-04 fetch）

#### 流程结构

Kiro 提供两条路径：

**标准路径（有审批门控）**：
```
用户 brief  →  Requirements（EARS 格式）  →  [human review]  →  Design  →  [human review]  →  Tasks  →  [human approve each]  →  Agent 实施
```

**Quick Plan（无门控）**：
```
用户 brief + 上前问题  →  Requirements + Design + Tasks（全自动一次生成）  →  用户 approve 整包  →  Agent 实施
```

**Design-First 路径**（反向）：
```
用户先写 Design  →  Requirements（从 Design 推导）  →  Tasks  →  实施
```

#### 三阶段 Artifact 格式

**Requirements（`requirements.md`）**
- EARS 格式：`WHEN [条件] THE SYSTEM SHALL [行为]`
- 自动分析一致性（找矛盾的需求）
- 人工介入：标准路径下用户 review + edit 再进 Design；Quick Plan 直接透传

**Design（`design.md`）**
- 自动分析现有代码仓（codebase analysis）
- 产出：架构、系统设计、tech stack 推荐
- 人工介入：标准路径下用户可修改再进 Tasks

**Tasks（`tasks.md`）**
- 依赖分析：自动识别任务间依赖，构建 DAG，独立任务并行运行
- 人工介入：每个 task 用户可选择"让 agent 执行"或手动处理
- Code review：`approve everything / step through each change / make edits`

#### Steering Files（偏好注入）

🟢 **SHIPPED — Kiro Steering Files**

Kiro 的偏好注入机制（对应 BMAD 的 constitution）称为 **Steering Files**，是 `.kiro/steering/` 目录下的 markdown 文件。工作方式：

- 文件在 Requirements、Design、Tasks 生成时自动注入上下文
- 内容：编码标准、库偏好、架构约束、团队规范
- 作用范围：可配置（特定阶段 / 特定文件类型 / 全局）

与 BMAD constitution 对比：
- Kiro Steering Files 有**作用范围元数据**（`alwaysApply: true` 或按 glob 匹配），BMAD constitution 无此粒度
- 效果一致：都是在 agent 生成每个 artifact 时把约束 prepend 到 context

#### 关键工程设计

🟢 **Quick Plan vs 标准路径的分叉**：这是 Kiro 最有工程价值的设计——对**边界清晰的功能**用 Quick Plan 跳过所有门控（用户上前答几个问题，一次生成三个 artifact），对**复杂/有争议的功能**用标准路径逐阶段审批。这解决了"门控太多 = overhead 太高"vs"无门控 = 失控"的经典张力。

🟢 **任务依赖 DAG**：Tasks 阶段 Kiro 自动构建任务依赖图，并行运行独立任务。这把 BMAD 手动拆 milestone 的工作自动化了。

---

### 1.3 OpenSpec（Fission-AI）：Artifact-Graph + Schema 可定制 + 防过度产 markdown

🟢 **SHIPPED — OpenSpec（@fission-ai/openspec，npm，2025 年主流 SDD 工具，>1k stars）**

一手来源：`~/Repos/opensource-hub/OpenSpec/` 本地源码（真实阅读）

#### 流程结构

OpenSpec 的核心是 **Artifact Dependency Graph**——显式声明每个 artifact 的 `requires` 依赖，用 Kahn's 算法求拓扑序，agent 按依赖顺序生成。

```yaml
# schemas/spec-driven/schema.yaml（实际源码）
artifacts:
  - id: proposal      # requires: []  → 根节点
  - id: specs         # requires: [proposal]
  - id: design        # requires: [proposal]
  - id: tasks         # requires: [specs, design]  → 叶节点，最后生成
apply:
  requires: [tasks]
```

对应的拓扑序：`proposal → specs/design（可并行）→ tasks → apply`

```typescript
// src/core/artifact-graph/graph.ts（实际源码）
getBuildOrder(): string[] {
  // Kahn's 算法 topological sort
  // 确定性：每次都是同一顺序（sorted for determinism）
}
getNextArtifacts(completed: CompletedSet): string[] {
  // 返回"依赖已满足且未完成"的 artifacts = 当前可生成的
}
```

#### 人工介入点

OpenSpec 的人工介入设计是最精细的：

**`/opsx:propose`（默认路径）**：一次生成全部规划 artifact，无中间门控。适合简单功能。

**`/opsx:continue`**：每次只生成"下一个可生成"的 artifact（依赖满足的最近节点）。适合需要逐步审阅的复杂功能。用法：
```
/opsx:continue  →  生成 proposal  →  用户 review/edit  →  /opsx:continue  →  生成 specs  →  ...
```

**依赖作为"可行性门控"而非"强制门控"**：OpenSpec 允许跳过依赖直接生成 artifact，但会显示警告：
```typescript
// src/commands/workflow/instructions.ts（实际源码）
if (isBlocked) {
  console.log('<warning>This artifact has unmet dependencies. Complete them first or proceed with caution.')
  console.log(`Missing: ${missing.join(', ')}`)
}
```
这是"提示性门控"而非"阻断性门控"——用户有权忽略警告继续。这比 BMAD 的硬门控更灵活但更容易滥用。

#### 防过度产 markdown：三个机制

🟢 **机制 1：Schema 控制 artifact 粒度**

每个 artifact 的 `instruction` 字段明确写"几页"、"关注什么"、"不写什么"：

```yaml
# schemas/spec-driven/schema.yaml（实际源码）
- id: design
  instruction: |
    Keep it concise (1-2 pages). Focus on the "why" not the "how" -
    implementation details belong in design.md.
    When to include design.md (create only if any apply):
    - Cross-cutting change or new architectural pattern
    - New external dependency or significant data model changes
    ...
```

注意 `design` 的 instruction 明确列出了**"什么情况下才创建 design.md"**——这是防止每个小 feature 都产一份过度详细设计文档的关键机制。

🟢 **机制 2：`project_context` 标签 + 禁止复制到输出**

```typescript
// src/commands/workflow/instructions.ts（实际源码）
console.log('<project_context>')
console.log('<!-- This is background information for you. Do NOT include this in your output. -->')
console.log(context)
console.log('</project_context>')
```

project config 注入的 context 被包在 `<project_context>` 标签里，并明确指示 agent "这是背景信息，不要输出到 artifact 里"。这直接防止 agent 把 config 内容照抄进生成的 markdown。

🟢 **机制 3：Schema 可自定义 + 规则注入粒度化**

```yaml
# openspec/config.yaml（实际格式）
rules:
  proposal:
    - Include rollback plan
  specs:
    - Use Given/When/Then format for scenarios
  design:
    - Include sequence diagrams for complex flows
```

规则按 artifact 类型注入，不是全局注入。设计 artifact 的规则不会污染 spec artifact 的生成，反之亦然。

#### 关键工程设计

🟢 **Artifact-Graph 是核心抽象**：`ArtifactGraph` 类（实际源码）把"哪些 artifact 应该在什么时候生成"从 agent 逻辑里剥离出来，变成声明式 YAML schema 描述。agent 只需问"当前可生成哪些"，graph 回答，不需要 agent 自己判断顺序。

🟢 **Schema 三层 override**：Project > User > Package built-in（实际源码 `resolver.ts`）。用户可以在项目级别完全自定义流程，而不需要 fork 工具。

🟢 **`/opsx:propose` = 快速路径，`/opsx:continue` = 精细路径**：同一套 artifact graph，两种遍历策略。这与 Kiro 的 Quick Plan vs 标准路径是同构设计，独立收敛到了同一结论。

---

## 2. 三产品对比表

| 维度 | BMAD | Kiro | OpenSpec |
|------|------|------|----------|
| **spec→design 阶段分离** | 强分离（不同 agent） | 弱分离（同流程不同步骤） | 声明式依赖分离（`requires`） |
| **人工门控** | 硬门控（阻断式） | 可选门控（Quick Plan 跳过） | 提示性门控（可忽略警告） |
| **偏好注入** | constitution.md（全局） | Steering Files（有范围元数据） | config.yaml rules（per-artifact） |
| **artifact 结构** | PRD + Architecture + Epics/Stories | requirements.md + design.md + tasks.md | schema.yaml 声明的 DAG |
| **编排主体** | 角色化 agent（Analyst/PM/Architect） | 单 agent（Kiro agent）分阶段 | 单 agent 按 graph 遍历 |
| **防过度产 markdown** | 无显式机制 | 无（依赖 Steering Files 约束） | 有（per-artifact instruction + context 标签） |
| **快速路径** | 无 | Quick Plan | `/opsx:propose`（one-shot） |
| **依赖追踪** | 无（靠 `bmad-help` 导航） | Tasks 阶段有 DAG | 全阶段 DAG |
| **自定义程度** | 高（34+ workflows 可组合） | 低（Steering Files 级别） | 高（Schema YAML 完全自定义） |

---

## 3. 黑盒 CAN / CANNOT

### CAN（纯文本进出可落地）

| 做法 | SHIPPED 来源 | 黑盒可行性 |
|------|-------------|------------|
| **Artifact Dependency Graph**（声明式依赖顺序） | OpenSpec `schema.yaml` + Kahn 算法 | ✅ 确定性代码，不依赖 LLM |
| **per-artifact instruction**（每阶段专属 prompt） | OpenSpec `schema.yaml` instruction 字段 | ✅ 纯 prompt engineering |
| **Quick Plan vs 精细路径分叉** | Kiro + OpenSpec 独立收敛 | ✅ 用户选择策略，不需要 LLM 判断 |
| **`project_context` 标签**（背景信息 vs 输出内容分离） | OpenSpec `instructions.ts` | ✅ 纯 prompt XML 标签 |
| **`bmad-help` 导航**（完成后自动推荐 next action） | BMAD | ✅ 确定性规则 |
| **per-artifact rules**（偏好注入粒度化到 artifact 类型） | OpenSpec config.yaml | ✅ 纯 context 注入 |
| **design.md 条件生成**（仅满足条件才创建） | OpenSpec `design` artifact instruction | ✅ prompt 约束 |
| **`decision-log.md` 落盘** | BMAD | ✅ 文件化 artifact |
| **EARS 格式需求**（`WHEN...THE SYSTEM SHALL`） | Kiro | ✅ 结构化 prompt template |

### CANNOT（需要黑盒之外的能力）

| 做法 | CANNOT 原因 | 黑盒替代 |
|------|-------------|---------|
| **任务依赖 DAG 自动构建**（Kiro Tasks 阶段） | 需要理解代码语义 + 准确依赖分析 | 人工在 design.md 手写依赖 |
| **codebase 自动分析**（Kiro Design 阶段） | 可以做，但准确率不稳定 | 强制 agent 做 §3.0 调研 + 人工核对现状摘要 |
| **需求一致性自动检查**（Kiro Requirements 阶段） | 可以 prompted，但无统计保证 | prompted critic agent 做语义冲突检查 |
| **Schema 级别 agent 记忆**（agent 跨 artifact 自动学习偏好） | 需要 procedural memory 系统 | 人工维护 config.yaml/constitution.md |

---

## 4. 对本 unit 的可操作建议

### 4.1 直接可搬的设计

**建议 A：建立 Artifact DAG，声明依赖顺序**

三个产品独立收敛到同一结论：用显式 DAG 控制 artifact 生成顺序，不依赖 agent 判断"接下来应该做什么"。

本 unit 已有 `change-spec-author → change-design-author → change-orchestrator` 的顺序流水线，这已经是隐式 DAG。可操作化为：

```yaml
# 概念上的 unit lifecycle graph
artifacts:
  spec:     requires: []
  design:   requires: [spec]
  tasks:    requires: [design]   # milestone 目录骨架
  impl:     requires: [tasks]
  review:   requires: [impl]
```

对应已有 skill 的门禁 1（spec 完成）→ 门禁 2（design 完成）→ 门禁 3（impl 完成）是同构的，不需要新增基础设施，只需让 spec-agent / design-agent 明确知道它们的"前置检查"和"后置产物"。

**建议 B：Quick Plan vs 精细路径分叉（现在缺失）**

Kiro + OpenSpec 独立收敛的结论：**对简单变更提供 one-shot 路径**，跳过逐步门控。

当前 spec-author 要求逐问澄清（1次1问），对 bugfix-lite 已有快车道（fix.md 两段），但 feat/refactor 路径没有。可以加：
- **简单 feat 快车道**：brief 足够清晰时（用户说"就这样，你理解对了"），spec-agent 可 one-shot 生成完整 spec.md，跳过逐问澄清，让用户整体 review 再修改。这与 OpenSpec `/opsx:propose` 同构。
- **复杂 feat 精细路径**：保留现有逐问澄清。

切换判断：可以在 spec-agent 开始时问用户："需求描述已经很清晰，我直接起草完整 spec 让你 review？还是逐步确认？"——由用户选，不由 agent 判断。

**建议 C：per-artifact instruction 明确写"不写什么"**

OpenSpec 的 `design` artifact instruction 明确列出"什么情况下才创建 design.md"。nano-multiagent 的 design-author skill 已有类似逻辑（§4.1 默认单 M1，§4.2 拆分要举证），可以进一步强化：

在 `design-author` skill 开头加"当以下条件任一不满足时，design.md 只需 1 页"的清单，防止 agent 为简单 unit 产出 10 页过度设计。

**建议 D：`<project_context>` 标签分离**

OpenSpec 把 config context 包进 `<project_context>` 标签，明确告诉 agent "这是背景，不要输出"。

spec-author 和 design-author 加载 AGENTS.md / SPEC.md 做背景调研时，可以把这些文档包在 `<background_context>` XML 标签里，并在 system prompt 里说明："这些标签内的内容是你的背景知识，不要引用或抄进输出 artifact"。防止 agent 把架构文档内容照抄进 spec.md。

**建议 E：`decision-log.md` 落盘澄清记录（BMAD 做法）**

BMAD 把决策理由独立落 `decision-log.md`，而不是埋在 PRD 里。

nano-multiagent 的 spec-author 已把澄清记录 Q/A 写进 spec.md。可以考虑把**架构决策的"拒绝理由"**（设计阶段的"选了 A 而非 B/C"）独立成 `decision-log.md` 或 design.md 的 `## Rejected Alternatives` 段，让后续维护者查阅历史决策不需要读完整个 design 文档。

### 4.2 什么先别做

**不要试图用 LLM 自动构建任务 DAG**（Kiro Tasks 阶段的依赖分析）。Kiro 的做法已经是 shipped 的，但对"spec→design"这种开放式规划任务，依赖分析准确率不稳定，自动化会引入隐性错误。坚持人工 milestone 拆分（design-author §4 的逻辑），代价是多一次人工确认，但对齐质量更高。

**不要上 Steering Files 粒度化的偏好注入**（目前阶段）。Kiro 的 Steering Files 和 OpenSpec 的 per-artifact rules 都是在 constitution/AGENTS.md 之上加一层 per-artifact 粒度控制。当前 spec-author / design-author 已经通过 system prompt 分离实现了"不同阶段不同约束"，不需要再加 infrastructure 层。等 constitution 被证明不够用再加。

**不要用 EARS 格式强制 requirements**。Kiro 用 EARS 格式（`WHEN...THE SYSTEM SHALL`）结构化需求，但 nano-multiagent 已有更完整的 Requirement/Scenario 结构（带 GIVEN/WHEN/THEN，有层级），功能上 superset of EARS，不需要迁移格式。

### 4.3 一个新发现：spec-agent 和 design-agent 需要共享"现状摘要"artifact

BMAD 的 Analyst → PM → Architect 流水线里，Analyst 的产物（research docs）会被后续角色读取。OpenSpec 的 proposal → specs → design 依赖链里，每个后续 artifact 的 instruction 都说"从 proposal 读 why，从 specs 读 what，再写 how"。

nano-multiagent 当前 spec-author 产出的 spec.md 包含"用户场景 + 验收标准 + 范围"，但**不包含代码仓现状分析**——design-author 的 §3.0 调研在 design 阶段做，产出"现状摘要"贴在 design.md 里。

这造成一个隐性问题：如果后续引入**自动化 spec-agent**，spec 阶段的问题可能是"这个需求和现有代码结构能对接上吗"——而 spec-agent 不知道代码现状，设计出来的 spec 可能在 design 阶段被发现"现有架构根本跑不通"（design-author §3.0.4 已有对应退出逻辑），然后被打回。

可操作改进：在 spec-author 的 §3.1 加**轻量代码仓探测**（只读 AGENTS.md / 顶层 SPEC.md，不看具体实现），把"本 unit 涉及哪个包 / 有无相关已有能力"加进 spec.md 的 `## 现状概览（轻量）` 段。这段在 design-author 会被 §3.0 详细调研覆盖，但能让 spec 阶段更快识别"不可能的需求"。

---

## 5. 诚实的 Reality Check

**BMAD 的主要问题是 markdown 爆炸**。`bmad-prd` 生成的 PRD 加 `decision-log.md` 加 architecture doc 加 epics + stories，一个功能可以产出 10+ 个 markdown 文件。社区反馈和 BMAD 文档本身都承认这一点——`bmad-help` 工具存在的部分原因就是帮用户在 markdown 文件丛林里找方向。

**Kiro Quick Plan 是"必要之恶"的工程妥协**。Quick Plan 一次生成三个 artifact 跳过门控，本质上是承认"对于 80% 的常见 feature，逐步门控 overhead > 价值"。这和 nano-multiagent 现有 spec-author 的逐问澄清路径是设计矛盾的——后者对每个功能都强制对话。Kiro 的做法提醒我们：**门控应该和变更复杂度匹配**，不是所有功能都值得 5 轮澄清。

**OpenSpec 的 Artifact-Graph 是最干净的工程抽象**，但它解决的问题是"顺序控制"，不是"质量控制"。artifact 按依赖顺序生成不等于生成的 artifact 质量够好。OpenSpec 对 spec/design 质量没有内置的 critic 机制，用户需要自己判断"这个 design.md 够不够用"。nano-multiagent 的 design-author §5 整体自检是 OpenSpec 没有的。

**三产品都没有解决"判断用户意图是否已经足够清晰"这个问题**。BMAD 靠 PM agent 的对话捕捉，Kiro 靠 Quick Plan 上前的几个问题，OpenSpec 完全靠用户自己判断。这是"spec 阶段 human-on-the-loop 的核心挑战"——如何让 agent 知道"brief 还不够"vs"已经可以起草了"。nano-multiagent spec-author 的"一轮一问 + 停止条件（§3.3）"是目前三产品里最工程化的解法，但仍然依赖 agent 的判断，没有可操作的量化标准。

---

## 6. 必读一手来源

| 来源 | 路径/链接 | 为什么读 |
|------|-----------|---------|
| **OpenSpec schema.yaml** | `~/Repos/opensource-hub/OpenSpec/schemas/spec-driven/schema.yaml` | artifact DAG 的完整实现，per-artifact instruction 写法的最佳范例 |
| **OpenSpec instructions.ts** | `~/Repos/opensource-hub/OpenSpec/src/commands/workflow/instructions.ts` | `<project_context>` 标签分离机制，输出 artifact 结构 |
| **OpenSpec ArtifactGraph** | `~/Repos/opensource-hub/OpenSpec/src/core/artifact-graph/graph.ts` | Kahn 算法拓扑排序 + getNextArtifacts 实现 |
| **BMAD 文档** | docs.bmad-method.org/tutorials/getting-started | Phase 1-3 的完整编排，`bmad-help` 导航机制，decision-log |
| **Kiro 官网** | kiro.dev/docs/specs/ | Quick Plan vs 标准路径，Steering Files，任务依赖 DAG |
