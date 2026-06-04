# feat-397 调研笔记：业界/学术界如何用 agent team 做 spec/design

> 探索阶段临时文档。目的：在定 spec 边界前，摸清"agent team 自动化 spec+design"这件事
> 业界和学术界做到哪了、方向在哪、什么经验可直接迁移到本项目既有的 change-* 流水线。
> 调研日期：2026-06。

## 1. 全景：两个阵营，结论相反

业界做这件事的人，分成两派，而且两派的成败恰好印证了一个判断：**判断层不能全自动，但劳动层能。**

### 阵营 A —— "AI 软件公司"（全自动角色模拟，端到端）

把整家软件公司塞进一个 multi-agent 系统，一句话需求进，PRD/设计/代码/测试全出。

- **MetaGPT**：内置 产品经理/架构师/项目经理/工程师 + 精心编排的 SOP。一行需求 → user stories / 竞品分析 / 需求 / 数据结构 / API / 文档。2025-01 推出商业产品 MGX（号称"世界第一个 AI agent 开发团队"）。
- **ChatDev**：CEO/程序员/测试 沿 "chat chain" 协作；核心机制 **communicative dehallucination**——agent 在生成前先反问要更具体的细节，减少"编码幻觉"。2026-01 发 ChatDev 2.0（DevAll），零代码多 agent 编排平台。

**关键数据（打脸点）**：质量评分 ChatDev 0.395 / MetaGPT 0.152 / GPT-Engineer 0.142。即——**全自动的"盒子里的公司"产出的是玩具，不是生产级**。这正是我们前面哲学讨论的结论的实证：把判断层整个交给没有你这个目标函数的系统，得到的是"看似合理但通用"的东西。

### 阵营 B —— Spec-Driven Development 工具（人留作 verifier，在阶段边界把关）

2025 年作为对 "vibe coding"（agent 产出看似合理但偏离意图、幻觉 API、随规模衰减）的直接反制而兴起。生产可信的方案**全部**保留人在阶段边界做 verifier。

- **GitHub spec-kit**（93k+ star，最广泛采用）：`Constitution → Specify → Plan → Tasks → Implement`。核心赌注是 **constitution**——一份不可变的架构原则文件，约束所有 agent、跨工具生效。**这就是我前面说的"把品味编译一次、复用千次"的那层。**
- **Kiro**（AWS，agentic IDE）：`Requirements → Design → Tasks` 线性三步，每步一个 markdown。需求写成 user story + **GIVEN/WHEN/THEN 验收标准**——和本项目 spec.md 模板的 Scenario 格式一模一样。强制"先形式化意图，再写码"。
- **Tessl**：spec-as-source，spec 是主维护物，代码用 `@generate`/`@test` 标签从 spec 生成，spec↔代码双向同步。

**Martin Fowler 团队的关键结论**：跨所有这些工具，**人是 verifier 不只是 steerer**——必须"reflect and refine"中间产物。**主要痛点**：markdown 太多、review 累；模板/checklist 再精致，agent 仍频繁忽略指令、或过度遵从（造重复、过度工程）。"人的掌控力存疑，哪怕上下文窗口更大了。"

## 2. 学术界

- **MARE**（Multi-Agent collaboration for Requirements Engineering，arXiv 2405.03256）：5 个 agent、9 个 action，覆盖 RE 四阶段 `elicitation → modeling → verification → specification`；用一个**共享 workspace** 让 agent 上传/取用中间需求产物完成 handoff；比 SOTA 高 15.4%。
- **ReqInOne**：LLM agent 生成软件需求规格说明书（SRS）。
- **Specine**：把生成的代码 lift 成"需求 DSL"（比自然语言更标准、消歧、抗不完整），Pass@1 平均 +29.6%。
- **RE 系统综述**：prompt 工程是 LLM-RE 的基础也是瓶颈，归纳 9 个主题（context / persona / templates / disambiguation / reasoning / analysis / keywords / wording / few-shot）。共性挑战：领域细微差别、幻觉、复杂依赖。

## 3. 最对口的一个：BMAD-METHOD

**和你想做的事几乎完全重合**，可直接对照学习。两阶段：

1. **Agentic Planning**：Analyst → PM → Architect（+ UX Designer）逐个与人协作，产出经验证的 PRD + Architecture，**写一行代码之前全部 doc 已就绪并校验**。
   - Analyst：把模糊想法 → 具体 business case。
   - PM：business case → 完整 PRD（功能/非功能需求 + epic + user story 层级）。
   - Architect：→ 系统设计、技术栈、数据流图、安全考量。
2. **Dev 交接**：Scrum Master agent 把规划"编译"成超详细的 story file（含完整上下文 + 实现细节 + 架构指引），喂给 Dev agent。

