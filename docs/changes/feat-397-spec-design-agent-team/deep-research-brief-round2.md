# Deep Research Brief（第二轮）：以"agent 架构 / harness / 多 agent 工程实践"为中心

> 给 deep research agent 的第二轮委托。第一轮过度偏向学术 ML 方法（个性化奖励分解、
> conformal prediction、learning-to-defer 等），这些多是 research-grade、几乎未进生产。
> 本轮**重心切到工程实践层**：真实 agent 产品/harness 怎么搭自动化 spec/design 的系统。
> 语言：中文为主，技术名词保留英文。

---

## 0. 背景（自包含）

委托方是一个**个人开发者**，维护一套基于 LLM agent 的软件自动开发流水线（Spec-Driven Development）。
变更生命周期：`探索→门禁1→设计→门禁2→实施→门禁3→验收`。**写代码环节（实施+验收）已全自动、趟通**；
目标是把**前两环——spec 对齐、design 对齐——也自动化**，让人只给轻 brief + 在价值岔路异步裁决
（human-on-the-loop，不是踢出）。已有基础设施：文件化 artifact 工作区、门禁、结构化验收（GIVEN/WHEN/THEN）、
一轮一问澄清、独立 reviewer、IM/agent 通道。

---

## 1. 硬约束：只能黑盒 LLM（关键，先读）

委托方通过 provider 代理调用模型——**文本进、文本出**。因此**以下整类方法直接排除，不要推荐**：

- **任何训练**：fine-tune / RLHF / DPO / RL / LoRA / 奖励模型训练 / 矩阵分解训练
  （即 RLPA、VPL、PReF 基函数训练、PAL、Persona-Tailoring-DPO、DITTO 的 DPO 步、NS-DPO、CURLoRA 全部出局）。
- **logit 访问**：token logprob / entropy / MSP / 任何 gray-box 特征。
- **解码层介入**：写进 logit 空间或逐 token 干预的方法——**Drift、AMULET、T-POP 全部出局**。
  ⚠️ 特别纠正：第一轮把这三个当"无需训练、适合个人开发者"推荐是错的——它们"不训练"但要解码/logit 访问，黑盒拿不到。

**仍可用（纯黑盒）**：prompt 工程、few-shot / in-context、检索 + 文件/记忆（RAG 类，如 Mem0/MemoryBank）、
多次采样比一致性（sample-consistency 置信度）、prompted critic、prompted 动态 checklist、
prompt 自优化（SynthesizeMe/FERMI 类）、LLM-as-judge、黑盒 conformal（ConU / LofreeCP，需校准集不需 logits）、
learning-to-defer 的**决策逻辑**（不训模型）。

> 对第一轮推荐的每个方法，请给一张 **CAN / CANNOT（黑盒下）** 表，CANNOT 的给出**最佳黑盒替代**。

---

## 2. 本轮重心：工程实践，不是学术理论

**核心转向**：委托方本身在造 agent harness。真正要的是"**主流 agent 产品/harness 是怎么工程化地搭出
spec/design 自动化的**"，而不是又一批论文方法。请围绕架构与工程模式展开。

### 2.1 强制要求：区分 "shipped" vs "research-grade"
对你提到的**每一个技法/模式**，明确标注：
- **🟢 SHIPPED**：真在生产级 agent 产品 / 开源 coding agent / 主流 harness 里被采用（给出是谁、在哪用）。
- **🟡 RESEARCH**：只在论文/benchmark 里验证过，未见生产采用。
除非 RESEARCH 项明确黑盒可直接落地，否则一律降权。**这一栏是本轮最重要的产出**——直接回答"这是不是主流"。

### 2.2 来源优先级（重要）
1. **一手工程材料**：前沿实验室的 agent 构建工程指南/工程博客（如 Anthropic "building effective agents"、
   "context engineering" 等同类一手文章）、真实开源 coding agent / harness 的**源码与设计文档**
   （Claude Code、spec-kit、BMAD、Kiro、OpenHands/SWE-agent、LangGraph/AutoGen/CrewAI 的实际编排实现）、
   生产事后复盘（postmortem）。
2. **失败面的权威实证**：MAST（arXiv 2503.13657）、AgentPrune（ICLR 2025）、各 multi-agent 对照实验。
3. **学术理论**：仅当能落地且黑盒可行时才纳入，且标 🟡。

> 反 anti-pattern：不要再用大量 arXiv 个性化/对齐论文堆砌。本轮要工程，不要综述。

