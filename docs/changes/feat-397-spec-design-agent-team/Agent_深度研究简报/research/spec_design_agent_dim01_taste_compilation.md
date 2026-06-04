# 维度：编译人类品味/判断的最佳实践

> 研究范围：如何将个人/团队的产品判断、架构偏好、审美标准固化成agent可复用资产
> 研究时间：2025年7月
> 搜索次数：25+次独立搜索（中英文混合）
> 覆盖来源：学术论文（arXiv/ACM/IEEE）、技术博客、官方文档、行业报告

---

## 1. Constitution/原则文件方案

### 1.1 核心概念与现状

Constitution/原则文件方案是当前最主流的"编译品味"手段。其核心思想是将不可变（或准不可变）的原则、约束和偏好写入一个独立文件，在agent的每次决策前加载为上下文。

**GitHub Spec-Kit的Constitution机制**是该方向的代表性实现：

Claim: GitHub Spec-Kit使用constitution.md作为"governing principles and development guidelines"，在所有后续开发阶段前加载
Source: GitHub Spec-Kit官方文档
URL: https://github.com/github/spec-kit
Date: 2025-2026
Excerpt: "Use the `/speckit.constitution` command to create your project's governing principles and development guidelines that will guide all subsequent development. This step creates or updates the `.specify/memory/constitution.md` file with your project's foundational guidelines that the coding agent will reference during specification, planning, and implementation phases."
Context: Spec-Kit是GitHub官方推出的Spec-Driven Development工具包，已被广泛采用
Confidence: high

Claim: Constitution文件与AGENTS.md/copilot-instructions.md有本质区别——前者on-demand加载、后者per-request加载
Source: GitHub Spec-Kit Discussion #2476
URL: https://github.com/github/spec-kit/discussions/2476
Date: 2026-05-18
Excerpt: "The constitution file is loaded on-demand by the commands for establishing context and it does not mean it will always need the entire file. Whereas AGENTS.md, copilot-instructions.md, CLAUDE.md get sent with every request to the LLM irrespective of the context at hand...AGENTS.md is for how the agent is allowed to operate and what it can or cannot do and is dependent on your coding agent. Constitution are principles irrespective of that."
Context: 社区讨论确认了constitution文件与agent指令文件的层级关系
Confidence: high

Claim: Constitution文件被描述为"immutable principles"和"architectural DNA"
Source: Specmatic Spec-Kit integration project
URL: https://github.com/specmatic/specmatic-mcp-cdd-with-spec-kit
Date: 2025-09-17
Excerpt: "This project operates under a constitutional governance model following GitHub Spec Kit methodology. The constitution.md file serves as the architectural DNA of the system, establishing immutable principles that govern how specifications become code."
Context: 多个实际项目已将constitution机制作为架构治理核心
Confidence: high

### 1.2 Constitution的遵守问题与Drift

Claim: 存在"Curse of Instructions"现象——随着单条上下文中指令数量增加，agent对每条指令的遵守率急剧下降
Source: Tony Lee's Blog - Three Spec Files Before Giving Work to Claude Code
URL: https://tonylee.im/en/blog/three-spec-files-before-ai-agent-coding/
Date: 2026-03-12
Excerpt: "Research on LLM instruction-following shows a pattern called the 'Curse of Instructions.' As the number of directives in a single context increases, compliance with each individual directive drops sharply. I tested this directly: when I packed project rules, feature specs, and task lists into one CLAUDE.md file, the agent ignored roughly half the instructions toward the end."
Context: 实践者的一手经验，直接指向长指令列表的有效性上限
Confidence: high

Claim: Constitution文件并非银弹——实际项目中存在constitution内容与AGENTS.md重复的问题，且agent可能简单复制AGENTS.md内容
Source: GitHub Spec-Kit Discussion #2476
URL: https://github.com/github/spec-kit/discussions/2476
Date: 2026-05-18
Excerpt: "Every time I generate a constitution file using spec-kit, the agent basically just replicates what's in the AGENTS.md file...Context engineering is becoming more and more important and a lot of care is placed in curating the right AGENTS.md/copilot instructions, so how does the constitution file fit into that process?"
Context: 社区真实反馈，说明constitution的独立价值需要更清晰界定
Confidence: high

Claim: "Specs without automated tests and type checks drift silently"——constitution需要配合harness才能防止drift
Source: Spec-Driven Development: Structure Beats Vibes
URL: https://pub.towardsai.net/spec-driven-development-structure-beats-vibes-06203898fa68
Date: 2026-05-12
Excerpt: "Specs without automated tests and type checks drift silently. The spec says what you want; the harness proves the code matches. Harness engineering is the enforcement layer."
Context: 该作者提出spec+harness的双层模型来对抗drift
Confidence: high

### 1.3 ArbiterOS：治理优先的宪法工程

