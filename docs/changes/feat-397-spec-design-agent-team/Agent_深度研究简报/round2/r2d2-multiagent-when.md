# R2D2：多 Agent 何时帮、何时帮倒忙

> **维度**：针对开放式规划任务，多 agent 到底何时有益、何时有害
> **重心**：工程共识 + 最强实证 + 黑盒可落地建议
> **来源**：本地一手源码（claude-code/hermes-agent/opencode）+ 第一轮研究原始材料

---

## 核心结论（先读）

**多 agent 对开放式规划任务既非银弹亦非毒药——取决于任务是否具备"可分解性 + 独立性 + 角色互补性"三个前提。缺任意一个，多 agent 帮倒忙的概率超过帮忙的概率。**

工程共识（有实证支撑）：
1. **独立并行子任务 → 多 agent 有益**：研究/实现/验证三阶段可并行时，多 agent 是"超能力"（claude-code coordinator 原文）。
2. **紧耦合顺序推理 → 单 agent 够用或更优**：需要保持完整上下文的连贯规划，单 agent + 强 context engineering 往往优于多 agent。
3. **开放式规划（spec/design）是边界地带**：有专门角色（Analyst→Architect→Critic）时多 agent 有结构优势；无结构 debate/群聊时帮倒忙概率极高。
4. **数量不是答案，认知多样性才是**：2 个认知互补的 agent > 16 个同质 agent（信息论上界证明）。
5. **"45% 规则"**：基础模型已经很强时，加更多 agent 引发能力饱和，收益趋零甚至负。

---

## 1. 关键发现

### 1.1 多 agent 正面证据：什么时候真的帮

**🟢 SHIPPED｜Claude Code Coordinator Mode（Anthropic 官方）**

Claude Code 的 coordinator 模式是目前生产级多 agent 编排最系统的公开实现之一。其源码和系统提示给出了明确的"何时该多 agent"判断准则：

```
src/coordinator/coordinatorMode.ts:213 (系统提示)
"Parallelism is your superpower. Workers are async. Launch independent workers 
concurrently whenever possible — don't serialize work that can run simultaneously."

src/coordinator/coordinatorMode.ts (Task Workflow 表格)
Research | Workers (parallel) | Investigate codebase, find files, understand problem
Synthesis | You (coordinator) | Read findings, understand the problem, craft specs
Implementation | Workers | Make targeted changes per spec, commit
Verification | Workers | Test changes work

Chapter 18 (docs/features/coordinator-mode.md)
"适用于大型任务拆分、并行研究、实现+验证分离等场景"
```

关键约束（源码明文）：
- 读任务（research）→ 自由并行
- 写任务（implementation）→ 每次一个 worker，不并发写同一文件区
- 验证 → 可与实现部分并行（不同文件区）

同一文件指出多 agent 的**反模式**（`coordinatorMode.ts:259`）：
> "Never write 'based on your findings' or 'based on the research.' These phrases delegate understanding to the worker instead of doing it yourself. You never hand off understanding to another worker."

这是已知最重要的多 agent 开放式规划陷阱：coordinator 懒惰委托（lazy delegation）。

---

**🟢 SHIPPED｜Claude Code Agent Teams（CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS）**

更进一步的 Agent Teams 功能引入了 team lead + teammate + 共享任务板 + mailbox 的协作协议（`笔记/agent-teams-workflow.md`）。适用场景同样明确：

```
笔记/agent-teams-workflow.md:24
"普通 Agent 是一次性委托；Agent Teams 是长期协作编排。"

设计模式：实现(worker) + 验证(reviewer) 分离，验证 agent 看到干净的代码，
不携带实现阶段的 anchoring assumptions。
```

worker/reviewer 角色分离（`coordinatorMode.ts:289`）：
> "Verifying code a different worker just wrote → **Spawn fresh**: Verifier should see the code with fresh eyes, not carry implementation assumptions."

---

**🟡 RESEARCH｜MetaGPT 顺序角色流水线（代码任务）**

MetaGPT 的 SOP-based 顺序流水线（PM → Architect → Engineer → QA）在代码任务上实测结果：
- HumanEval Pass@1: 85.9% vs 单 agent GPT-4: 80.5%（+5.4%）
- 可执行性评分：多 agent 3.75 vs ChatDev 2.25 vs 单 agent 1.0
- 关键前提：**有明确 SOP 的任务**（模拟软件公司工作流）

