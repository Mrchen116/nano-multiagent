# open-gsd/gsd-core 深挖报告

> **服务目标**：直接服务于 feat-397 unit  
> **本轮命题**：gsd-planner 的 goal-backward 规划实现如何防止 spec-author 的 objective-satisfied-early-stop 失败模式  
> **代码库路径**：`/tmp/claude-feat397-r3/05-open-gsd-gsd-core`（git clone --depth 1）  
> **标注纪律**：🟢SHIPPED（生产中运行）/ 🟡RESEARCH（仅论文）  
> **完成日期**：2026-06-04

---

## 0. 定性总结

🟢SHIPPED — gsd-core 是一个**可安装的 npm 包**（`@opengsd/gsd-core`，GitHub 有 CI badge、npm 版本徽章、Discord），在 Claude Code / Codex / Cursor / Windsurf 等多个 coding agent runtime 上真实运行。它的 planning 流水线直接对应本命题关心的 spec/design 失败模式，且全部机制在黑盒 LLM 下可落地。

---

## 1. 该源针对的 spec/design 失败模式与 multi-agent 结构

### 1.1 直接对应的失败模式

#### 失败模式 A：Objective-Satisfied-Early-Stop（目标满足即止）

单 agent 一旦生成了看起来"合理"的 spec/plan，就会停止深挖——因为 objective 已经"满足"了。没有独立视角来质疑"这个 plan 真的能达成目标吗？"

**gsd-core 的补法：Goal-Backward 方法论 + 独立 plan-checker agent**

gsd-planner 强制执行一套 5 步 goal-backward 协议（`agents/gsd-planner.md` L551-642）：

```
Step 1: State the Goal → outcome-shaped，不是 task-shaped
        Good: "Working chat interface"（结果）
        Bad:  "Build chat components"（任务）

Step 2: Derive Observable Truths → "目标达成的必要条件是什么？"
        为"working chat interface"列出 3-7 条用户视角可验证的事实
        测试标准：每条都能由人使用应用来核实

Step 3: Derive Required Artifacts → 为每条 truth：什么文件必须存在？

Step 4: Derive Required Wiring → 为每个 artifact：什么连接必须建立？

Step 5: Identify Key Links → 哪里最可能断裂（级联失败点）
```

这些 truths 作为 `must_haves.truths[]` 落入 PLAN.md frontmatter，成为下游 plan-checker 的检验锚点。关键设计：**truths 来自"用户视角可验证的结果"，不是"开发者视角的任务完成"**——这直接对抗 early-stop：agent 不能声称"创建了认证端点"就算 done，必须证明"用户可以用有效凭据登录"。

随后，一个**独立的 gsd-plan-checker agent 在新 context 窗口里**从目标反向审查计划：

```
"Plan completeness ≠ Goal achievement"
"A task 'create auth endpoint' can be in the plan while password hashing is missing."
```

gsd-plan-checker 的 adversarial_stance 节（`agents/gsd-plan-checker.md` L29-43）明确要求：
- 出发假设：**这套计划无法交付目标**（除非有证据证明相反）
- 每个 issue 必须标 BLOCKER / WARNING，不允许无 severity 的模糊输出
- 禁止"接受听起来合理的任务列表而不追溯每条 truth"

#### 失败模式 B：单视角／无对抗压力（无独立 critic）

单 agent spec/design 因为出发目标一致、无认知多样性，无法可靠自我批判。

**gsd-core 的补法：Generator-Critic 拓扑 + 专职角色分工**

流水线中 4 个专职角色在各自独立 context 中工作，目标互相不同（而非同质辩论）：

| 角色 | 文件 | 核心目标 | 工具限制 |
|------|------|---------|---------|
| gsd-phase-researcher | `agents/gsd-phase-researcher.md` | "What do I need to know to PLAN this phase well?" | Read/WebFetch/Grep（无 Write 到主代码） |
| gsd-planner | `agents/gsd-planner.md` | 生成可执行的 PLAN.md | Read/Write/Bash/Glob |
| gsd-plan-checker | `agents/gsd-plan-checker.md` | 验证计划**能否**达成目标（事前，不是事后） | Read/Bash/Glob/Grep（只读） |
| gsd-verifier | `agents/gsd-verifier.md` | 验证代码**是否**达成目标（事后） | Read/Bash/Glob/Grep（只读） |

