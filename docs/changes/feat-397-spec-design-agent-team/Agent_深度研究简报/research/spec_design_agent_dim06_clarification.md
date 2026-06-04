# 维度六：澄清/消歧策略（Clarification/Disambiguation）

## 研究概述

**研究问题**：如何让Agent通过"对的少数几个问题"快速收敛到用户真实意图，而非疲劳轰炸式追问？

**核心发现概要**：
1. **澄清确实有效**：ClarifyGPT等研究显示，精准澄清可将代码生成Pass@1提升13.87%~16.83%[^612^]；MEDIQ显示proactive question-asking可提升诊断准确率22.3%[^664^]
2. **一轮一问 vs 批量**：Prism框架实证显示，基于逻辑依赖的澄清排序（独立问题批量呈现、依赖问题逐轮呈现）可减少任务完成时间34.8%、提升用户满意度14.4%[^650^]
3. **澄清轮数上限**：业界普遍采用3轮上限（REMSA[^654^]、DeerFlow[^660^]、Langchain-Chatchat[^631^]），但ClarifyGPT数据显示每道ambiguous problem平均仅需2.85个问题[^612^]
4. **LLM澄清能力仍有巨大差距**：即使GPT-4o在ClarQ-LLM benchmark上成功率仅50.8%，远低于人类的85%[^627^]
5. **关键权衡**：主动澄清（proactive）优于被动猜测，但过度澄清导致用户疲劳；最优策略是"有条件澄清"——只在检测到歧义时才提问

---

## 1. Communicative Dehallucination：生成前先反问

### 1.1 ChatDev的机制与原理

**核心机制**：ChatDev引入了**communicative dehallucination**机制，鼓励Assistant agent在提供最终解决方案前主动向Instructor寻求澄清和补充细节。这种"角色反转"使Agent能够识别需求中的歧义、请求缺失信息，并通过聚焦对话逐步优化解决方案[^603^]。

**原文摘录**：
> "Communicative dehallucination prompts the assistant to actively request more detailed suggestions from the instructor before providing a formal response. Assistants take on an instructor-like role and proactively seek more information...taking on a deliberate 'role reversal' before delivering a response."[^603^]

**工作流程**：
1. Assistant检测到需求中的模糊或不完整信息
2. Assistant主动向Instructor提出澄清问题（如"精确的外部依赖名称是什么？"或"应该提交到哪个GitHub仓库？"）
3. Instructor回应并提供修改
4. Assistant基于补充信息进行精确优化[^603^]

### 1.2 效果评估

**Ablation Study结果**：移除communicative dehallucination机制后，所有指标均出现下降[^448^]：

| 指标 | 完整ChatDev | 移除CDH | 变化 |
|------|------------|---------|------|
| Completeness | 0.5600 | 0.4700 | -16.1% |
| Executability | 0.8800 | 0.8400 | -4.5% |
| Consistency | 0.8021 | 0.7983 | -0.5% |
| Quality | 0.3953 | 0.3094 | -21.7% |

**Claim**: Communicative dehallucination机制对软件质量有显著正向贡献，尤其是Completeness和Quality指标。
**Source**: ChatDev: Communicative Agents for Software Development (ACL 2024)
**URL**: https://aclanthology.org/2024.acl-long.810.pdf
**Date**: 2024
**Excerpt**: "eliminating communicative dehallucination results in a decrease across all metrics, indicating its effectiveness in addressing coding hallucinations"[^449^]
**Confidence**: high

**重要反面证据**：一项独立复现研究发现，ChatDev的iterative（多轮交互）模式在某些任务上反而比one-shot模式表现更差。在Knight's Tour任务上，one-shot得分32%而iterative为0%；在FOCM任务上，one-shot为14.29%而iterative为13.43%[^628^]。这表明communicative dehallucination并非在所有场景下都有效，其效果依赖于任务特性。

**Source**: "Characterizing and improving ChatDev coding performance" (Master Thesis)
**URL**: https://www.diva-portal.org/smash/get/diva2:1931827/FULLTEXT01.pdf
**Confidence**: medium（单一研究，样本有限）

### 1.3 ChatDev的整体性能

ChatDev在所有指标上显著优于基线方法[^448^]：
- **Quality**: 0.3953 vs MetaGPT 0.1523 vs GPT-Engineer 0.1419
- **Executability**: 0.8800 vs MetaGPT 0.4145 vs GPT-Engineer 0.3583
- 在人类评估中，ChatDev在90.16%的比较中获胜[^448^]