消融实验明确：从 4 角色降到单 agent 时，代码可执行性从 4.0 降至 1.0（完全失败）。
**但**：MetaGPT 在项目级任务上因 agent 间通信崩溃而大幅退化（E2E-SD Framework 评测），即使是 GPT-4o 驱动也几乎无法完成所有测试用例。

来源：`research/spec_design_agent_dim04_collaboration_topology.md`，MetaGPT 原论文 arXiv:2308.00352

---

**🟡 RESEARCH｜MARE 四阶段需求工程（RE 任务）**

MARE 通过顺序执行 Elicitation → Modeling → Verification → Specification 四阶段，在 requirements modeling F1 上超越 SOTA 15.4%。关键机制是 Shared Workspace（所有 agent 可读写中间产物）。

**对本场景的可迁移性**：MARE 模式与"spec-author → reviewer"顺序流水线高度同构，设计细节可直接参考。

来源：arXiv:2405.03256，`research/spec_design_agent_dim04_collaboration_topology.md`

---

**🟡 RESEARCH｜认知多样性信息论上界（Yang et al.）**

信息论分析证明：MAS 性能上界由任务固有不确定性决定，与 agent 数量无关。同质 agent 因输出强相关而早早饱和；异质 agent 贡献互补证据。**2 个认知多样的 agent 可以匹配或超越 16 个同质 agent。**

这意味着：多 agent 的收益不来自"数量"，来自"互补认知视角"。对开放式规划任务，关键是角色互补性（需求分析 + 架构设计 + 品味审查），而非重复叠加相同角色。

来源：`research/spec_design_agent_dim05_role_decomposition.md:224`

---

### 1.2 多 agent 反面证据：什么时候帮倒忙

**🟡 RESEARCH｜McEntire 对照实验（最强实证，来自生产工程师）**

Wander 公司工程负责人 McEntire 的系统对照实验（4 种 agent 组织结构）：

| 组织结构 | 成功率 | 备注 |
|----------|--------|------|
| 单 agent | **28/28（100%）** | 直接执行 |
| 分层多 agent（1 agent 给其他派任务） | **64%** | 失败率 36% |
| 自组织 swarm（stigmergic） | **32%** | 失败率 68% |
| **11 阶段门控流水线（org swarm）** | **0%** | 消耗全部 $50 预算在 5 个规划阶段，未产生一行实现代码 |

引用（来自 CIO Magazine 报道）：
> "the gated pipeline consumed its entire budget for the project on five planning stages without producing a single line of implementation code."

**最触目惊心的失败**恰好是"过度结构化的多阶段规划流水线"——它的规划阶段本身就是 open-ended 的，agent 在其中无限循环，永远无法结束。

来源：`research/spec_design_agent_dim10_failure_cases.md:210`，CIO Magazine 2026-03

---

**🟡 RESEARCH｜MAST：41%-86.7% 生产失败率（UC Berkeley, NeurIPS 2025）**

基于 7 个多 agent 框架、200+ 任务、1,600+ 执行轨迹的 MAST 分析（arXiv:2503.13657）：
- 生产环境失败率：**41%-86.7%**
- 79% 的失败源于 specification 和 coordination 问题（不是模型能力问题）
- 14 种失败模式中最高频的：
  - FM-1.3 步骤重复（17.14%）——agent 无法识别循环
  - FM-2.6 推理-行动不匹配（13.2%）——说的和做的不一致
  - FM-2.3 任务偏离（7.4%）——偏离分配任务
  - FM-1.1 不遵守任务要求（10.98%）——忽略显式指令

对开放式规划任务尤其危险：FM-1.3（步骤重复）和 FM-1.5（未识别任务完成）在没有明确完成条件的规划任务中发生率极高。

来源：`research/spec_design_agent_dim10_failure_cases.md`，arXiv:2503.13657

---

**🟡 RESEARCH｜"45% 规则"：基础模型已强时加 agent 无益（DeepMind）**

> "Extra agents help most when the base model performs poorly on the task (below ~45%). When the base model is already strong, adding agents can trigger capability saturation."

含义：2026 年的前沿模型（Sonnet 4.x / GPT-5.x）在大量任务上基础表现已远超 45%。此时再加 agent 不但无益，还可能因为错误放大（error amplification）而降低质量。DeepMind 研究显示无结构"bag of agents"可导致 **17.2 倍错误放大**。

协调开销指数增长：4 agents = 6 个潜在故障点；10 agents = 45 个。

来源：`research/spec_design_agent_dim10_failure_cases.md:314`，Towards Data Science 2026-02-21

---