这不是"同质辩论"（uniform debate），而是**基于阶段、工具和职责的非对称分工**：researcher 不规划、planner 不验证、checker 不写代码。认知目标不同，自然形成对抗压力。

#### 失败模式 C：Scope Reduction 悄然发生（agent 私自降标）

单 agent 面对复杂需求，会用"v1"、"simplified version"、"hardcoded for now"悄然缩小范围，而不通知委托方。

**gsd-core 的补法：Scope Reduction Prohibition + 多源覆盖审计**

gsd-planner 有明文禁止列表（`agents/gsd-planner.md` L76-107）：

```
PROHIBITED language in task actions:
- "v1", "v2", "simplified version", "static for now"
- "future enhancement", "placeholder", "basic version"
- "will be wired later", "dynamic in future phase"
```

同时强制执行**四源覆盖审计**（Multi-Source Coverage Audit）：

```
SOURCE    | ID     | Feature/Requirement         | Plan | Status   | Notes
GOAL      | —      | {phase goal from ROADMAP}   | 01   | COVERED  |
REQ       | REQ-14 | OAuth login                 | 02   | COVERED  |
RESEARCH  | —      | Refresh token rotation      | NONE | ⚠MISSING | No plan covers this
CONTEXT   | D-01   | Use jose for JWT            | 02   | COVERED  |
```

任何 `⚠ MISSING` 项必须上报 orchestrator 并给出三个选项（加入计划 / 拆分阶段 / 明确推迟），**不允许沉默遗漏**。Planner 唯一合法的拆分理由是三个约束（context 成本超限 / 信息缺失 / 依赖冲突），"功能太难"不是合法理由。

#### 失败模式 D：Context 装不下"全局产品+深度架构+调研"

单 agent 试图在同一 context 窗口中完成调研 + 决策对齐 + 规划，必然顾此失彼。

**gsd-core 的补法：Fresh ~200K Context 隔离机制**

README 明确表述其核心价值主张："solves context rot — the quality degradation that accumulates as an AI fills its context window — by running all heavy research, planning, and execution work in fresh-context subagents while keeping your main session lean."

具体实现（`gsd-core/workflows/plan-phase.md`）：

1. orchestrator 只持路径引用，不在自身 context 中加载大文件（universal-anti-patterns 规则 2："Never inline large files into subagent prompts — tell agents to read files from disk")
2. 每个阶段 spawn 一个新 agent（`Agent(prompt=..., subagent_type="gsd-phase-researcher")`），该 agent 在独立 context 窗口中读取需要的文件
3. orchestrator 规则："After calling Agent() above, stop working on this task immediately. Do not read more files... Only resume when the subagent result is available." 防止 orchestrator 上下文被 subagent 结果污染
4. context_window 配置驱动深度：< 500K 只读 frontmatter，≥ 500K 允许全文读取

这样每个 subagent 拿到的是 **clean ~200K** 窗口，不携带前序对话的"尾巴"。

#### 失败模式 E：无独立决策 checkpoint，人无插手点

单 agent 会在无人审核下完成大段规划，等用户拿到结果时已经构建在有问题的假设上。

**gsd-core 的补法：三阶段人介入结构（见第 2 节）**

### 1.2 多 agent 拓扑结构

gsd-core 的 spec/planning 层拓扑：