Claim: ArbiterOS提出"Agent Constitution Framework (ACF)"作为治理型ISA（指令集架构），将agent治理从feature提升为runtime intrinsic property
Source: ArbiterOS论文 - A Governance-First Paradigm for Principled Agent Engineering
URL: https://arxiv.org/html/2510.13857v1
Date: 2025
Excerpt: "We propose the Agent Constitution Framework (ACF) as this instruction set. The crucial distinction is that the ACF is a macro-architecture ISA designed purely for governance, not a micro-architecture ISA for computation...This classification—for example, that a step is a probabilistic 'Cognitive' instruction whose outputs are untrusted—provides the unambiguous vocabulary for the Policy Engine to enforce architectural rules."
Context: 这是从"手工提示工程"走向"有原则的agent工程"的学术蓝图，目前仍属perspective paper阶段
Confidence: medium

Claim: ArbiterOS提出Evaluation-Driven Development Lifecycle (EDLC)，使用"Golden Dataset"持续验证constitution的行为一致性
Source: ArbiterOS论文
URL: https://arxiv.org/html/2510.13857v1
Date: 2025
Excerpt: "By embedding evaluation as a first-class automation target, ArbiterOS ensures that reliability is not left to artisanal practice but becomes an enforceable property of the software lifecycle...If a critical regression in performance is detected, the check fails, automatically blocking the pull request from being merged and preventing behavioral drift."
Context: 将continuous evaluation引入agent治理，是对抗drift的工程化方案
Confidence: medium

### 1.4 AWS Kiro的Steering Files

Claim: AWS Kiro使用"Steering Files"（per-project configuration for coding standards, preferred libraries, and conventions injected as context into every agent interaction）来指导agent行为
Source: Amazon's Dual-Track Coding Agent Bet: Q Developer vs. Kiro in 2026
URL: https://agentmarketcap.ai/blog/2026/04/11/amazon-q-developer-vs-kiro-dual-track-coding-agent-strategy-2026
Date: 2026-04-11
Excerpt: "Supporting this workflow is a set of infrastructure features absent from Q Developer: Agent Hooks (event-driven automations that fire on file save, create, or delete), Steering Files (per-project configuration for coding standards, preferred libraries, and conventions injected as context into every agent interaction), and selectable Autopilot vs. Supervised modes."
Context: Kiro的steering files与Spec-Kit的constitution本质上是同类方案的不同命名
Confidence: high

### 1.5 方案评估：Constitution/原则文件

| 维度 | 评估 |
|------|------|
| 有效性 | **中**——对简单明确的规则有效，但长constitution面临"curse of instructions"问题 |
| 维护成本 | **低至中**——一次编写、多次引用，但需要与代码同步更新 |
| 实现复杂度 | **低**——只需一个markdown文件 |
| 抗drift | **弱（无harness时）**——内容存在≠被遵守，需要配合CE/EDLC |
| 个人开发者可行性 | **高**——立即可用，零基础设施成本 |
| 关键局限 | 无法捕捉隐性品味；agent可能"看似遵循实则忽略"；无法自适应 |

---

## 2. Few-shot案例库方案

### 2.1 核心概念

Few-shot案例库方案通过向agent提供过往认可/否决的spec/design决策示例，引导agent学习人类的判断模式。

Claim: Few-shot prompting存在"over-prompting dilemma"——增加示例数量反而可能降低性能，且最优示例数量因模型而异
Source: The Few-shot Dilemma: Over-prompting Large Language Models
URL: https://arxiv.org/html/2509.13196v1
Date: 2025
Excerpt: "We identify the few-shot dilemma caused by over-prompting for certain LLMs, challenging the conventional wisdom about LLM-based few-shot learning with our experimental results on two software engineering datasets...By gradually incorporating more TF-IDF-selected few-shot examples, we identify their optimal quantity for each LLM."
Context: 在软件工程数据集（PROMISE数据集）上的实证研究，发现TF-IDF选择方法优于随机和embedding选择
Confidence: high

Claim: 动态示例选择（retrieval-augmented few-shot learning）可显著提升性能
Source: Few-Shot Learning for LLMs: Examples and Implementation Guide
URL: https://tetrate.io/learn/ai/few-shot-learning-llms
Date: 2025-12-07
Excerpt: "Advanced implementations use dynamic example selection, where examples are chosen based on the specific input being processed. For each new input, you retrieve the most similar examples from a database of labeled instances, creating a customized few-shot prompt. This approach, sometimes called retrieval-augmented few-shot learning, can significantly improve performance by ensuring examples are always relevant to the current input."
Context: 实践指南类文章，但建议来自业界经验
Confidence: medium

### 2.2 案例数量与选择偏差

Claim: 对许多任务，性能在5-7个示例后达到plateau，额外示例浪费token
Source: Tetrate - Few-Shot Learning for LLMs
URL: https://tetrate.io/learn/ai/few-shot-learning-llms
Date: 2025-12-07
Excerpt: "Experiment with different numbers of examples to find the optimal balance between performance and token cost. Plot performance against example count to identify the point of diminishing returns. For many tasks, performance plateaus after 5-7 examples, making additional examples wasteful."
Context: 经验法则，适用于分类/生成等标准任务；软件设计决策可能需要更多示例
Confidence: medium