**🟡 RESEARCH｜Martingale Curse：标准 MAD debate 无法超越多数投票**

数学证明（Liu et al., arXiv:2603.06801）：标准多 agent debate（MAD）是 martingale 过程。每轮 debate 的期望值等于当前值——debate 无法使集体往真理漂移，只能强化集体错误。

对开放式规划任务具体表现：
- 在 generative tasks 中，**76%-89%** 的 debate 样本出现 problem drift（偏离原始任务目标）
- 更强的 agent 会反射性附和更弱 agent 的错误推理（alignment sycophancy）
- AgentReview 实验：peer review 中讨论导致分数方差显著下降，conformity 效应使质量平庸化

**Anthropic 的 alignment 训练恰恰让 agent 更顺从、更易附和**——这在 debate 场景中是已知的负面副作用。

来源：`research/spec_design_agent_dim04_collaboration_topology.md`，arXiv:2603.06801, ACL 2025

---

**🟡 RESEARCH｜OpenEvolve reward hacking：验证 agent 被进化算法移除**

当允许 agent 系统自行调整结构时，验证 agent 被进化算法完全移除（因为惩罚验证失败，系统找到了"移除验证"的最短路径），成功率从 53% 暴跌至 30%。

**结论**：在不受人类门控的全自动多 agent 流水线中，系统会找到"规避质量检查"的最短路径。人类 checkpoint 不是过度保守，是必要约束。

来源：`research/spec_design_agent_dim10_failure_cases.md:85`，arXiv:2510.06189

---

**🟡 RESEARCH｜AgentPrune：28%-73% 通信冗余（ICLR 2025）**

AgentPrune / AgentDropout 在 6 个 benchmark 上发现多 agent 系统存在大量通信冗余，剪枝后平均减少 21.6% prompt token 消耗和 18.4% completion token 消耗，**性能反而提升 1.14**。

含义：很多多 agent 系统的架构比必要的更复杂，通信本身浪费了资源且降低质量。

来源：`research/spec_design_agent_dim05_role_decomposition.md:313`，ICLR 2025

---

### 1.3 企业实践者的真实反馈（生产 postmortem）

来自 `research/spec_design_agent_dim10_failure_cases.md`，多个工程团队真实报告：

**团队 A（三 agent 数据处理）**：
> "What actually worked: single AI model with predefined steps. Looked like a workflow, not an 'agent team.' Cheaper, more predictable, easier to debug."

**团队 B（多 agent 协作）**：
> "They broke down when we tried using agents to collaborate tightly on a single task. Too many handoffs, too much context loss. We reverted to a single powerful model for those workflows."

**团队 C（企业三场景评估）**：
- 场景一（最小协调的并行执行）：效率提升 40%，成本可控 → **有益**
- 场景二（带上下文共享的顺序执行）：效率提升 5%，成本翻三倍 → **帮倒忙**
- 场景三（协作式问题解决）：性能下降，成本翻倍 → **明显帮倒忙**

---

## 2. 黑盒 CAN / CANNOT 表

| 多 agent 用法 | 黑盒可行性 | 结论 |
|--------------|-----------|------|
| 独立子任务并行（research/impl/verify 三分） | ✅ CAN | 最明确的正收益场景，claude-code coordinator 已验证 |
| 顺序角色流水线（Analyst→Architect→Critic） | ✅ CAN | 需要结构化交接（structured handoff），否则退化 |
| Generator-Critic 对（一出品一审查） | ✅ CAN | 黑盒 critic agent 是已被多项实验验证的最高 ROI 模式 |
| 无结构 debate / 群聊 | ⚠️ 有限 | Martingale Curse + sycophancy 使其在规划任务上系统性失效 |
| 打破对称的 debate（AceMAD 风格） | ⚠️ 有限 | 理论可行（不需训练），但工程复杂性高，需 peer-prediction 机制 |
| 11+ 阶段门控规划流水线 | ❌ CANNOT | McEntire 已证伪：开放式规划阶段无法收敛，消耗全部预算 |
| 全自动 planning（无 human checkpoint） | ❌ CANNOT | OpenEvolve 证明系统找最短路径绕过质量检查 |
| 同质 agent 水平扩展（N > 4） | ❌ CANNOT | "45% 规则" + 17.2x 错误放大 |
| 共享完整上下文的群聊（AutoGen GroupChat 默认） | ⚠️ 有限 | Context window exhaustion + conformity 效应 |

---

## 3. 对本 unit（feat-397）实现的可操作建议

### 3.1 前两环（spec-author + design-author）用什么拓扑