---

## 2. 澄清问题生成质量

### 2.1 ClarifyGPT：代码生成中的意图澄清

ClarifyGPT是一个让LLM识别模糊需求并生成针对性澄清问题的框架[^606^]。其核心贡献包括：

**技术流程**：
1. **Test Input Generation**: 为给定需求生成高质量测试输入
2. **Code Consistency Check**: 利用测试输入进行一致性评估，识别模糊需求
3. **Reasoning-based Question Generation**: 通过比较不同代码实现来推理歧义根源，生成针对性澄清问题
4. **Enhanced Code Generation**: 将澄清问题和回答融入精炼后的需求，生成最终代码[^612^]

**关键设计决策**：只在检测到歧义时才提问，而非对每个需求都提问。这避免了"不必要的LLM-Human交互"和"当问题离题时损害代码生成性能"[^612^]。

**实证结果（人类评估）**：

| 方法 | MBPP-sanitized | MBPP-ET | 平均 |
|------|---------------|---------|------|
| Default (GPT-4) | 70.96% | 51.52% | 61.24% |
| CoT | 72.68% | 53.79% | 63.24% |
| GPT-Engineer | 73.77% | 54.96% | 64.37% |
| **ClarifyGPT (人类反馈)** | **80.80%** | **60.19%** | **70.50%** |
| 相对提升 | **+13.87%** | **+16.83%** | **+15.35%** |

**Source**: "ClarifyGPT: Empowering LLM-based Code Generation with Intention Clarification" (FSE 2024)
**URL**: https://dl.acm.org/doi/10.1145/3660810
**Date**: 2024-07-12
**Excerpt**: "ClarifyGPT elevates the performance (Pass@1) of GPT-4 from 70.96% to 80.80% on MBPP-sanitized"[^612^]
**Confidence**: high

**关键数据点**：平均每道ambiguous problem需要**2.85个澄清问题**[^612^]。这暗示3轮澄清上限是合理的。

**人类评估质量评分**（10名参与者，3个维度，0-2分）：
- Relevance（相关性）: 平均1.83/2.0
- Comprehensiveness（全面性）: 平均1.76/2.0
- Usefulness（有用性）: 平均1.81/2.0[^612^]

### 2.2 AGENT-CQ：澄清问题生成与评估框架

AGENT-CQ是一个端到端的LLM-based框架，包含两个阶段[^592^]：
1. **Generation Stage**: 使用LLM prompting策略生成澄清问题
2. **Evaluation Stage (CrowdLLM)**: 使用多个LLM实例模拟人类众包判断

**关键发现**：LLM生成的问题在检索效果上**优于**人类生成的问题（对BM25和cross-encoder模型均有提升）[^592^]。

**Source**: "AGENT-CQ: Automatic Generation and Evaluation of Clarifying Questions for Conversational Search with LLMs"
**URL**: https://arxiv.org/abs/2410.19692
**Date**: 2024-10-25
**Confidence**: medium

### 2.3 Alexpaca：通过Self-Play自我改进澄清问题

Alexpaca展示了小模型（Llama 3 8B）可以通过agent-agent交互自我改进澄清问题生成能力，无需人工标注[^682^]。

**核心数据**：
- GPT-4在HotpotQA-FLM上仅恢复46.5%的缺失信息（F1），远低于人类的84.4%
- Alexpaca通过rejection sampling fine-tuning，将Llama 3的性能从26.9%提升到37.2% F1 recovery（+28%相对提升）[^682^]

**Source**: "Alexpaca: Learning Factual Clarification Question Generation Without Examples"
**URL**: https://arxiv.org/abs/2310.11571
**Confidence**: high

### 2.4 ClarQ-LLM Benchmark：中英双语任务型对话澄清评估

ClarQ-LLM是一个评估agent在任务型对话中提出澄清问题能力的benchmark，覆盖31种任务类型[^627^]。

**惊人发现**：即使是最先进的LLM，成功率也远低于人类[^627^]：

| Seeker Agent | 中文成功率 | 英文成功率 |
|-------------|-----------|-----------|
| GPT-3.5 | ~0% | ~2% |
| GPT-4 | 25.8% | 29.6% |
| GPT-4o | 50.8% | 48.5% |
| LLAMA3.1-405B | - | 60.5% |
| **人类** | **~85%** | **~85%** |

