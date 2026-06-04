# Deep Research Brief：用 agent team 自动化软件需求的 spec & design 两个环节

> 这是一份给独立 deep research agent 的研究委托。下面的【背景】是自包含的——你不需要
> 访问任何私有代码库即可理解问题。请围绕【研究问题】展开，输出见【期望产出】。
> 语言：中文为主，技术名词保留英文原文。

---

## 1. 背景（自包含）

### 1.1 我在做什么

我维护一套基于 LLM agent 的**软件自动开发流水线**，采用 Spec-Driven Development（SDD）方法论。一个"变更单元"（feature / bugfix / refactor）的生命周期分四阶段，阶段之间有"门禁"（gate）必须达标才能往下：

```
[探索: 对齐"做什么"] ──门禁1──▶ [设计: 对齐"怎么做"] ──门禁2──▶ [实施: 写码+测试] ──门禁3──▶ [验收/归档]
```

- **探索阶段**产出 `spec.md`：纯用户视角，回答"做什么"。验收标准用 `Requirement → Scenario(GIVEN/WHEN/THEN)` 结构写。**禁止**出现任何实现/架构/库选型。
- **设计阶段**产出 `design.md`：架构决策、模块切分、接口、数据流、被拒方案、milestone 拆分。回答"怎么做"。
- **实施阶段**：多个 coding agent 在隔离 worktree 里并行跑 TDD 三提交循环（先写测试→实现→文档），合并到集成分支。
- **验收阶段**：一个**独立**（非写码同一个）的 reviewer agent 走真实用户旅程逐条核对 spec 的每个 Scenario。

### 1.2 现状：后两环已经全自动，前两环还靠人

- **实施 + 验收（写码环节）已经基本全自动、趟通了**：orchestrator 派发 → worker 实现 → reviewer 验收，这条链不再需要我逐步介入。
- **痛点在前两环（spec + design）**：每个需求我都得很详细地亲自参与对齐——从产品经理视角想全局、从架构师视角想长期可演进、从前端设计视角想美观、遇到陌生领域还要自己上网查资料、参考同类项目。这个"对齐"过程是同步的、逐需求的、极耗我个人注意力，导致**无法 scaling up**。

### 1.3 目标

我想造一个 **agent team 接管 spec + design 这两个环节**（到门禁 2 定稿为止，之后交给已趟通的实施/验收链）。理想状态：**我只做"简单的需求沟通"，后面 spec 对齐 + design 对齐由 agent team 自动完成。**

注意边界（这点很重要，别误解成"全自动乌托邦"）：

- **不是要把人完全踢出去。** 是要把人从"每个需求的每个对齐细节的同步参与者"，转变为"只在少数真正的价值岔路上、异步地、在门禁处做裁决与审查"——即从 human-in-the-loop 转为 human-on-the-loop。
- 我前期的哲学推演得出一个核心判断，需要研究来证实或推翻：**spec/design 的本质是"注入人类的价值判断与品味"，而 agent 只能对着给定目标函数优化。如果不把"我的品味/产品判断/架构偏好"以某种持久、可复用的形式"编译"出来喂给 agent team，那么轻 brief 进去，得到的会是"看似合理但通用、且随 milestone 累积偏移（drift）"的 spec/design。** 类比：马化腾能只给轻 brief，是因为接住 brief 的张小龙已内化了他的品味；agent team 当前缺这层"张小龙"。

### 1.4 技术约束 / 自由度

- 模型：可用很强的前沿模型（Opus 级）。不缺算力。
- 框架：**不限于任何现有 agent 框架**，我可以自由自建。可以群聊（多 agent 同会话辩论）、可以单聊（点对点）、任意拓扑。
- 已有基础设施：文件化的 artifact workspace（每个变更单元一个目录，存 spec/design/进度/验收）、门禁机制、结构化验收标准（GIVEN/WHEN/THEN）、一轮一问的交互式澄清、独立 reviewer 角色。