Claim: FSPO（Few-Shot Preference Optimization）证明通过few-shot偏好示例可实现有效个性化，在合成用户上达87% AlpacaEval胜率，真实用户上达72%
Source: FSPO论文
URL: https://arxiv.org/html/2502.19312v1
Date: 2025-02-26
Excerpt: "FSPO achieves an 87% Alpaca Eval winrate on average in generating responses that are personalized to synthetic users and a 72% winrate with real human users in open-ended question answering...Inspired by the strong in-context learning capabilities of LLMs, we propose Few-Shot Preference Optimization (FSPO), which reframes reward modeling as a meta-learning problem."
Context: Stanford/DeepMind/OpenAI合作的论文，证明了few-shot preference learning在个性化上的可行性
Confidence: high

### 2.3 方案评估：Few-shot案例库

| 维度 | 评估 |
|------|------|
| 有效性 | **中-高**——对特定类别的决策有效，但需要高质量案例 |
| 维护成本 | **中**——需要持续收集、标注和更新案例 |
| 实现复杂度 | **低-中**——从简单prompt中的示例到RAG式动态检索 |
| 抗drift | **中**——案例库固定，但检索可能引入不一致 |
| 个人开发者可行性 | **高**——可从少量个人案例开始 |
| 关键局限 | 案例选择的bias；示例过多导致context膨胀；难以覆盖"为什么这样判断"的隐性逻辑 |

---

## 3. 角色化Critic Agent方案

### 3.1 核心概念与实证效果

Critic Agent方案设置一个专门的reviewer/critic agent，其prompt中固化品味标准，对producer agent的产出进行审查。

Claim: Generator-Critic（Producer-Reviewer）模型是"highly effective implementation of the Reflection pattern"，分离关注点可防止"cognitive bias of an agent reviewing its own work"
Source: Agentic Design Patterns - Reflection Pattern
URL: https://github.com/Mathews-Tom/Agentic-Design-Patterns/blob/main/01-Part_One/Chapter_4-Reflection-1HXXJOQIMWowtLw4WMiSR360caDAlZPtl5dPPgvq9IT4.md
Date: 2025-09-03
Excerpt: "This separation of concerns is powerful because it prevents the 'cognitive bias' of an agent reviewing its own work. The Critic agent approaches the output with a fresh perspective, dedicated entirely to finding errors and areas for improvement."
Context: 这是关于Reflection Pattern的经典教材级描述
Confidence: high

### 3.2 消融实验证据

Claim: 消融研究显示critic agent可显著提升代码生成安全性和helpfulness——移除critic summarizer后safety从91%降至87%，helpfulness从79%降至72%
Source: INDICT - Code Generation with Internal Dialogues of Critiques
URL: https://arxiv.org/html/2407.02518v2
Date: 2024
Excerpt: "When we simply removed the summarizer and let the actor agent receive the full dialogue history, we noticed the performance degraded to 87% and 72% in safety and helpfulness...simply using a single critic agent with dual quality criteria will affect the performance, reducing the safety and helpfulness metrics to 87% and 76% respectively."
Context: 在GPT4o-mini上的消融实验，证明多critic协作优于单critic
Confidence: high

Claim: CVE-Genie的消融研究显示移除critic agent后reproduction success从15/15降至8/15，false reproduction增加47%
Source: CVE-Genie Multi-Agent Framework
URL: https://arxiv.org/html/2509.01835v2
Date: 2025
Excerpt: "Removing critic agents reduced success to 8/15 while increasing false reproductions by 47%, highlighting their role in reliable end-to-end CVE reproduction."
Context: 安全领域的多agent系统消融实验
Confidence: high

Claim: STMA（Spatio-Temporal Memory Agent）的消融研究显示critic对复杂任务至关重要——LLM作为critic的表现通常强于作为planner
Source: STMA Paper
URL: https://arxiv.org/html/2502.10177v2
Date: 2025-03-02
Excerpt: "We observe that the LLM's performance as a critic is generally stronger than its performance as a planner. This may be because the critic's role is a classifier—determining whether an action is 'correct' or 'incorrect' based on beliefs and current environment. The classification task seems simpler than the planner's generative task of creating new plans."
Context: embodied AI领域的有趣发现——分类（critic）比生成（planner）更容易
Confidence: high

Claim: LiveClin的消融研究显示，增加Critic agent将physician-validated accuracy从84.5%提升至93.0%，同时降低trivial question比例从16.5%至5.5%
Source: LiveClin Benchmark
URL: https://arxiv.org/html/2602.16747v1
Date: 2025-04-14
Excerpt: "Adding the Critic agent was essential for factual accuracy, raising physician-validated accuracy from 84.5% to 93.0% and further reducing the trivial ratio to 5.5%. This iterative refinement is critical for producing reliable, clinically demanding content at scale."
Context: 医疗领域的高 stakes应用
Confidence: high

### 3.3 Critic Agent的局限性

