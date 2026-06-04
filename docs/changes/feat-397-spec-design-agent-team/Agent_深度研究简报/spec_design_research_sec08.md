## 8. 必读来源推荐

在12个研究维度、200+篇文献的调研中，以下五篇来源构成了理解"multi-agent系统自动spec/design对齐"这一问题的核心知识骨架。它们分别覆盖了反面证据、理论基础、工程框架、统计保障和范式转型五个不可或缺的视角。按优先级排序如下。

### 8.1 五篇核心论文/文章

#### 8.1.1 "Why Do Multi-Agent LLM Systems Fail?"（MAST，UC Berkeley NeurIPS 2025）——反面证据大全

**作者与机构**：Wei-Lin Chiang et al., UC Berkeley（Ion Stoica、Matei Zaharia团队）[^1000^]

**核心贡献**：这是首个基于大规模实证标注的多agent系统失败分类法。研究者分析了7个流行MAS框架在200+任务上的表现，通过1,600+执行轨迹的标注，识别出14种细粒度失败模式，分为Specification Issues（44.2%）、Inter-Agent Misalignment（32.3%）和Task Verification（23.5%）三大类。三位标注者独立标注达到Cohen's Kappa = 0.88的高一致性。

**为何必读**：在规划任何multi-agent系统之前，这篇论文提供了最全面的"避坑指南"。它证明了一个令人警醒的事实：多agent LLM系统在生产环境中的失败率高达41%-86.7%，79%的失败源于specification和coordination问题而非模型能力不足[^997^]。ChatDev在ProgramDev基准上仅33.33%的成功率[^1010^]、MetaGPT在项目级几乎无法处理所有测试用例——这些实证数据构成了对"多agent万能论"的最有力反驳。

**关键启示**：(1) 步骤重复（17.14%）和推理-行动不匹配（13.2%）是最常见的单类失败模式；(2) 人类介入接口的缺失是当前框架设计的系统性盲区；(3) 14种失败模式可作为设计review的checklist。

#### 8.1.2 "Breaking the Martingale Curse"（AceMAD）——打破共识陷阱的理论方案

**作者**：Zijian Liu et al. [^367^]

**核心贡献**：从概率论角度证明了标准Multi-Agent Debate（MAD）是一个martingale过程——每轮debate的期望值等于当前值，因此没有正向drift toward truth。这被称为"Martingale Curse"。在此基础上，论文提出了asymmetric cognitive potential energy机制：truth-holders不仅知道正确答案，还能预判crowd的misconceptions，而hallucinating majority则对集体错误盲目。这种不对称性在nonlinear aggregation下转化为submartingale drift toward truth。

**为何必读**：所有涉及"多agent讨论/评审/review"的设计决策都应以这篇论文为理论基础。它解释了为何简单的多agent投票或讨论不仅无效，甚至可能有害——76%-89%的生成任务样本出现problem drift[^433^]，85.5%的agent表现出sycophantic conformity[^460^]。AceMAD在六个benchmark的challenging subsets上比标准MAD提升20.31%，消融研究显示移除second-order cognition导致性能下降14.6%。

**关键启示**：(1) 打破对称性（而非增加agents）是关键；(2) cross-model mixing、persona-driven roles、cognitive system variation都能提供有效的不对称性；(3) N≤4, T≤2是debate的安全边界。

#### 8.1.3 MARE（Jin et al., 2024）——多Agent需求工程的代表性框架

**作者**：Yuan Jin et al. [^20^]

**核心贡献**：MARE（Multi-Agents Collaboration Framework for Requirements Engineering）是将需求工程分解为四个顺序任务（elicitation→modeling→verification→specification）的多agent协作框架，每个任务由专门agent执行。MARE(gpt-3.5-turbo)在需求建模F1上超越三个SOTA基线最多15.4%[^20^]。其核心设计——Shared Workspace让所有agent可访问intermediate artifacts——解决了顺序流水线中的信息传递问题。

**为何必读**：MARE是学术界在"spec自动化"方向上最完整的端到端框架。它证明了顺序流水线在需求工程任务上的有效性，提供了Checker agent的详细设计（基于accept criteria检查correctness、completeness、consistency），并引入了human evaluation在correctness、completeness、consistency三个维度上的评估方法。对于构建brief→spec流水线的开发者，MARE是最直接的参考架构。

**关键启示**：(1) 专门的verification stage是质量保障的关键；(2) Shared Workspace解决了顺序流水线的信息丢失问题；(3) 四阶段设计（elicitation→modeling→verification→specification）可直接映射到个人开发者的需求工程workflow。

#### 8.1.4 KnowNo（ICRA 2023）+ Conformal Social Choice——Escalation的统计保证

**作者**：Anastasios N. Angelopoulos et al.（KnowNo）；后续扩展包括Conformal Social Choice等[^310^]

**核心贡献**：KnowNo将conformal prediction（共形预测）引入LLM的selective classification，为"何时escalate给人类"提供了统计保证：以用户指定的错误率上限（α）控制自动化决策的风险。Conformal Social Choice进一步将框架扩展到multi-agent setting，将失败拦截率提升至81.9%。

**为何必读**：在"agent何时该问人"这个决策上，直觉和启发式规则是不可靠的。KnowNo提供了目前唯一具有统计保证的框架——它不是"大概不确定就escalate"，而是"以至少1-α的概率保证正确答案在预测集中"。对于个人开发者而言，这意味着可以精确控制human review的workload与决策质量之间的trade-off。

**关键启示**：(1) Conformal prediction的coverage guarantee（≥1-α）是目前唯一有统计基础的escalation决策标准；(2) 需要 calibration set进行初始校准，但无需知道模型的内部分布；(3) 与SC方法（AUROC 0.68-0.79）结合可实现多信号融合的escalation策略。

#### 8.1.5 "Spec-Driven Development: From Code to Contract"（2025）——Spec-as-Source的理论基础

**作者与来源**：多篇论文构成的Spec-Driven Development（SDD）文献簇，核心包括Fowler团队对Tessl/Kiro/Spec-Kit的分析[^68^][^92^][^139^]

**核心贡献**：提出了从code-first到spec-as-source的连续谱系：spec-first（spec在编码前编写）→ spec-anchored（spec与代码同步演化）→ spec-as-source（人类只编辑spec，代码完全派生）。Martin Fowler亲测Tessl Framework后指出："Moving right increases the authority of specifications over code, but also increases the discipline required to maintain alignment"[^68^]。

**为何必读**：这是理解"spec在AI coding时代角色变迁"的必读文献。它将2000年代Model-Driven Development（MDD）的历史教训与当前LLM-based coding tools对照分析，指出spec-as-source与MDD高度相似——MDD因"抽象层级尴尬、overhead过大"从未在业务应用中成功，而LLM移除了MDD的部分overhead但引入了non-determinism[^92^]。对于设计spec→design→code多跳传递系统的开发者，这一谱系提供了最清晰的理论坐标系。

**关键启示**：(1) Spec-first是当前最务实的起点，spec-as-source是长期目标但尚未成熟；(2) "Drowning in a sea of markdown"是spec-first的真实风险——spec会快速drift from shipped code[^145^]；(3) 双向同步（spec↔code）比单向控制更可行。

---

以上五篇来源的阅读顺序建议：先读MAST建立对风险的清醒认知，再读AceMAD理解协作拓扑的理论边界，然后读MARE获取工程框架的具体参考，结合KnowNo设计escalation机制，最后以SDD文献簇定位自己在spec-as-source谱系上的长期目标。它们共同构成了一个从"反面避坑"到"正面建设"、从"理论约束"到"工程实践"的完整知识闭环。