---

## 3. 研究问题（架构/harness/多 agent 居中）

### P0 — 架构与编排（主线）
1. **planning 阶段的 harness 模式**：真实 agent 产品在"需求→spec→design"这种**开放式规划**阶段（不是写代码），
   用什么架构？重点扒：orchestrator-worker、subagent 隔离（独立 context 窗口）、文件即记忆/artifact 传递、
   确定性门控、human-approval choke point、role-structured 顺序流水线。各自 SHIPPED 在哪。
2. **多 agent 到底何时帮、何时帮倒忙**（针对开放式规划任务）：给出当前**主流工程共识**与最强实证
   （含 Anthropic 多 agent 研究的正反结论、MAST、AgentPrune "45% 规则"、单 agent vs 多 agent 对照）。
   结论要可操作：什么时候该上多 agent、什么时候单 agent + 强 context engineering 就够。
3. **context engineering**：长规划链里怎么**不靠 ML**地防 drift / 控 context——compaction、结构化 artifact、
   retrieval、sub-agent 隔离、constitution 按需加载。主流 harness 实际怎么做的。

### P1 — 把"品味/escalation/评测"落到工程层（黑盒）
4. **品味编译的工程做法**（非训练）：shipped 产品实际靠什么装"用户偏好"——constitution/rules 文件、
   AGENTS.md 类、文件化 memory、few-shot 案例检索、prompted persona？对比它们的真实效果与维护坑
   （含 constitution 被忽略 / 与 AGENTS.md 重复这类已知工程问题）。
5. **特定资产**：委托方现有做法是"做 feat spec 时让 agent 记录所有用户原话"，于是 `docs/changes/*/spec.md`
   里跨历史 unit 攒了一批"用户在各种岔路上怎么说、怎么取舍"的语料。问：有没有**从既有决策/理由语料
   bootstrap 个性化**的工程做法（而不是重新收集 preference pairs）？怎么把这批原话变成 few-shot / persona /
   检索案例库，纯黑盒。
6. **escalation 的工程做法**（黑盒）：只靠"多次采样比一致性 + prompted 置信 + 确定性 gate + human-approval 节点"
   能把"何时该问人"做到什么程度？value-fork（价值判断 vs 事实判断）能否纯靠 prompting 检测？
   对开放式生成任务（非选择题）有没有 SHIPPED 的置信/escalation 证据？conformal 只保留黑盒可落地的部分（ConU/LofreeCP）。
7. **spec/design 质量评测 harness**（第一轮点名的最大缺口）：practitioner 实际用什么评一份 spec/design 的好？
   LLM-as-judge harness、golden set、eval-driven development（EDLC）。怎么把 judge 校准到**单个人的品味**
   （而非"平均人类"）？"可演进性"有没有可操作的代理指标？

### P2 — 落到本场景
8. **既有 SDD 产品的 planning 阶段拆解**：BMAD（Analyst/PM/Architect→SM→Dev）、spec-kit（Constitution→Specify→Plan→Tasks）、
   Kiro（Requirements→Design→Tasks）——它们**前两环具体怎么编排、哪里要人、哪里自动**？哪些做法可直接搬到
   "已有 orchestrator/worker/reviewer 流水线 + 只补前两环"的场景。
9. **失败复盘**：有没有人试过"agent 自动 planning/spec/design"然后翻车/回退？根因是什么（架构层，不是模型层）？

---

## 4. 期望产出

1. **一张主表**：每个推荐的架构模式/技法 ×（SHIPPED/RESEARCH 标注 + 谁在用 + 黑盒 CAN/CANNOT + 可迁移性）。
2. **针对本场景的架构方案**：在"已有文件化 artifact + 门禁 + orchestrator/worker/reviewer"之上，
   前两环该怎么搭——给出推荐的 agent 拓扑、context/artifact 流、品味装载方式、escalation 机制、评测 harness。
   明确"先做什么、什么先别做"。
3. **第一轮推荐的黑盒再过滤表**（CAN/CANNOT + 替代）。
4. **3–5 个必读一手工程来源**（优先源码/工程博客/postmortem，不是 arXiv），每个一句话理由。
5. **诚实的 reality check**：哪些是 hype、哪些被证明帮倒忙、最大的工程风险是什么。

> 要点：**工程优先、shipped 优先、黑盒可落地优先。** 区分"现在就能搭" vs "纸面理论"是第一价值。