---

## 2. 核心问题陈述

> **如何设计一个 multi-agent 系统，让它在"人只做轻量需求沟通"的前提下，自动完成软件需求的
> spec 对齐与 design 对齐两个环节，产出达到生产可信质量、且不随后续实施累积意图偏移的
> spec/design 文档——同时把人对该产出的验证成本压到最低（human-on-the-loop，而非
> in-the-loop 或 out-of-the-loop）？**

子命题：
- (a) 人的"品味/产品判断/架构偏好"如何被显式编译成 agent team 可复用的资产？哪种形式最有效（原则文件 / 案例库 / 角色化 critic / 偏好模型 / 别的）？
- (b) 哪些 spec/design 决策可以安全地全自动，哪些必须升级（escalate）给人？如何让系统自己识别"这是一个需要人裁决的价值岔路"？
- (c) 多 agent 的协作拓扑（群聊辩论 vs 顺序流水线 vs 角色 critic 对抗）哪种对 spec/design 质量最有利？
- (d) 如何让人的验证成本足够低（不被一堆 markdown 淹没），同时不牺牲对 drift 的防护？

---

## 3. 已知现状（请在此基础上往深处走，不要重复这部分的浅层调研）

我已做过一轮浅层调研，结论如下。**请验证、纠正、并大幅深化；尤其找出下面没覆盖到的方案、最新进展、以及反面证据/失败案例。**

**业界分两个阵营，成败相反：**

- **阵营 A — "AI 软件公司"（全自动角色模拟，端到端）**：MetaGPT（PM/架构师/工程师 + SOP，商业产品 MGX）、ChatDev（CEO/程序员/测试 chat-chain，机制 "communicative dehallucination"=生成前先反问细节）。**实证质量评分低**（ChatDev ~0.395 / MetaGPT ~0.152），即全自动盒子产出玩具级、非生产级。
- **阵营 B — Spec-Driven Development 工具（人留作 verifier，在阶段边界把关）**：GitHub spec-kit（`Constitution→Specify→Plan→Tasks→Implement`，核心是不可变原则文件 "constitution"）、AWS Kiro（`Requirements→Design→Tasks`，用 GIVEN/WHEN/THEN）、Tessl（spec-as-source，spec↔code 双向同步）。生产可信方案**无一例外**保留人为 verifier/refiner。Fowler 团队结论：人是 verifier 不只是 steerer；主要痛点是 markdown 太多、review 累、agent 忽略或过度遵从指令。

**与我目标最重合的现成方案：BMAD-METHOD** —— 两阶段：Agentic Planning（Analyst→PM→Architect→UX 协作出经验证的 PRD+Architecture）；再由 Scrum Master agent 把规划编译成超详细 story file 喂给 Dev agent。其 Planning 阶段 ≈ 我要做的 spec+design。

**学术界**：MARE（5 agent / 9 action，覆盖 RE 四阶段 elicitation→modeling→verification→specification，共享 workspace 做 handoff，+15.4% vs SOTA）；ReqInOne（SRS 生成 agent）；Specine（把代码 lift 成 requirement DSL，Pass@1 +29.6%）；RE 综述归纳 9 个 prompt 主题。

**初步共识方向**：角色分解成不同 persona（价值在强制切换镜头）；共享 artifact workspace + handoff；"constitution"/原则文件作为持久约束（= 编译过的品味）；消歧/澄清作为显式步骤；人在阶段边界做 verifier；结构化 spec/需求 DSL 降歧义。

**初步判断的开放问题**：没人"把人完全踢出 spec/design"还能拿到生产级质量；前沿不是"去掉人"而是"降低 review 负担 + 防 drift"。

---

## 4. 希望探索的方向（按优先级分组）

### P0 — 直接决定本系统设计的核心问题