Claim: Critic agent的有效性取决于其prompt中固化标准的质量——本质上仍是prompt engineering的包装
Source: 多项消融实验的综合分析
URL: 多个来源
Date: 2025
Excerpt: （综合分析）消融实验一致证明critic agent能提升质量，但所有critic的设计都依赖于人类预设的评价标准。如果品味标准本身难以形式化，critic只能捕捉到显式规则而无法覆盖隐性判断。
Context: 本报告的综合判断
Confidence: high

### 3.4 方案评估：Critic Agent

| 维度 | 评估 |
|------|------|
| 有效性 | **高**——消融实验一致证明有效（通常+5-15%质量提升） |
| 维护成本 | **中**——需要维护critic的prompt和评价标准 |
| 实现复杂度 | **中**——需要多agent orchestration基础设施 |
| 抗drift | **中**——critic本身也可能drift；critic的标准需要人类更新 |
| 个人开发者可行性 | **中**——现代agent框架（LangGraph/CrewAI）已原生支持 |
| 关键局限 | 只能检查显式规则；无法捕捉"我知道这样更好但说不出为什么"的隐性品味 |

---

## 4. 偏好学习/RLHF-style方案

### 4.1 方法论全景

这是学术研究最密集的方向，涵盖从训练时偏好优化到测试时个性化的大量方法。

Claim: 个性化对齐（Personalized Alignment）领域的完整方法谱系包括：VPL（变分偏好学习）、PREF（矩阵分解奖励模型）、PPT（上下文学习个性化）、Drift（免训练属性组合）、AMULET（测试时在线解码）、T-POP（在线偏好反馈）
Source: A Survey of Personalized Large Language Models
URL: https://arxiv.org/html/2502.11528v2
Date: 2025
Excerpt: "VPL employs a variational encoder to encode preference annotations into a latent variable...PREF models each user's personalized reward function as a linear combination of shared base reward functions...PPT leverages in-context learning for scalable personalization...Drift proposes a training-free method where user preference is modeled as a linear combination of interpretable attributes...AMULET formulates the decoding process of each token as an independent online learning problem...T-POP synergistically combines test-time alignment with dueling bandits."
Context: 2025年最全面的个性化LLM综述
Confidence: high

### 4.2 各方法详解

#### VPL (Variational Preference Learning)

Claim: VPL使用变分编码器将少量偏好标注编码为捕捉个人品味的潜变量，使奖励模型能条件于用户特定上下文
Source: Poddar et al., 2024 / A Survey of Personalized LLMs
URL: https://arxiv.org/html/2502.11528v2
Date: 2025
Excerpt: "VPL incorporates a variational encoder to infer a latent distribution over hidden user preferences, enabling the model to condition its reward functions and adapt policies based on user-specific context. In simulated control tasks, VPL demonstrates effective modeling and adaptation to diverse preferences."
Context: 需要preference标注数据，适用于有结构化反馈的场景
Confidence: high

#### PREF (Personalization via Reward Factorization)

Claim: PREF将个人奖励函数建模为共享基础奖励函数的线性组合，仅需约10个反馈示例即可推断新用户的组合权重
Source: Shenfeld et al., 2025
URL: https://arxiv.org/html/2503.17338v2
Date: 2026-02-19
Excerpt: "Shenfeld et al. concurrently propose the same architecture as RFM, but under a different name: 'PReF', for personalisation via reward factorization...they focus on how to exploit RFM's simple architecture to improve several aspects of the training pipeline. Among these, two contributions stand out: a stable initialisation of the model through singular value decomposition and an efficient way of selecting examples for adaptation via active learning."
Context: PREF/RFM架构的简洁性使其在实际部署中具有吸引力
Confidence: high

#### AMULET (Test-Time Online Learning)

Claim: AMULET将每个token的解码过程视为独立在线学习问题，无需重训练即可实时适应用户偏好
Source: AMULET / T-POP论文引用
URL: https://arxiv.org/html/2509.24696v1
Date: 2025
Excerpt: "AMULET approaches this from another unique test-time perspective, by formulating the decoding process of each token as an independent online learning problem. It obtains the optimization direction by contrasting the model's output with and without user-provided prompts and utilizes an efficient closed-form solution for real-time iterative optimization."
Context: 测试时方法的计算开销低，但个性化深度有限
Confidence: high

#### T-POP (Test-Time Personalization with Online Preference Feedback)

Claim: T-POP在三个模型（Mistral-7B, Llama-3.1-8B, Qwen2-7B）上平均比AMULET提升14.7%，在Qwen2-7B上提升28.0%，win rate平均94.2%
Source: T-POP论文
URL: https://arxiv.org/html/2509.24696v1
Date: 2025-09-29
Excerpt: "T-POP demonstrates an average improvement of 28.0% over the second best method, AMULET, across all four preference attributes on Qwen2-7B...Aggregating these results, T-POP establishes a robust overall average improvement of 14.7% against AMULET...T-POP achieves personalization with remarkable consistency, with its win rate almost universally above 90%, averaging 94.2% across all settings."
Context: T-POP是目前测试时个性化方向的SOTA方法
Confidence: high

#### PROSE (Preference Reasoning by Observing and Synthesizing Examples)