```
用户 brief + ROADMAP.md
      │
      ▼
[Orchestrator: /gsd:discuss-phase]
  • 识别"灰色地带"（实现决策的模糊点）
  • 人机对话，逐项捕捉决策
  • 禁止 scope creep（新能力→backlog，不扩张当前 phase）
  • 输出：CONTEXT.md（locked decisions / deferred / claude's discretion）
      │
      ▼
[Subagent: gsd-phase-researcher]  ← 独立 context 窗口
  • 目标："我需要知道什么才能规划好这个阶段？"
  • 读 CONTEXT.md（用户决策）+ REQUIREMENTS.md + STATE.md
  • 输出：RESEARCH.md（技术方案、约束、包合法性审计）
      │
      ▼
[Subagent: gsd-planner]  ← 独立 context 窗口
  • 输入：CONTEXT.md + RESEARCH.md + REQUIREMENTS.md + ROADMAP.md
  • 执行 goal-backward 5步：Truths → Artifacts → Wiring → Key Links
  • 执行四源覆盖审计（GOAL/REQ/RESEARCH/CONTEXT）
  • 输出：PLAN.md（含 must_haves frontmatter）
      │
      ▼ （revision loop，最多 3 轮）
[Subagent: gsd-plan-checker]  ← 独立 context 窗口
  • adversarial 出发假设："计划无法交付目标"
  • 7 维度检查：Requirement Coverage / Task Completeness / 
    Context Compliance / Goal Achievement / Artifact Reachability /
    Scope vs Budget / Threat Model
  • 每条 issue 必须标 BLOCKER/WARNING
  • 输出：VERIFICATION PASSED / ISSUES FOUND（触发 revision loop）
      │
      ▼ （若 3 轮后仍有 blockers）
[Escalation Gate → 人]
  • 呈现剩余 issues，询问 "Proceed anyway" / "Adjust approach"
```

这是**非对称顺序拓扑**（非 debate 环），每个节点不同目标、不同工具集、不同 context，从根本上避免了 Martingale Curse（同质 agent 无法通过辩论提升正确率）。

---

## 2. 人留在哪

gsd-core 对人介入点设计非常精确，分三层：

### 2.1 /gsd:discuss-phase —— 决策捕捉层（强制人在环）

这是唯一一个不以 subagent 模式运行、而是直接与用户交互的阶段。

**人必须决策的内容：**
- 实现灰色地带（多条路都走得通的选择，如"分页 vs 无限滚动"）
- 哪些是 locked decisions（D-NN），哪些推迟，哪些交给 Claude 自决
- 不在阶段范围内的新想法 → deferred backlog（不由 agent 决定是否纳入）

**关键设计：** `/gsd:discuss-phase` 明确区分"user = visionary/product owner"和"Claude = builder"——"Ask about vision and implementation choices. Capture decisions for downstream agents."用户不应被问关于 codebase 模式（researcher 负责）或技术风险（researcher 负责）的问题。

### 2.2 /gsd:plan-phase —— 规划 checkpoint（选择性人在环）

以下情况 orchestrator 会暂停并升级给人：

| 触发条件 | 升级方式 |
|---------|---------|
| `CONTEXT.md` 不存在 | 询问"继续还是先 discuss-phase" |
| `## PHASE SPLIT RECOMMENDED`（planner 判断 context 超限） | AskUserQuestion：如何拆分 sub-phases，用户批准后才继续 |
| `## ⚠ Source Audit: Unplanned Items Found` | 给出 3 个选项（加计划/拆阶段/推迟），等用户决定 |
| revision loop 3 轮后仍有 BLOCKER | `Proceed anyway` vs `Adjust approach`，明确等人裁决 |
| 发现 `[ASSUMED]/[SUS]` 包（安全门控） | 强制 `checkpoint:human-verify` 任务，阻断自动批准 |

### 2.3 任务级 checkpoint（执行期）

计划里的任务有四种类型，后三种均暂停等人：
- `auto`：完全自主
- `checkpoint:human-verify`：Claude 自动化完成，人确认结果
- `checkpoint:decision`：实现中遇到选择点，人做决策
- `checkpoint:human-action`：真正无法自动化的手工步骤（罕见）

**设计原则：** "Automation-first rule: If Claude CAN do it via CLI/API, Claude MUST do it. Checkpoints verify AFTER automation, not replace it."——人不被用于替代可自动化的工作，只在"需要视觉确认 / 需要决策 / 无法自动化"时介入。

---

## 3. 黑盒 CAN / CANNOT