1. **"编译人类品味/判断"的最佳实践**：把个人/团队的产品判断、架构偏好、审美标准固化成 agent 可复用资产，业界/学术界有哪些具体做法？对比：原则/constitution 文件 vs few-shot 案例库（过往认可/否决的决策）vs 角色化 critic agent vs 偏好学习/RLHF-style 个性化 vs memory 系统。各自的有效性证据、维护成本、泛化能力、抗 drift 能力？有没有"AI alignment to an individual's taste"方向的工作？

2. **escalation / 何时该问人**：让自治 agent 系统**自己判断**"这个决策超出我的授权、需要升级给人"的机制。关键词：active learning、uncertainty estimation、confidence-gated escalation、ask-vs-act policy、human handoff design。怎么避免两个极端（什么都问 vs 什么都不问）？有没有量化"决策价值/不确定性"来触发升级的成熟方法？

3. **防 intent drift（意图偏移）**：spec→design→实施多跳传递中，原始意图如何衰减、如何度量、如何防护？traceability、spec-as-contract、bidirectional sync（如 Tessl）、requirement DSL（如 Specine）等手段的实证效果对比。

### P1 — 协作机制与质量

4. **多 agent 协作拓扑对产出质量的影响**：群聊辩论（debate / multi-agent discussion）vs 顺序流水线 vs generator-critic 对抗 vs society-of-mind，哪种在"开放式设计/需求"类任务（非有标准答案的任务）上更优？有没有对比实验？debate 是否真能提升质量，还是会收敛到平庸/共识陷阱？

5. **角色分解的真实价值**：PM/architect/UX/analyst 这种角色 persona 划分，提升的是产出质量还是只是"看起来像那么回事"？有没有消融实验证明"多镜头"本身有效，而不只是 prompt 包装？最优角色集是什么？

6. **澄清/消歧策略**：交互式澄清（一轮一问 vs 批量）、communicative dehallucination、proactive clarification question generation 的最佳实践与失败模式。如何让 agent 问"对的少数几个问题"而不是疲劳轰炸？

### P2 — 评测、前端设计维度、长期演进

7. **如何评测一份 spec/design 的"好"**：除了下游代码 Pass@1，有没有直接评测 spec/design 质量（完整性、一致性、对齐 stakeholder 意图、可演进性）的方法/benchmark/rubric？这决定我能否给 agent team 一个可优化的目标函数。

8. **前端/UI 设计自动化**：我的需求常含"整体美观性"维度。agent 自动做产品视觉/交互设计（设计系统、参考同类产品、生成可对比的视觉方案）业界做到哪了？关键词：AI design agent、design review agent、自动竞品/landscape 调研。

9. **架构长期可演进性的自动判断**：agent 如何评估一个 design 的"长期可演进性/技术债风险"，而不只是"能跑就行"？有没有让 agent 做架构 trade-off 推理、考虑未来扩展的工作？

10. **失败案例与反面证据**：哪些团队尝试了"agent 自动 spec/design"然后失败/回退了？失败的根因是什么？（这比成功案例更有信息量。）

---

## 5. 期望产出

1. **方向 1/2/3（P0）的深度综述**：每个方向给出当前最佳方案、关键论文/产品、实证证据、以及对"个人开发者自建系统"场景的可迁移性评估。
2. **一张方案对比表**：把"编译品味"和"协作拓扑"的候选做法横向对比（有效性证据 / 维护成本 / 实现复杂度 / 抗 drift）。
3. **明确的反面证据**：哪些做法被证明无效或有陷阱（如 debate 的共识陷阱、原则文件被 agent 忽略、过度角色化的虚假复杂度）。
4. **3–5 篇必读来源**：最值得我精读的论文/工程文章，附一句话理由。
5. **针对核心问题陈述（§2）的直接回答**：基于证据，给出"该怎么搭这个系统"的方向性建议，以及最大的未解风险。

> 优先要**有实证支撑的结论和一手来源**，不要泛泛的"AI 很有前景"式综述。对每条关键论断附可核查的出处。