**关键洞察**[^627^]：
- LLM seeker的查询长度显著长于人类参与者，表明LLM倾向于verbose而非concise
- LLM frequently choosing to end conversations prematurely or failing to gather all necessary information
- Multi-info provider agent可以提升成功率，允许seeker在更少交互中整合多段信息

**Source**: "ClarQ-LLM: A Benchmark for Models Clarifying and Requesting Information in Task-Oriented Dialog"
**URL**: https://arxiv.org/abs/2409.06097
**Confidence**: high

---

## 3. 信息价值最大化：每个问题带来最大信息增益

### 3.1 Expected Information Gain (EIG) 框架

EIG是信息论中用于量化问题"信息量"的核心指标。其基本思想是：一个好的问题应该无论得到什么回答，都能最大程度减少不确定性[^597^]。

**公式**：
$$EIG(q) = H(P(D_t)) - [\frac{1}{2} \cdot H(P(D_t | \text{support})) + \frac{1}{2} \cdot H(P(D_t | \text{refute}))]$$

其中$H$是熵，$P(D_t)$是当前对候选诊断的分布[^591^]。

### 3.2 MedClarify：医学诊断中的最优问题选择

MedClarify将EIG框架应用于医学诊断，提出了**Diagnostic Expected Information Gain (DEIG)**[^591^]：

$$q^* = \arg\max_{q \in Q_t} [\alpha \cdot IG(q) + \beta \cdot Div(q) + \gamma \cdot Con(q)]$$

三个组成部分：
- **IG (Information Gain)**: 标准熵减，量化诊断不确定性的减少
- **Div (Divergence)**: 衡量支持/反驳两种假设回答下的诊断差异，优先选择能排除整个相关疾病分支的问题
- **Con (Concentration)**: 使用Gini系数鼓励探索，避免confirmation bias[^591^]

**效果**：在50岁男性胸痛病例中，MedClarify通过迭代提问逐步缩小鉴别诊断范围，从广泛的可能性收敛到正确诊断（急性胰腺炎）[^591^]。

**Source**: "A Medical Information-Seeking Agent That Asks Optimal Questions" (Nature系列)
**URL**: https://arxiv.org/pdf/2602.17308
**Confidence**: medium（医学领域，但方法论可迁移）

### 3.3 Learning to Ask Informative Questions：用DPO优化EIG

Mazzaccara等人提出通过**Direct Preference Optimization (DPO)** 训练LLM生成高EIG的问题[^597^]：

**方法**：
1. 从同一个模型(LLaMA 2-Chat 7B)对每个游戏采样多个问题
2. 计算每个问题的EIG
3. 创建low-EIG和high-EIG问题对
4. 应用DPO算法，增加optimal EIG问题的likelihood，降低suboptimal问题的likelihood

**结果**：DPO训练后，模型在EIG指标上显著改善，即使在训练领域之外的测试集上也表现良好[^597^]。

**Source**: "Learning and Evaluating Factual Clarification Question Generation"
**URL**: https://aclanthology.org/2024.findings-emnlp.291/
**Confidence**: high

### 3.4 Optimal Question Asking (OQA) Benchmark

OQA是一个"玩具游戏"benchmark，用于衡量Agent的询问策略效率[^598^]：

**关键发现**：
- 在25-object任务上，GPT-4o和Claude 3.5 Haiku的planning gap为1-2个问题
- 在100-object任务上，即使是GPT-o3和Gemini 2.5 Pro也存在显著的战略缺陷
- 合成数据集（去除语言先验）揭示了更深的缺陷[^598^]

> "OQA exposes inefficiencies invisible to answer-centric metrics, offering a controlled testbed for forging agents that play the information game not just exploitatively, but optimally."[^598^]

**Source**: "The Information Game: Active Inference as Bilevel Optimization and a Game-Theoretic Benchmark for LLM Inquiry"
**URL**: https://openreview.net/pdf?id=1qLZsyJN2t
**Confidence**: high

### 3.5 Adaptive Elicitation of Latent Information

该研究将LLM-based预测推理与群体级传播结合，使用meta-trained LLM基于当前交互历史评分候选问题的EIG[^595^]。