| 机制 | CAN/CANNOT | 理由 |
|-----|-----------|------|
| Goal-backward truths 生成（LLM 从目标推逆）| **CAN** | 纯文本推理，无需 logit 访问 |
| 四源覆盖审计（GOAL/REQ/RESEARCH/CONTEXT）| **CAN** | 文本匹配 + LLM 判断，无需训练 |
| gsd-plan-checker adversarial stance | **CAN** | System prompt 注入；独立 context |
| Revision loop（最多 3 轮，stall 检测）| **CAN** | 纯 orchestration 逻辑 |
| Fresh context 隔离（每个 subagent 新窗口）| **CAN** | Agent() spawn，标准 Claude Code API |
| Locked decisions 追溯（D-NN citation）| **CAN** | 文本格式约束 + 正则检查（gsd-tools.cjs）|
| Scope Reduction Prohibition | **CAN** | System prompt 禁用词列表 |
| 人机交互 checkpoint（AskUserQuestion）| **CAN** | Claude Code 原生 TUI |
| Stall detection（issue count 不降即升级）| **CAN** | 数值比较，deterministic |
| User profiling（8 维度行为分析）| **CAN** | 文本分析，无需模型访问 |
| Logit-based conformal prediction（KnowNo 原版）| **CANNOT** | 需 next-token probability |
| Fine-tune / RLHF 偏好学习 | **CANNOT** | 需训练访问 |
| 解码层干预（Drift/AMULET/T-POP）| **CANNOT** | 需 logit 访问 |

全部核心机制均为 **CAN**。gsd-core 的设计本身就是为黑盒 LLM runtime（Claude Code / Codex / Cursor）设计的，不依赖任何 logit 或训练访问。

---

## 4. 🟢SHIPPED 证据

- **谁**：open-gsd 组织（GitHub: `https://github.com/open-gsd/gsd-core`）
- **在哪**：npm 包 `@opengsd/gsd-core`，有版本徽章（CI passing）、npm downloads 徽章、Discord 社区
- **支持的 runtime**：Claude Code、OpenCode、Gemini CLI、Kilo、Codex、Copilot、Cursor、Windsurf
- **规模指标**：83KB 的 `execute-phase.md`、85KB 的 `plan-phase.md`、47KB 的 `gsd-planner.md`——这是有大量真实使用积累后的复杂工程产物，不是 demo
- **核心设计决策有 PR 编号追溯**：`#3569`（closed-phase gate）、`#3042`、`#3045`、`#3718` 等——证明是有用户 issue 驱动演化的真实产品

**标注：🟢SHIPPED**

---

## 5. 对 feat-397 实现的直接可搬内容

### 5.1 Goal-Backward Truths 作为 spec 断言锚

**直接可搬。** gsd-core 的 must_haves.truths 格式可原样迁移为 spec-author 的必填输出格式：

```yaml
must_haves:
  truths:
    - "[用户视角可验证的结果 1]"
    - "[用户视角可验证的结果 2]"
  artifacts:
    - path: "src/..."
      provides: "..."
  key_links:
    - from: "..." to: "..." via: "..."
```

这解决了 spec-author 的 early-stop 问题：**truths 是 spec 完整性的可检验锚**，spec-verifier 可以逐条询问"这条 truth 在 spec 的哪个需求里被覆盖了？"

### 5.2 四源覆盖审计框架

**直接可搬。** 把 gsd-core 的四源（GOAL/REQ/RESEARCH/CONTEXT）映射到 feat-397 的输入：

| gsd-core 源 | feat-397 对应 |
|------------|-------------|
| GOAL（ROADMAP goal） | brief 的核心目标陈述 |
| REQ（REQUIREMENTS.md）| spec 中的功能需求条目 |
| RESEARCH（RESEARCH.md）| design-author 的架构调研结果 |
| CONTEXT（D-XX decisions）| 澄清环节中用户锁定的决策 |

每次 spec-author 完成后，独立 spec-checker 运行四源扫描，任何 MISSING 行必须上报，不允许沉默遗漏。

### 5.3 Locked Decisions 追溯机制（D-NN citation）

**直接可搬。** 用户在 spec 对齐环节做的每个明确决策赋予 ID（D-01, D-02...），后续 design 文档中必须 cite 对应 ID。独立 checker 验证"每个 D-NN 至少有一个 design 决策覆盖它"。这使得用户决策的追溯从隐性变为可机械检验。

### 5.4 Generator-Critic 顺序对 + Revision Loop（最多 N 轮）

**直接可搬。** 

```
spec-author → spec-checker（BLOCKER/WARNING）→ 
  [if issues]: spec-author revision（带 checker feedback 的新 spawn）→ 
  [max 3 iterations] → stall detection → escalate to human
```