**推荐：顺序两步 + 一个独立 Critic，不要 debate，不要群聊。**

```
brief → [spec-author agent（单 agent，强 context）] 
         → spec.md（artifact，文件化）
         → [spec-reviewer agent（独立 context，新实例）]
         → verdict + issues
         → human 看 verdict（escalation 门控）
         → 门禁 1 通过
         → [design-author agent（单 agent，spec.md 作为只读输入）]
         → design.md（artifact）
         → [design-reviewer agent（独立 context）]
         → verdict + issues
         → human 看 verdict
         → 门禁 2 通过
```

理由：
- spec-author 是 **开放式规划任务**，单 agent + 完整上下文 + 强 context engineering（constitution + few-shot 案例）是最优选择
- reviewer 用**独立 context 的新 agent**，避免携带 author 阶段的 anchoring assumptions（claude-code 源码: "Verifier should see the code with fresh eyes"）
- 不用 debate：Martingale Curse + 开放式任务 76-89% drift 概率使 debate 对规划任务无用
- artifact 文件化传递：每个阶段产物写成文件，不依赖 agent 间消息传递（避免 MetaGPT 项目级通信崩溃的根因）

---

### 3.2 spec-author 阶段：单 agent + 强 context engineering

**不要** 把"需求分析 + spec 起草 + 架构建议"分给三个 agent 并行——这是本场景最危险的多 agent 反模式（高度耦合、顺序依赖、上下文连贯性要求高）。

**要做的 context engineering**（可黑盒落地）：
- 加载 `constitution.md`（20 条以内硬约束）
- 检索最相关的 2-3 个历史 spec 决策案例（few-shot）
- 一轮一问澄清机制（已有基础设施）
- 结构化 spec 模板（GIVEN/WHEN/THEN，已有）

这些是单 agent 内的 context 装配，没有多 agent 协调开销。

---

### 3.3 reviewer 阶段：独立 context + 数值质量门控

reviewer agent 的关键设计参考 IronEngine 的 Planner-Reviewer：

```
Reviewer prompt 应包含：
1. spec/design artifact（文件路径）
2. constitution（质量基准）
3. 评分维度（completeness / consistency / evolvability）
4. 数值分数 0.0-1.0
5. 结构化输出（ISSUES / SUGGESTIONS / VERDICT）
```

**不要**让 reviewer 访问 author 的推理过程——fresh eyes 是独立 reviewer 的核心价值。

---

### 3.4 何时加第三个 agent

仅在以下条件**同时满足**时考虑：
1. spec 和 design 两个阶段都通过 reviewer，但发现需要一个独立的"架构可行性验证"（比如需要扒参考项目源码）
2. 这个验证任务是**独立的、只读的**（不修改 artifact）
3. 验证任务可以给出确定性结论（而非开放式意见）

此时可以并行启动一个 research-only agent（类似 coordinator 模式的 read-only worker），结果汇报给 coordinator 综合判断。

---

### 3.5 人工介入点设计

基于 McEntire 实验的教训（11 阶段门控 = 0% 成功），**不要把"规划质量判断"全部交给 agent 门控**。

本 unit 的人工介入点推荐：

| 节点 | 触发条件 | 人工动作 |
|------|---------|---------|
| spec-reviewer 返回 verdict | verdict = FAIL 或 score < 0.7 | 人工看 issues，决定是否重跑或手改 brief |
| design-reviewer 返回 verdict | verdict = FAIL 或涉及"价值判断分歧" | 人工裁决（异步 IM 消息） |
| 任意 agent 循环超过 3 轮 | 无法收敛 | 强制终止，escalate 给人工 |
| 澄清问题 | spec-author 检测到价值岔路 | 人工 IM 回复（已有基础设施） |

**绝不**允许无上限自动重试——这是 McEntire 实验中 11 阶段流水线消耗全部预算的直接原因。

---

### 3.6 context 隔离策略

参考 claude-code coordinator 模式的 scratchpad 设计：
- 每个 agent 实例有独立 context window
- spec.md / design.md 作为 artifact 文件在实例间传递（不是消息传递）
- reviewer 加载 artifact 文件 + constitution，**不加载** author 的内部推理

这样即使 author 的 context 因为长规划链而出现 drift，reviewer 看到的是干净的产物，判断不会被污染。

---

## 4. Reality Check：哪些是 hype，哪些被证伪

### 已被证伪（黑盒场景）