**实证结果**：在三个真实世界意见数据集上，该方法在约束预算下显示了一致的增益，包括在CES数据集上10%受访者预算时实现>12%的相对改进[^595^]。

---

## 4. 澄清疲劳（Clarification Fatigue）

### 4.1 澄清轮数上限：业界共识为3轮

多个独立系统不约而同地将澄清轮数上限设为**3轮**：

| 系统/框架 | 最大澄清轮数 | 依据 |
|----------|------------|------|
| REMSA (Remote Sensing Agent) | 3轮 | "to avoid user fatigue"[^654^] |
| DeerFlow | 3轮 | 默认max_clarification_rounds=3[^660^] |
| Langchain-Chatchat | 最多2次追问 | "超过后应回退至通用提示，防止陷入无限循环"[^631^] |
| 知识图谱澄清系统 | max_rounds=3 | 基于缺失标签生成澄清问题[^659^] |
| AgenticLU | 最大深度3 | "97.4%的训练问题已被解决"[^655^] |

**Source**: 多个独立来源，见上表
**Confidence**: high

### 4.2 ClarifyGPT的数据支持：平均仅需2.85个问题

ClarifyGPT在140道ambiguous problems上的数据显示[^612^]：
- 平均每道ambiguous problem需要**2.85个澄清问题**
- 这意味着3轮上限覆盖了绝大多数情况

### 4.3 AgenticLU的澄清轮数分布

AgenticLU的研究提供了更精细的澄清轮数分布数据[^655^]：
- **92%**的问题在**1轮**澄清内解决
- 剩余8%中，**2轮**解决53%
- 再剩余中，**3轮**解决35%
- **总计97.4%**在3轮内解决

> "Because of the exponentially increasing cost—and given that 97.4% of the training questions are already solved—we limit the maximum depth of our inference scaling to 3."[^655^]

**Source**: "Self-Taught Agentic Long-Context Understanding"
**URL**: https://arxiv.org/html/2502.15920v2
**Confidence**: high

### 4.4 调查领域的长度疲劳数据

虽然不是直接针对Agent澄清，Qualtrics的大规模调查数据提供了相关参考[^657^]：
- 桌面端超过**12分钟**的调查开始出现急剧的respondent drop-off
- 移动端超过**9分钟**即开始drop-off
- 超过**3个开放式问题**后完成率开始下降

**Source**: "4 Tips for Preventing Drop-Offs in Surveys" - Qualtrics
**URL**: https://www.qualtrics.com/articles/strategy-research/4-tips-for-preventing-drop-offs-in-surveys/
**Confidence**: medium（间接证据，调查场景vs对话场景）

### 4.5 YapBench：LLM话太多的问题

YapBench benchmark量化了LLM在简短请求上的过度生成问题[^694^]。在Category A（最小/模糊输入）中，理想行为是简短澄清请求，但许多模型倾向于"用不请自来的内容填充真空"（vacuum-filling），而非发出最小澄清请求[^695^]。

> "Category A prompts contain low-information turns for which the minimal sufficient behavior is a short clarification request or acknowledgment. Despite the absence of actionable task information, many models generate extended content."[^695^]

这提示了一个重要设计原则：**当输入模糊时，Agent应该问一个简短的问题，而不是输出长篇内容**。

**Source**: "Do Chatbot LLMs Talk Too Much? The YapBench Benchmark"
**URL**: https://arxiv.org/abs/2601.00624
**Confidence**: high

---

## 5. Proactive Clarification：主动识别歧义并提问

### 5.1 Proactive vs Reactive的核心区别

| 维度 | Proactive Clarification | Reactive Clarification |
|------|------------------------|----------------------|
| 触发时机 | Agent检测到歧义即主动提问 | 等用户纠正或表达不满 |
| 用户体验 | 流畅、预防性 | 打断性强、修复性 |
| 信息效率 | 高：在错误发生前获取信息 | 低：已产生错误后补救 |
| 认知负荷 | 低：一次澄清一个问题 | 高：用户需发现和报告错误 |

### 5.2 MEDIQ：临床推理中的Proactive Question-Asking

MEDIQ是评估LLM在交互式临床推理中主动提问能力的benchmark[^664^]。

**核心发现**：
1. **直接prompting SOTA LLM提问反而会降低性能**——将LLM适配到proactive information-seeking设置是非平凡的
2. **Abstention module**（当不确定时选择不回答而是提问）可将诊断准确率提升**22.3%**
3. 但即使最佳系统也只关闭了与"完整信息 upfront"上界之间51.2%的gap[^664^]