**对照本项目**：
| BMAD | 本项目 change-* |
|---|---|
| Planning（Analyst/PM/Architect 出 PRD+Arch） | **= 本 unit 要做的 spec-author + design-author** |
| Scrum Master 把 plan 编译成 story file | = orchestrator 派发包 |
| Dev agent | = change-impl-worker（已趟通） |

即：BMAD 把"agent team 先做规划、再把编译好的上下文交给已有 coding agent"做成了产品形态——正是你要补的前两环。

## 4. 横切方向：大家在收敛的几条共识

1. **角色分解成不同 persona**（analyst/PM/architect/UX）——价值不在角色本身，在**强制切换不同镜头**看同一需求。
2. **共享 artifact workspace + handoff**（MARE 的 workspace）——本项目 `docs/changes/<unit>/` 已经是这个。
3. **"Constitution"/原则文件 = 持久约束 = 编译过的品味**（spec-kit 的核心赌注）——这是让"轻 brief"成立的那层"张小龙"。
4. **消歧/澄清作为显式步骤**（ChatDev 的 communicative dehallucination：生成前先反问）——本项目 spec-author 的"一轮一问"正是这个。
5. **人 = 阶段边界的 verifier，不进每轮循环** = human-on-the-loop——和本项目门禁模型一致。
6. **结构化 spec / 需求 DSL（GIVEN/WHEN/THEN）降歧义**——本项目 spec.md 模板已用。

## 5. 给本 unit spec 的硬信号

- **没有任何人"把人完全踢出 spec/design"还能拿到生产级质量。** 全自动的 company-in-a-box（MetaGPT/ChatDev）评分低；生产可信的（spec-kit/Kiro/BMAD/Tessl）**无一例外**保留人在阶段边界做 verifier/refiner。这从实证上支撑了前面哲学讨论的 human-on-the-loop 结论。
- **前沿不是"去掉人"，是"降低 review 负担"。** 反复出现的抱怨是 markdown 太多、review 累、agent 忽略/过度遵从指令。所以本 unit 真正要解的开放问题是：**让 agent team 产出的 spec/design 既足够好、又足够简洁，使你在门禁处的验证变便宜**——而不是消灭那次验证。
- 本项目相对这些方案的**已有优势**：change-* 已有 workspace（docs/changes）、门禁、GIVEN/WHEN/THEN、一轮一问澄清、且**写码段已全自动**。缺的恰是阵营 B 反复强调的那层 **constitution / 编译过的品味**，以及把单 agent 顺序流水线升级成**多镜头 agent team**。

## Sources

- [MetaGPT (GitHub)](https://github.com/FoundationAgents/MetaGPT) · [MetaGPT 解析 2026](https://aiinovationhub.com/metagpt-multi-agent-framework-explained/) · [MetaGPT 论文 arXiv 2308.00352](https://arxiv.org/pdf/2308.00352)
- [ChatDev (GitHub)](https://github.com/OpenBMB/ChatDev) · [ChatDev 架构综述](https://mgx.dev/insights/52ba1e5c3cf849c295aa8c41555a1194)
- [MARE 论文 arXiv 2405.03256](https://arxiv.org/abs/2405.03256)
- [ReqInOne arXiv 2508.09648](https://arxiv.org/pdf/2508.09648) · [Specine arXiv 2509.01313](https://arxiv.org/html/2509.01313)
- [LLM in RE 系统综述（Frontiers）](https://www.frontiersin.org/journals/computer-science/articles/10.3389/fcomp.2025.1519437/full) · [LLM for RE SLR arXiv 2509.11446](https://arxiv.org/html/2509.11446v1)
- [GitHub Spec Kit](https://github.com/github/spec-kit) · [Spec Kit 文档](https://github.github.com/spec-kit/)
- [Fowler: 理解 SDD —— Kiro / spec-kit / Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)
- [2026 SDD 工具对比（MarkTechPost）](https://www.marktechpost.com/2026/05/08/9-best-ai-tools-for-spec-driven-development-in-2026-kiro-bmad-gsd-and-more-compare/)
- [BMAD-METHOD (GitHub)](https://github.com/bmad-code-org/BMAD-METHOD) · [BMAD 介绍（Reenbit）](https://reenbit.com/the-bmad-method-how-structured-ai-agents-turn-vibe-coding-into-production-ready-software/)
- [Where Do Humans Fit in AI-Assisted Dev（InfoQ）](https://www.infoq.com/news/2026/03/mf-aiassisted-dev/) · [Human-in-the-Loop SDLC 治理](https://tblocks.com/articles/human-in-the-loop-sdlc-governance/)