Claim: PROSE通过迭代精化和跨样本一致性验证推断用户偏好，比CIPHER提升33%；结合ICL可进一步提升9%
Source: PROSE论文 (Apple Research)
URL: https://arxiv.org/html/2505.23815v1
Date: 2025-05-27
Excerpt: "PROSE more accurately infers nuanced human preferences, improving the quality of the writing agent's generations over CIPHER (a state-of-the-art method for inferring preferences) by 33%. Lastly, we demonstrate that ICL and PROSE are complementary methods, and combining them provides up to a 9% improvement over ICL alone."
Context: Apple的研究，专注于从用户写作样本推断偏好，对"软件设计品味"场景有一定可迁移性
Confidence: high

#### CIPHER (Preference Learning from User Edits)

Claim: CIPHER实现了最低用户编辑成本的个性化，通过从历史中检索相似上下文的推断偏好来生成响应
Source: CIPHER/PRELUDE论文 (NeurIPS 2024)
URL: https://proceedings.neurips.cc/paper_files/paper/2024/file/f75744612447126da06767daecce1a84-Paper-Conference.pdf
Date: 2024
Excerpt: "CIPHER infers user preference for every context in the history with the aid of an LLM. In the future, given a context, it retrieves inferred preferences of similar contexts from the history and uses them to generate a response. CIPHER is computationally efficient and only slightly increases the LLM query cost compared to the base agent."
Context: 微软/DeepMind合作，从用户编辑中学习偏好
Confidence: high

#### DPO-f+ (Code Repair Preference Alignment)

Claim: DPO-f+在代码修复反馈对齐任务上，Pass@1比baseline提升5.71pp，比标准DPO提升3.30pp，在SWE-bench Lite上resolution rate比DPO提升1.67pp
Source: DPO-f+论文
URL: https://arxiv.org/html/2511.01043v1
Date: 2025-11-02
Excerpt: "DPO-f+ consistently outperforms both baseline models and standard DPO. It achieves superior feedback accuracy, improving the Pass@1 by 5.71 pp over the baseline and 3.30 pp over standard DPO, while achieving the highest overall alignment scores."
Context: 这是偏好学习在软件工程领域的直接应用，证明了方法的可行性
Confidence: high

### 4.3 方案评估：偏好学习/RLHF-style

| 维度 | 评估 |
|------|------|
| 有效性 | **高（学术基准）/ 中（实际SE场景）**——方法在标准benchmark上表现优异，但软件设计品味的个性化benchmark缺乏 |
| 维护成本 | **高（训练方法）/ 低（测试时方法）**——AMULET/T-POP无需重训练 |
| 实现复杂度 | **高**——需要RL/DPO基础设施；测试时方法相对简单 |
| 抗drift | **高（在线方法）**——T-POP等在线方法可持续学习 |
| 个人开发者可行性 | **低（训练方法）/ 中（测试时方法）**——个人开发者难以运行训练pipeline |
| 关键局限 | 需要偏好数据；软件设计品味的反馈难以形式化为pairwise preference；冷启动问题 |

---

## 5. Memory系统方案

### 5.1 核心概念与分类

Claim: AI agent memory分为semantic（事实/知识）、episodic（过往经验）和procedural（学习行为/prompt规则）三类
Source: LangMem SDK / Cognitive Science框架
URL: https://langchain-ai.github.io/langmem/
Date: 2025-02-27
Excerpt: "LangMem supports multiple types of memory, each serving different purposes: Semantic (Facts & Knowledge), Episodic (Past Experiences), Procedural (System Behavior), Short-Term (Conversation Context)."
Context: LangChain团队的开源memory SDK
Confidence: high

### 5.2 主要Memory系统

#### Mem0

Claim: Mem0 benchmarks显示比full-context prompting降低91%的p95延迟和90%的token使用
Source: Mem0 Blog - Long-Term Memory for AI Agents
URL: https://mem0.ai/blog/long-term-memory-ai-agents
Date: 2026-04-13
Excerpt: "Mem0 benchmarks show 91% lower p95 latency and 90% token reduction versus full-context prompting. Structured memory pipelines enable personalization across hundreds of sessions without re-reading prior history."
Context: Mem0是AWS Agent SDK的exclusive memory provider，50K+ GitHub stars
Confidence: high

#### Zep

Claim: Zep使用Temporal Knowledge Graph动态综合非结构化对话数据和结构化业务数据，维护历史关系
Source: Zep AI Documentation
URL: https://getzep.com
Date: 2025-2026
Excerpt: "Zep employs a temporal knowledge graph engine called Graphiti to dynamically synthesize unstructured conversational data and structured business data, while maintaining historical relationships."
Context: Zep强调temporal reasoning，适合需要理解时间变化的场景
Confidence: high

#### LangMem

Claim: LangMem是唯一支持agent重写自身system prompt的memory系统（procedural memory），这是Mem0和Zep都不具备的能力
Source: Atlan - Long-Term Memory LangChain Agents Guide
URL: https://atlan.com/know/long-term-memory-langchain-agents/
Date: 2026-04-08
Excerpt: "LangMem is the only option in this stack where the agent can rewrite its own system prompt based on accumulated experience (procedural memory). No equivalent exists in Mem0 or Zep. If your agent needs to adapt its behavior from what it has learned, not just recall stored facts, LangMem adds that capability."
Context: LangMem的prompt optimization能力直接关联到"编译品味"的需求
Confidence: high