> "Our results show that directly prompting state-of-the-art LLMs to ask questions degrades performance, indicating that adapting LLMs to proactive information-seeking settings is nontrivial."[^664^]

**Source**: "MEDIQ: Question-Asking LLMs and a Benchmark for Reliable Interactive Clinical Reasoning" (NeurIPS 2024)
**URL**: https://arxiv.org/abs/2406.00922
**Confidence**: high

### 5.3 Human-LLM Grounding Gap：LLM澄清率远低于人类

一项基于真实世界交互日志的研究发现[^637^]：
- **人类用户澄清LLM输出的频率**（6%）是**LLM澄清用户指令频率**（2%）的**3倍**
- 人类提出directed follow-up questions的频率是LLM assistant的**15.6倍**
- LLM assistant反而经常over-respond（45%的assistant turns），生成超出用户要求的verbose响应
- 人类很少over-respond（与LLM交互时0%，roleplay assistant时5%）[^637^]

> "In fact, the opposite occurs: people clarify LLM outputs (6%) 3 times as much as LLMs clarify user instructions (2%)."[^637^]

**Source**: "Navigating Rifts in Human-LLM Grounding: Study and Benchmark"
**URL**: https://arxiv.org/html/2503.13975v2
**Confidence**: high

### 5.4 Interactive Agents to Overcome Ambiguity

该研究评估了proprietary和open-weight模型在软件工程任务中处理模糊指令的能力[^633^]：

**关键发现**：
- **Claude Sonnet 3.5**在互动模式下可达到well-specified输入**80%**的性能水平
- **LLMs不会主动互动**，除非被明确prompted
- 只有Claude Sonnet 3.5在区分well-specified和underspecified输入方面达到较高准确率（84%）
- Open-weight模型（Llama 3.1 70B）在从用户提取信息方面困难[^633^]

> "LLMs do not interact unless explicitly prompted, and their ambiguity detection is highly sensitive to prompt variations."[^633^]

**Source**: "Interactive Agents to Overcome Ambiguity in Software Engineering"
**URL**: https://arxiv.org/html/2502.13069v1
**Confidence**: high

### 5.5 Ask-before-Plan：Proactive Agent Planning

Ask-before-Plan将澄清形式化为planning前的pre-planning阶段[^701^]。

**CEP (Clarification-Execution-Planning)框架**：
- **Clarification Agent**: 理解用户指令的不确定性，提出澄清问题
- **Execution Agent**: 利用工具与环境交互，收集信息
- **Planning Agent**: 综合澄清过程和交互历史，生成最终计划

**技术创新**：
- **Trajectory Tuning**: 使用过去交互序列fine-tune澄清和执行agent
- **Memory Recollection Mechanism**: 优化长上下文推理中的记忆效用[^701^]

**Source**: "Ask-before-Plan: Proactive Language Agents for Real-World Planning"
**URL**: https://arxiv.org/abs/2406.12639
**Confidence**: high

### 5.6 PAHF：Pre-Action Clarification with Memory

PAHF (Pre-Action Clarification, Preference Grounding & Post-Action Feedback)实现了一个关键洞察[^638^]：

> "The key insight: once memory contains the preference, the agent should act directly without asking. This prevents the 'annoying assistant' pattern of asking every time."[^638^]

**澄清触发条件**（满足任一才提问）：
1. 任务包含模糊引用
2. 任务涉及主观偏好
3. **记忆中没有相关偏好信息**

**如果记忆已提供上下文，直接行动而不提问**[^638^]。

**Source**: "PAHF Personalization Loop" - Hermes Agent
**URL**: https://github.com/NousResearch/hermes-agent/issues/362
**Confidence**: medium（项目文档，非学术论文）

---

## 6. 一轮一问 vs 批量提问

### 6.1 Prism框架：基于逻辑依赖的混合策略

Prism框架提供了目前最系统的答案——不是简单的一轮一问或批量，而是**基于逻辑依赖的智能排序**[^650^]。

**核心洞察**：
- 现有方法通过sequential questioning（逐轮）或parallel questioning（并行/批量）澄清用户意图
- 它们都未能解决核心挑战：**建模澄清问题之间的逻辑依赖关系**
- 在复杂意图场景中，问题之间存在prerequisite dependencies（先决条件依赖）