stall detection（"issue count 不降则升级"）是防止无限循环的关键——gsd-core 在 `references/revision-loop.md` 中有完整实现模式。

### 5.5 Scope Creep 防护（Scope Guardrail）

**直接可搬。** `discuss-phase.md` 中的 scope guardrail 对 spec-author 同样适用：

```
Allowed: "How should posts be displayed?" (clarify HOW within phase)
Not allowed: "Should we also add comments?" (new capability → deferred backlog)
```

spec-author 应有明文规则：当 brief 隐含超出 scope 的功能时，捕捉为"Deferred Ideas"而不是悄然纳入 spec，也不丢弃——这直接对抗了"agent 私自扩张/删减 scope"的失败模式。

### 5.6 Fresh Context 隔离作为一等公民

**设计原则可搬。** gsd-core 最核心的工程哲学：orchestrator 只路由、不执行，每个重工作在新 context 的 subagent 里完成。对 feat-397 意味着：

- spec-author、design-author、spec-checker、design-checker 每个都在**独立 context 窗口**中启动
- orchestrator 只传文件路径引用，不内联大文件
- context_window 配置驱动深度（< 200K 只读摘要，≥ 200K 全文）

---

## 6. 与前两轮报告的关系

| 前两轮已确立 | gsd-core 新增的精确机制 |
|------------|----------------------|
| Generator-Critic 顺序对 🟢 | plan-checker 的 adversarial_stance（出发假设"无法交付目标"）+ BLOCKER/WARNING 分类强制 |
| 独立 context 窗口 🟢 | orchestrator 规则"After calling Agent(), stop working"——防止 orchestrator 上下文被 subagent 结果污染 |
| Artifact 文件传递（文件即记忆）🟢 | CONTEXT.md 作为 locked decisions 的单一来源，下游 agent 不允许重新辩论已锁定决策 |
| ExitPlanMode human choke point 🟢 | 三层人介入结构（discuss/plan checkpoint/task checkpoint），精确区分"人做决策"vs"人确认结果"vs"人做手工操作" |
| EARS 结构化语法 🟢 | gsd-core 的 truths 格式（可验证的用户视角陈述）是同等效果的结构化锚，且无需 WHEN...SHALL 语法学习曲线 |
| Four-role pipeline（MetaGPT 消融）🟡 | gsd-core 实现了 5+ 专职角色，但设计上避免了 MetaGPT 的"水平层"问题——Researcher/Planner/Checker 是**不同目标的对抗关系**，不是分工合作的同质流水线 |

---

## 7. 关键文件路径索引

| 文件 | 内容摘要 |
|------|---------|
| `agents/gsd-planner.md` L551-642 | goal-backward 5步方法论完整实现 |
| `agents/gsd-planner.md` L76-107 | scope reduction prohibition + 四源覆盖审计规范 |
| `agents/gsd-plan-checker.md` L29-43 | adversarial stance + BLOCKER/WARNING 强制分类 |
| `agents/gsd-plan-checker.md` L81-102 | "Plan completeness ≠ Goal achievement" 核心原则 |
| `gsd-core/workflows/plan-phase.md` L1-50 | orchestrator 初始化 + 4 个 subagent 角色声明 |
| `gsd-core/workflows/plan-phase.md` L483-530 | researcher spawn + "stop working" orchestrator 规则 |
| `gsd-core/workflows/plan-phase.md` L1162-1214 | PHASE SPLIT 和 Source Audit 升级给人的 escalation 逻辑 |
| `gsd-core/workflows/discuss-phase.md` L46-74 | scope guardrail + "user = visionary, claude = builder" 哲学 |
| `gsd-core/references/revision-loop.md` | Check-Revise-Escalate 模式 + stall detection 完整实现 |
| `gsd-core/references/gates.md` | Pre-flight / Revision / Escalation / Abort 四类 gate 分类 |
| `gsd-core/references/planner-source-audit.md` | 四源审计表格格式 + gap 处理规则 |
| `gsd-core/references/thinking-models-planning.md` | Pre-Mortem / MECE / Constraint Analysis 等 6 个结构化推理模型 |
| `gsd-core/references/universal-anti-patterns.md` | 跨所有工作流的通用反模式规则（context budget + subagent + scope） |