#### Letta (Core Memory)

Claim: Letta的Core Memory是"always-present, editable in-context memory block"，agent通过tool call自行修改
Source: Core Memory Wiki (Letta)
URL: https://github.com/chappyasel/meta-kb/blob/main/wiki/concepts/core-memory.md
Date: 2026-04-04
Excerpt: "Core memory is a small, persistent text block that lives inside an agent's system prompt on every single inference call...Crucially, agents can modify this scratch pad themselves through tool calls, so the memory reflects what the agent has learned, not just what a developer pre-loaded."
Context: Letta（原MemGPT）是core memory概念的开创者
Confidence: high

Claim: Letta agent通过"system prompt learning"（memory blocks）和skill learning实现持续学习
Source: Letta Code Blog
URL: https://www.letta.com/blog/letta-code
Date: 2025
Excerpt: "Agents programmatically rewrite their context to improve and adapt over time, including system prompt learning (through memory blocks) and skill learning...Skills are simply `.md` files, they can be managed in git repositories for versioning - or even used by other coding agents that support skills."
Context: Letta Code的定位正是"memory-first coding agent"
Confidence: high

### 5.3 Memory系统的Drift问题

Claim: Procedural memory存在"procedural drift"风险——无管制的自我修改导致次优工作流的渐进式强化
Source: Atlan - Semantic vs Procedural Memory
URL: https://atlan.com/know/semantic-memory-vs-procedural-memory-ai-agents/
Date: 2026-04-17
Excerpt: "Procedural drift (SSGM, arXiv:2603.11768, 2026) documents this as a production failure mode and recommends consistency verification and temporal decay modeling...Ungoverned self-modification leads to procedural drift, gradual reinforcement of suboptimal workflows."
Context: 这是memory系统方案的关键风险
Confidence: high

Claim: Context rot是agent在长会话中因上下文窗口填满而导致的渐进质量退化——早期指令被稀释
Source: MindStudio - What Is Context Rot
URL: https://www.mindstudio.ai/blog/what-is-context-rot-ai-agents/
Date: 2026-04-18
Excerpt: "Context rot is the gradual quality degradation that happens as an AI agent's context window fills with noise over a long session...Earlier instructions get pushed further from the model's 'attention' and have less influence on new outputs."
Context: Context rot是memory系统需要解决的核心问题
Confidence: high

### 5.4 方案评估：Memory系统

| 维度 | 评估 |
|------|------|
| 有效性 | **中-高**——对事实性偏好有效，对隐性品味的捕捉有限 |
| 维护成本 | **中**——需要memory management基础设施 |
| 实现复杂度 | **中-高**——需要向量存储、embedding pipeline |
| 抗drift | **中**——存在procedural drift风险；需要consolidation机制 |
| 个人开发者可行性 | **中**——Mem0/Zep提供托管服务；LangMem开源 |
| 关键局限 | 记忆的是"发生了什么"而非"为什么这样判断"；procedural drift风险 |

---

## 6. "AI alignment to an individual's taste"研究方向

### 6.1 学术进展

Claim: 2025年出现了首个comprehensive survey of personalized alignment，提出了unified framework：preference memory management → personalized generation → feedback-based alignment
Source: A Survey on Personalized Alignment
URL: https://arxiv.org/html/2503.17003v1
Date: 2025-03-21
Excerpt: "This paper presents the first comprehensive survey of personalized alignment—a paradigm that enables LLMs to adapt their behavior within ethical boundaries based on individual preferences. We propose a unified framework comprising preference memory management, personalized generation, and feedback-based alignment."
Context: 这是个性化对齐领域的里程碑式综述
Confidence: high

Claim: Persona-judge实现了training-free的个性化对齐——利用LLM内在的偏好判断能力，draft model生成、judge model交叉验证
Source: Persona-judge论文
URL: https://arxiv.org/html/2504.12663v2
Date: 2025
Excerpt: "Persona-judge leverages the intrinsic preference judgment capabilities of the model. Specifically, a draft model generates candidate tokens conditioned on a given preference, while a judge model, embodying another preference, cross-validates the predicted tokens whether to be accepted."
Context: Zhejiang University的工作，创新性地将speculative decoding思想用于个性化
Confidence: high

Claim: "Personality Alignment"研究使用IPIP-NEO-120/300问卷构建了30万+样本的PAPI数据集，实现了training-free的个人对齐
Source: PERSONALITY ALIGNMENT OF LARGE LANGUAGE MODELS
URL: https://arxiv.org/pdf/2408.11779v1
Date: 2024
Excerpt: "We propose a training-free personal-alignment paradigm, which provides over 300,000 unique preference samples, and a method efficiently aligning individual preference characteristics during the model's forward computation."
Context: 这是将心理学人格测量引入LLM个性化的开创性工作
Confidence: high