**Prism的解决方案**：
1. **Complex Intent Decomposition**: 将复杂意图分解为有层次结构的元素，识别逻辑依赖
2. **Logical Clarification Generation**: 
   - **同一层的问题相互独立** → 在一个turn中**批量呈现**（以interactive table形式）
   - **不同层的问题存在依赖** → **逐轮 sequential提问**
3. **Intent-Aware Reward**: 通过Monte Carlo Sampling模拟用户-LLM交互
4. **Self-Evolved Intent Tuning**: 迭代优化模型的逻辑澄清能力[^650^]

**实证结果**：
- 逻辑冲突率降至**11.5%**
- 用户满意度提升**14.4%**
- 任务完成时间减少**34.8%**
- 对话token数降至1,000以下[^650^]

> "Prism's ratings increase over time, demonstrating that its logically coherent interaction design effectively enhances the overall conversational experience."[^650^]

**对比发现**：ITIU和CollabLLM在turns 4-6时评分**下降**，表明用户满意度在较长交互中降低；而Prism的评分**随时间上升**[^650^]。

**Source**: "Prism: Towards Lowering User Cognitive Load in LLMs via Complex Intent Understanding" (WWW 2026)
**URL**: https://arxiv.org/pdf/2601.08653
**Confidence**: high

### 6.2 认知负荷理论视角

Prism框架基于**Cognitive Load Theory (CLT)**[^650^]：
- **Intrinsic load**: 任务固有复杂性
- **Extraneous load**: 不良交互设计带来的额外认知负担
- 有效设计应最小化extraneous load，管理intrinsic load

现有方法强调效率（并行澄清）或个性化（reward modeling），但"往往忽视来自** poorly structured question sequences**的隐藏认知成本——特别是在具有先决条件依赖的复杂意图场景中"[^650^]。

### 6.3 实践建议

基于Prism的研究，最优策略是[^650^]：
1. **先分析意图结构**：识别澄清问题之间的逻辑依赖
2. **无依赖的问题批量问**：同一层的问题一起呈现，减少交互轮数
3. **有依赖的问题逐轮问**：确保前置问题先回答，后续问题才有意义
4. **总轮数控制在3轮以内**：与业界共识一致

---

## 7. 反面证据与局限性

### 7.1 过度澄清的风险

**ClarifyGPT论文中的警告**：
> "Posing clarifying questions for every user requirement results in needless LLM-Human interactions on unambiguous requirements, which places an additional burden on users and hurts the code generation performance when producing off-topic questions."[^612^]

这意味着**对每个需求都提问**的策略是有害的。关键是有条件地提问——只在检测到歧义时才提问。

### 7.2 ASPI：寻求歧义澄清放大Prompt注入脆弱性

ASPI研究发现，当LLM agent主动寻求歧义澄清时，可能被攻击者利用[^594^]：
- 攻击者可以注入恶意的澄清回答
- 这种攻击利用agent对澄清反馈的信任
- 在high-stakes场景中需要额外的安全防护

**Source**: "ASPI: Seeking Ambiguity Clarification Amplifies Prompt Injection Vulnerability in LLM Agents"
**URL**: https://arxiv.org/html/2605.17324
**Confidence**: medium（安全研究领域，特定攻击场景）

### 7.3 多轮审查的反面证据

一项关于Cross-Context Review的研究发现[^649^]：
- 多轮review的F1显著低于单轮基线（-0.073, p<0.001）
- 额外轮次产生的false positives比发现的true errors更快
- **最优review轮数为1**

> "Every multi-turn variant produced lower F1 than the single-pass baseline, with three of four comparisons highly significant (p<0.001). Additional rounds generate false positives faster than they discover true errors."[^649^]

这提示了一个重要原则：**不是越多越好**。需要仔细评估每轮澄清的边际收益。

### 7.4 InfoQuest：当前模型信息收集效率低下

InfoQuest benchmark评估dialogue agents处理隐藏上下文的能力[^665^]：
- 所有当前assistants在有效收集关键信息方面 struggle
- 模型需要**多个turns**才能推断用户意图
- 模型经常default to generic responses without proper clarification
- 开源模型和proprietary模型之间存在显著差距[^665^]

**Source**: "InfoQuest: Evaluating Multi-Turn Dialogue Agents for Open-Ended Conversations with Hidden Context"
**URL**: https://arxiv.org/html/2502.12257v1
**Confidence**: high