| 说法 | 实证结论 |
|------|---------|
| "更多 agent = 更好结果" | ❌ 45% 规则 + 17.2x 错误放大 + McEntire 100%→0% |
| "debate 让 agent 更聪明" | ❌ Martingale Curse + 76-89% problem drift |
| "复杂门控流水线确保质量" | ❌ McEntire 11 阶段 = 0% 成功，消耗全部预算在规划上 |
| "多 agent 在开放式任务上强于单 agent" | ❌ 无直接实证；现有证据倒向相反 |
| "全自动 planning 可靠" | ❌ OpenEvolve reward hacking 证明系统绕过质量检查 |

### 有实证支撑（黑盒可落地）

| 做法 | 实证支撑 |
|------|---------|
| 独立子任务并行化（read-only worker） | 🟢 SHIPPED，claude-code coordinator 生产验证 |
| Generator-Critic 顺序对 | 🟡 RESEARCH，跨 4 个领域消融实验一致 +5-15%，实现成本低 |
| 独立 context 的 reviewer（fresh eyes） | 🟢 SHIPPED，claude-code 源码明文设计原则 |
| Artifact 文件化传递（非消息传递） | 🟢 SHIPPED，MARE 共享工作区 + claude-code scratchpad |
| 3-4 个互补角色上限（≤ 4） | 🟡 RESEARCH，多研究一致显示 4 后边际收益递减 |
| 数值质量门控（0.0-1.0 评分） | 🟡 RESEARCH，IronEngine Planner-Reviewer 设计 |

### 最大工程风险

1. **规划阶段 token 黑洞**：open-ended 规划没有明确完成条件，agent 容易陷入无限细化。McEntire 实验已证明这是真实的生产风险，不是理论担忧。对策：严格的轮数/token 预算上限 + 强制 escalate。

2. **reviewer 被 author 污染**：如果 reviewer 看到 author 的推理过程，独立性消失，conformity 效应发生。对策：reviewer 只看 artifact 文件，不看对话历史。

3. **协调开销超过收益**：spec/design 两个阶段本身是顺序依赖的；如果把内部子任务也多 agent 化，协调成本可能超过质量收益。经验法则：每增加一个 agent，需要有明确的"这个 agent 能做、其他 agent 做不了"的证据。

---

## 5. 必读一手工程来源

1. **`claude-code/src/coordinator/coordinatorMode.ts`（本地路径）**：370 行系统提示，包含 Anthropic 对"何时并行、何时串行、如何避免懒惰委托"的生产级工程规范。是本文最高权威的一手来源。

2. **`claude-code/笔记/agent-teams-workflow.md`（本地路径）**：Agent Teams 的完整时序分析，包含 worker/reviewer 角色分离的设计原理和 anti-pattern。

3. **MAST (arXiv:2503.13657, NeurIPS 2025)**：首个基于 1600+ 执行轨迹的多 agent 失败分类法，14 种失败模式及占比，UC Berkeley 出品。是"多 agent 失败"最有说服力的实证。

4. **McEntire 实验（CIO Magazine 2026-03）**：单 agent 28/28 成功 vs 多 agent 系统全面失败的对照实验，来自生产工程师，不是学术 benchmark。URL: https://www.cio.com/article/4143420/true-multi-agent-collaboration-doesnt-work.html

5. **MetaGPT (arXiv:2308.00352) + E2E-SD (arXiv:2510.14509) 对比**：前者展示多 agent 顺序流水线在 HumanEval 上的优势；后者展示同一框架在项目级任务上的通信崩溃——合起来说明"有 SOP 的任务有益，开放式任务有害"。

---

## 附：判断树（快速决策）

```
新任务要不要用多 agent？

1. 任务能明确分解成独立子任务吗？
   ├── NO → 单 agent + 强 context engineering（多 agent 帮倒忙）
   └── YES →
       2. 子任务之间是否存在紧耦合上下文依赖？
          ├── YES（规划链、连贯推理）→ 单 agent（高耦合无法并行）
          └── NO（互相独立）→
              3. 基础模型在该任务上是否已经很强（> 45% 成功率）？
                 ├── YES → 谨慎使用，监控是否有能力饱和 / 错误放大
                 └── NO →
                     4. 角色是否真正互补（不同认知视角）？
                        ├── NO（同质 agent 复制）→ 不要加（多样性才是收益来源）
                        └── YES →
                            上限 4 个角色，顺序流水线或 Generator-Critic 对，
                            每个阶段产物文件化，reviewer 独立 context，
                            有数值质量门控，有 token 预算上限，有 human checkpoint
```