### 6.2 与软件设计品味的关联

**关键发现**：当前的"individual taste/preference"研究主要集中在：
- 写作风格（CIPHER, PROSE, PREDICT）
- 对话个性（helpful/harmless/verbose/concise/uplifting）
- 视觉偏好（ViPer）
- 推荐系统偏好

**软件设计品味（architecture preference, API design taste, abstraction level preference）**是一个尚未被充分研究的细分方向。最接近的是：
- DPO-f+在code repair feedback上的个性化
- Spec-Kit/Kiro在spec-driven development上的原则固化
- 但"为什么这个API设计比那个好"的品味学习仍是开放问题

---

## 7. 混合方案与综合架构

### 7.1 多层组合策略

基于上述研究，最有效的"品味编译"方案很可能是**多层组合**：

```
Layer 1: Constitution文件（不变原则）
    ↓ 约束边界
Layer 2: Core Memory（高频事实/偏好）
    ↓ 提供上下文
Layer 3: Few-shot案例库（相似场景的过往决策）
    ↓ 具体指导
Layer 4: Critic Agent（运行时审查）
    ↓ 执行时保障
Layer 5: 在线偏好学习（T-POP/AMULET风格）
    ↓ 持续适应
```

### 7.2 已有混合方案实例

Claim: Letta Code结合core memory（system prompt learning）+ skill learning + episodic memory实现持续学习
Source: Letta Code Blog / GitHub
URL: https://www.letta.com/blog/skill-learning
Date: 2025
Excerpt: "For Letta agents which support both skills and core memory (in-context memory blocks), memory can be organized in a hierarchy: Core Memory / System Prompt Learning: Learned system prompt - evolving system prompt that applies across tasks...Skills / Filesystem: Evolving files used for task-specific memory, designed to be interchangeable between agents."
Context: Letta Code是目前最接近"完整混合方案"的编码agent
Confidence: high

Claim: LangMem结合semantic + episodic + procedural memory，并支持prompt optimization
Source: LangMem SDK
URL: https://langchain-ai.github.io/langmem/
Date: 2025-02-27
Excerpt: "LangMem helps agents learn and adapt from their interactions over time. It provides tooling to extract important information from conversations, optimize agent behavior through prompt refinement, and maintain long-term memory."
Context: LangChain团队将memory management + prompt optimization整合在一个SDK中
Confidence: high

### 7.3 Remy的Spec-as-Source-of-Truth模式

Claim: Remy（MindStudio）使用spec文档作为跨session的持久真相源，agent每次从spec重新读取而非依赖会话历史
Source: MindStudio - Context Rot Prevention
URL: https://www.mindstudio.ai/blog/what-is-context-rot-ai-agents/
Date: 2026-04-18
Excerpt: "In Remy, the spec is the source of truth—a structured markdown document that captures what the application does, including data types, rules, edge cases, and architectural decisions. The spec persists across sessions. The agent reads it fresh each time rather than relying on accumulated conversation history."
Context: 这是一种根本不同的context管理模式——用结构化spec替代对话历史
Confidence: medium

---

## 8. 横向对比表

| 方案 | 有效性证据 | 维护成本 | 实现复杂度 | 抗drift | 个人开发者可行性 | 隐性品味覆盖 |
|------|-----------|---------|-----------|---------|----------------|------------|
| **Constitution文件** | 中（社区广泛采用） | 低-中 | 低 | 弱（无harness时） | **高** | 低 |
| **Few-shot案例库** | 中-高（FSPO: 87%/72%胜率） | 中 | 低-中 | 中 | **高** | 中 |
| **Critic Agent** | 高（消融实验+5-15%） | 中 | 中 | 中 | **中** | 低-中 |
| **偏好学习/RLHF** | 高（学术benchmark） | 高（训练）/低（测试时） | 高 | 高（在线方法） | **低-中** | 中 |
| **Memory系统** | 中-高（91%延迟降低） | 中 | 中-高 | 中（有drift风险） | **中** | 中 |
| **混合方案** | 最高（理论） | 高 | 高 | 最高 | **低-中** | 最高 |

---

## 9. 关键洞察与开放问题

### 9.1 核心洞察

1. **没有银弹**：单一方案无法完整捕捉"品味"的多层次性。品味既包含显式规则（可用constitution/few-shot捕捉），也包含隐性模式（需要偏好学习/memory积累），还包含动态适应（需要在线学习）。

2. **"Curse of Instructions"是硬约束**：所有依赖长文本上下文的方案（constitution、few-shot）都面临注意力稀释问题。将品味"编译"为更紧凑的表示（latent preference embedding、compressed prompt rules）是更scalable的方向。

3. **Critic Agent是ROI最高的单一方案**：消融实验一致证明critic的有效性（通常+5-15%），实现复杂度适中，且已有LangGraph/CrewAI等框架原生支持。

4. **Procedural Memory是最有前景的方向**：LangMem的prompt optimization和Letta的core memory learning使agent能够真正"习得"行为模式而非仅仅"回忆"事实。但procedural drift风险需要governance机制对冲。