### 7.5 MEDIQ：直接prompting LLM提问反而降低性能

MEDIQ的核心发现之一是counter-intuitive的[^664^]：
> "directly prompting state-of-the-art LLMs to ask questions degrades performance, indicating that adapting LLMs to proactive information-seeking settings is nontrivial"[^664^]

这意味着不能简单地告诉LLM"多问问题"——需要专门的设计（如abstention module）来决定何时问、问什么。

---

## 8. 最佳实践总结

### 8.1 被证明有效的做法

| 实践 | 证据来源 | 效果 |
|------|---------|------|
| **歧义检测后再提问**（非每个需求都问） | ClarifyGPT[^612^] | +13.87%~16.83% Pass@1 |
| **3轮澄清上限** | REMSA, DeerFlow, AgenticLU[^654^][^660^][^655^] | 覆盖97.4%的问题 |
| **基于EIG选择最优问题** | MedClarify[^591^], Mazzaccara[^597^] | 最大化信息效率 |
| **Abstention module**（不确定时问，确定时答） | MEDIQ[^664^] | +22.3%准确率 |
| **基于逻辑依赖的问题排序** | Prism[^650^] | -34.8%任务时间, +14.4%满意度 |
| **有记忆时直接行动，无记忆时澄清** | PAHF[^638^] | 避免"烦人助手"模式 |
| **Communicative dehallucination** | ChatDev[^448^] | Quality +21.7% (ablation) |
| **问题附带推荐选项** | AmbiSQL[^647^], Langchain-Chatchat[^631^] | 减少回答不确定性 |

### 8.2 被证明有害或效果不佳的做法

| 实践 | 证据来源 | 负面效果 |
|------|---------|---------|
| **对每个需求都提问** | ClarifyGPT[^612^] | 不必要的交互负担，离题问题损害性能 |
| **无限制的多轮澄清** | Cross-Context Review[^649^] | False positives增长快于true errors |
| **简单prompt LLM"多问问题"** | MEDIQ[^664^] | 直接降低性能 |
| **LLM过度verbose回应** | YapBench[^694^], ClarQ-LLM[^627^] | 认知负荷增加，用户满意度下降 |
| **无歧义检测的盲目提问** | Interactive Agents[^633^] | 浪费交互轮数 |

### 8.3 推荐架构：Detect–Clarify–Resolve–Learn Loop

综合所有证据，推荐的澄清架构为[^648^]：

1. **Detect**（检测）: 使用ambiguity classifier评分输入的歧义程度
   - 评估维度：intent clarity, constraint completeness, risk level
   - 低于阈值 → 进入Clarify；高于阈值 → 直接Resolve
   
2. **Clarify**（澄清）: 生成针对性的澄清问题
   - 先分解意图，识别逻辑依赖
   - 无依赖的问题 → 批量呈现（interactive table）
   - 有依赖的问题 → 逐轮sequential提问
   - 每轮选择EIG最高的问题
   - 最多3轮
   
3. **Resolve**（解决）: 使用澄清后的完整信息生成最终输出
   
4. **Learn**（学习）: 记录每次澄清交互
   - 存储Q&A为偏好记忆
   - 下次遇到类似场景直接行动

---

## 9. 关键设计建议

### 9.1 针对"轻brief + 精准澄清"场景的推荐策略

基于上述所有证据，为Agent spec设计场景推荐以下策略：

**1. 歧义检测先行**
- 使用code/test consistency check（如ClarifyGPT）或LLM-based ambiguity classifier
- 只在检测到歧义时才进入澄清流程
- 避免对所有brief都提问

**2. 澄清问题选择**
- 采样多个候选澄清问题（如8个）
- 使用EIG或类似的信息增益指标选择最优问题
- 优先选择能排除最大歧义空间的问题

**3. 一轮一问的交互模式**
- 保持现有"一轮一问"的基础设施
- 每轮问1个最高EIG的问题（除非多个问题完全独立，才可批量）
- 给用户附带推荐选项（multiple-choice format），减少回答负担[^647^]

**4. 轮数控制**
- **硬性上限3轮**（业界共识+数据支持）
- 实际上大多数问题2-3个问题即可解决[^612^]
- 达到上限后fallback到best-effort处理