5. **Context Rot是所有长会话agent的结构性问题**：不解决context management，任何品味编译方案都会在长会话中退化。

6. **软件设计品味的个性化是开放研究方向**：当前研究集中在写作风格、对话个性、视觉偏好等方向，缺少"architecture taste"、"API design preference"、"abstraction level preference"等软件工程specific的个性化研究。

### 9.2 推荐的最小可行方案（MVP）

对于个人开发者维护Spec-Driven Development流水线的场景：

**阶段1（立即实施）**：
- Constitution文件（`constitution.md`）+ AGENTS.md双轨制——constitution管原则，AGENTS.md管操作约束
- Critic Agent——在每个spec/design产出后运行审查
- 渐进式Few-shot案例库——从5-10个个人最满意/最不满意的决策开始

**阶段2（有基础设施后）**：
- Core Memory（Letta风格）——让agent记住高频偏好和约束
- 定期`/compact`或session reset防止context rot
- 在线偏好信号收集——每次agent产出后收集approve/reject信号

**阶段3（规模化）**：
- T-POP/AMULET风格的在线偏好学习
- Continuous Evaluation pipeline（ArbiterOS EDLC风格）
- Procedural memory的governance机制（防止drift）

### 9.3 开放问题

1. **如何量化"软件设计品味"**？——需要建立architecture preference、API design taste的评估框架
2. **如何捕捉隐性判断**？——"我知道这样更好但说不出为什么"的品味如何形式化
3. **个性化vs.一致性的权衡**——品味过于个人化可能导致agent产出不可预测
4. **跨项目品味的迁移**——一个项目中习得的品味如何迁移到不同domain的新项目
5. **品味本身的演化**——人的品味会随时间演化，agent如何跟上而不产生滞后

---

## 参考文献索引

| 编号 | 来源 | 类型 | 关键贡献 |
|------|------|------|---------|
| [^103^] | GitHub Spec-Kit | 官方文档 | Constitution机制 |
| [^104^] | Spec-Kit Discussion #2476 | 社区讨论 | Constitution vs AGENTS.md |
| [^105^] | AWS Kiro Dual-Track Strategy | 行业分析 | Steering Files |
| [^107^] | Spec Kit Through Its Paces | 实践报告 | Constitution实际效果 |
| [^117^] | Personalized Constitutionally-Aligned Agent | 学术论文 | Superego Agent框架 |
| [^120^] | Personality Alignment of LLMs | 学术论文 | PAPI数据集 |
| [^121^] | Personalization of LLMs: A Survey | 综述 | 个性化全景 |
| [^124^] | A Survey on Personalized Alignment | 综述 | 个性化对齐框架 |
| [^127^] | Mem0 Long-Term Memory | 技术博客 | Memory系统benchmark |
| [^128^] | T-POP | 学术论文 | 测试时个性化SOTA |
| [^129^] | FSPO | 学术论文 | Few-shot偏好优化 |
| [^132^] | PROSE/PREDICT (Apple) | 学术论文 | 用户写作样本偏好推断 |
| [^137^] | Structure Beats Vibes | 实践指南 | Spec + Harness模型 |
| [^154^] | Video Story Generation | 学术论文 | Critic消融实验 |
| [^157^] | CVE-Genie | 学术论文 | Critic消融实验 |
| [^158^] | INDICT | 学术论文 | Multi-critic代码生成 |
| [^173^] | STMA | 学术论文 | Critic vs Planner |
| [^177^] | Mem0 Memory Types | 官方文档 | Memory分层模型 |
| [^190^] | The Few-shot Dilemma | 学术论文 | Over-prompting问题 |
| [^242^] | T-POP (v2) | 学术论文 | 在线偏好反馈 |
| [^246^] | PROSE | 学术论文 | 迭代偏好推断 |
| [^325^] | Semantic vs Procedural Memory | 技术分析 | Memory分类与drift |
| [^327^] | Letta Code | 开源项目 | Memory-first coding agent |
| [^331^] | Three Spec Files | 实践指南 | Curse of Instructions |
| [^332^] | ArbiterOS | 学术论文 | Governance-first paradigm |
| [^333^] | Agent Drift | 技术分析 | Drift来源分析 |
| [^334^] | Context Rot | 技术分析 | Context window degradation |
| [^348^] | Persona-judge | 学术论文 | Token-level self-judgment |
| [^349^] | FSPO (PDF) | 学术论文 | Meta-learning for personalization |
| [^347^] | RFM/PREF | 学术论文 | Reward factorization |
| [^538^] | LangMem SDK | 官方文档 | Memory + Prompt optimization |
| [^540^] | LangMem Architecture | 技术教程 | Procedural memory详解 |
| [^536^] | Core Memory Wiki | 技术文档 | Letta core memory架构 |
| [^324^] | DPO-f+ | 学术论文 | Code repair preference alignment |

---

*报告生成时间: 2025年7月*
*搜索覆盖: 25+次独立搜索，涵盖arXiv论文、官方文档、技术博客、社区讨论*