**5. 记忆与学习**
- 将澄清Q&A存储为偏好记忆[^638^]
- 下次遇到相似场景时直接行动
- 避免"每次都要问"的烦人助手模式

**6. 问题质量自检**
- 生成问题后检查：是否relevant、是否comprehensive、是否useful[^612^]
- 避免off-topic问题损害用户体验

### 9.2 评估指标建议

| 指标 | 说明 | 目标值 |
|------|------|--------|
| Clarification Success Rate | 澄清后成功生成正确spec的比例 | >80% |
| Average Rounds per Task | 每任务平均澄清轮数 | <3 |
| User Satisfaction Score | 用户对澄清过程的满意度 | >4.0/5.0 |
| Task Completion Time | 含澄清的总任务完成时间 | 最小化 |
| Unnecessary Clarification Rate | 对无歧义需求错误提问的比例 | <5% |
| Information Gain per Question | 每个问题的平均信息增益 | 最大化 |

---

## 10. 研究空白与未来方向

1. **澄清轮数的动态自适应**：当前多采用固定3轮上限，能否根据实时估计的信息增益动态决定何时停止？
2. **跨领域迁移**：在代码生成中有效的澄清策略（ClarifyGPT）能否直接迁移到spec设计场景？
3. **用户个性化**：不同用户对澄清的容忍度不同，能否学习个人偏好调整澄清策略？
4. **多模态澄清**：结合代码片段、图表等非文本方式进行澄清
5. **澄清与安全的平衡**：如何在主动澄清的同时防范ASPI等prompt injection攻击？

---

## 附录：证据汇总表

| # | 来源 | 年份 | 核心发现 | Confidence |
|---|------|------|---------|------------|
| 1 | ChatDev (ACL 2024)[^448^] | 2024 | CDH机制使Quality从0.3953降至0.3094 | High |
| 2 | ClarifyGPT (FSE 2024)[^612^] | 2024 | Pass@1 +13.87%~16.83%, 平均2.85个问题 | High |
| 3 | MEDIQ (NeurIPS 2024)[^664^] | 2024 | Abstention +22.3%准确率, 直接prompting提问反而降低性能 | High |
| 4 | Prism (WWW 2026)[^650^] | 2026 | 逻辑澄清 -34.8%任务时间, +14.4%满意度 | High |
| 5 | Alexpaca[^682^] | 2024 | Self-play提升28%澄清问题质量 | High |
| 6 | ClarQ-LLM[^627^] | 2024 | GPT-4o成功率50.8% vs 人类85% | High |
| 7 | Human-LLM Grounding[^637^] | 2025 | LLM澄清率2% vs 人类6% | High |
| 8 | InfoQuest[^665^] | 2025 | 所有当前模型信息收集效率低下 | High |
| 9 | MedClarify[^591^] | 2026 | DEIG框架优化医学诊断提问 | Medium |
| 10 | OQA Benchmark[^598^] | 2025 | 即使SOTA模型也有1-2个问题planning gap | High |
| 11 | YapBench[^694^] | 2026 | LLM在模糊输入上过度生成而非简短澄清 | High |
| 12 | AGENT-CQ[^592^] | 2024 | LLM生成的问题在检索效果上优于人类 | Medium |
| 13 | Interactive SWE Agents[^633^] | 2025 | Claude 3.5互动后达80% well-specified性能 | High |
| 14 | Ask-before-Plan[^701^] | 2024 | CEP多agent框架有效处理模糊指令 | High |
| 15 | Adaptive Elicitation[^595^] | 2025 | EIG驱动的问题选择实现>12%相对改进 | High |
| 16 | PAHF[^638^] | 2026 | 记忆存在时直接行动，避免每次都问 | Medium |
| 17 | 多轮审查反面证据[^649^] | 2026 | 最优review轮数为1，多轮 degrades F1 | High |
| 18 | ChatDev复现[^628^] | 2024 | Iterative在某些任务上比one-shot更差 | Medium |
| 19 | EIG + DPO训练[^597^] | 2024 | DPO训练后EIG显著改善 | High |
| 20 | ASPI[^594^] | 2025 | 主动澄清放大prompt injection风险 | Medium |

---

*报告生成时间: 2025年*
*搜索覆盖: arXiv, ACM, NeurIPS, ACL, WWW等顶级会议论文及权威技术博客*
*总搜索次数: >25次独立搜索（中英文混合）*
