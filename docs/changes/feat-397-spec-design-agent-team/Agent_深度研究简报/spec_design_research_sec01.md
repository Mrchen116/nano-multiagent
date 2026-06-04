## 1. P0核心问题深度综述（一）：编译人类品味/判断的最佳实践

### 1.1 问题本质：为什么Agent需要"品味"

#### 1.1.1 "张小龙"类比——内化的品味是接住轻brief的前提

在软件产品领域，一个广为人知的叙事是：马化腾之所以放心将微信产品交给张小龙，不仅因为张小龙懂得产品规则，更因为他内化了超越规则本身的"品味"（taste）——面对一条模糊的brief（如"做一款适合老年人的支付功能"），张小龙能凭直觉命中那个"对的"设计方向，而无需将每一条判断准则显式罗列[^103^]。这种能力恰好是当前multi-agent系统在spec对齐与design对齐环节中最匮乏的要素。

一个基于LLM的agent pipeline若要稳定地替代人类完成从brief到spec再到design的转换，核心瓶颈并不在于语法生成或框架调用——这些能力已被代码生成模型充分覆盖——而在于当brief存在ambiguity时，agent能否做出与人类产品决策者一致的判断选择。研究表明，在从轻brief到正式spec的转换中，仅2%的早期错位（如一个隐含的优先级假设偏差）可在后续环节被放大为40%的末端设计缺陷[^332^]。这一级联效应说明，品味的注入不是"锦上添花"，而是决定pipeline最终产出的结构性变量。

品味的独特性体现在它处理的是不可完全形式化的偏好权衡。当一名人类架构师选择"使用枚举类型而非字符串来表示状态"时，其背后可能同时涉及类型安全偏好、可维护性考量、团队习惯以及对未来扩展路径的直觉判断。这些维度中的一部分可以写入constitution文件（"优先使用类型安全方案"），但另一部分——如"在这个特定上下文中，类型安全的收益超过了它带来的boilerplate成本"——取决于对具体情境的隐性感知，这正是品味的领地[^331^]。

#### 1.1.2 现有方案的结构性缺陷：可形式化的偏好不是真正的品味

所有现有"编译品味"方案面临一个根本性张力：能被显式写下来的规则是"品味的最小公约数"，而真正的品味体现在对模糊地带的判断中[^103^][^332^]。Constitution文件可以规定"不使用全局状态"，但无法规定"在这种情况下全局状态可能是最优方案"。案例库可以提供过往决策的参考，但无法覆盖从未遇到过的新情境。偏好学习可以捕获统计模式，但需要大量标注数据来训练。

这一张力的学术表达来自个性化LLM领域的最新综述：当前所有个性化方法验证于对话风格、写作偏好和视觉审美等场景，而"软件架构品味"（architecture taste）——包括API设计偏好、抽象层次选择、模块边界判断——是一个尚未被充分研究的细分方向[^121^][^124^]。P-Check框架的作者指出，"某些偏好因素难以外化为明确规则（如微妙的tone、style、feel）"[^1136^]，这一判断在软件设计场景中同样成立。

从实践角度看，GitHub Spec-Kit的社区反馈提供了直接证据：当开发者使用spec-kit生成constitution文件时，agent倾向于简单复制AGENTS.md中已有的操作约束，而非提炼出独立的设计原则[^104^]。这说明即使在设计constitution机制的平台上，区分"可形式化的规则"与"真正的品味"仍然是一个未解决的问题。

这并不意味着编译品味的努力是无效的。研究证据表明，一个渐进的、多层次的品味内化路径是可行的：从显式规则（constitution）出发，通过运行时审查（critic agent）和案例学习（few-shot）逐步积累隐性模式，最终借助memory系统实现持续适应[^327^][^538^]。关键在于接受一个核心约束——不要追求100%自动化，在品味判断上，human-on-the-loop是feature不是bug[^332^]。

### 1.2 五大候选方案对比

基于对arXiv/ACM/IEEE文献、官方文档和技术博客的系统调研，本报告识别出五种已被实证研究的品味编译方案。以下按证据强度和实现可行性逐一分析。

#### 1.2.1 Constitution/原则文件：广泛采用但面临Curse of Instructions

Constitution文件方案是当前最主流的品味编译手段。GitHub Spec-Kit使用`constitution.md`作为"governing principles and development guidelines"，在所有后续开发阶段前加载[^103^]；AWS Kiro采用同质方案，以"Steering Files"形式注入项目特定的编码标准和库偏好[^105^]；ArbiterOS则将constitution提升为治理型ISA（指令集架构），提出Agent Constitution Framework（ACF）作为agent工程的宏观指令集[^332^]。

该方案的核心优势在于零基础设施成本——一个markdown文件即可启动，个人开发者可立即采用。然而，它面临三个已被实证确认的限制。

第一，"Curse of Instructions"现象：随着单条上下文中指令数量增加，agent对每条指令的遵守率急剧下降。实践者报告称，当将项目规则、功能spec和任务列表打包进一个CLAUDE.md文件时，agent对后半部分指令的遵守率约为50%[^331^]。这一发现与多项学术研究一致——长指令列表的注意力稀释是LLM的结构性限制。

第二，constitution文件无法捕捉隐性判断。当一条原则写明"优先使用不可变数据结构"时，agent知道规则本身，但不知道"何时应该打破这条规则"。 ArbiterOS提出的Evaluation-Driven Development Lifecycle（EDLC）试图通过对"Golden Dataset"的持续验证来缓解这一问题，要求当关键性能回归被检测到时自动阻止合并[^332^]。但EDLC本质上是对constitution遵守情况的监控机制，而非对隐性品味的捕获机制。

第三，constitution存在drift风险。实践报告指出，"Specs without automated tests and type checks drift silently"——constitution内容的存在不等于被遵守，需要配合harness（自动化测试/类型检查）才能防止agent逐渐偏离[^137^]。

综合评估，constitution文件是品味编译的合理起点，但应被视作约束边界的工具而非完整的品味表达。对于个人开发者，建议将constitution长度控制在20条原则以内，优先覆盖"不可违反的硬约束"而非"偏好性的软指导"。

#### 1.2.2 Few-shot案例库：FSPO证明87%/72%胜率，5-7个示例后收益递减

Few-shot案例库方案通过向agent提供过往认可或否决的spec/design决策示例，引导agent学习人类的判断模式。该方案的理论基础来自LLM的in-context learning能力，其实证支撑来自FSPO（Few-Shot Preference Optimization）框架。

FSPO由Stanford、DeepMind和OpenAI合作提出，将奖励建模重新表述为meta-learning问题，证明通过few-shot偏好示例可实现有效个性化：在合成用户上达到87% AlpacaEval胜率，在真实用户上达到72%[^129^]。这一结果表明，少量高质量案例的示范效应远超长文本规则的约束效应——agent从"看这个例子中人类是怎么做的"中学到的品味，比从"遵循以下20条原则"中获得的更贴近真实偏好。

然而，few-shot方案存在明确的收益递减边界。研究表明，对多数任务，性能在5-7个示例后达到plateau，额外示例浪费token且可能引入噪声[^190^]。更关键的是，存在"over-prompting dilemma"——增加示例数量反而可能降低性能，且最优数量因模型而异[^190^]。这一发现对实践有直接影响：案例库不应追求规模，而应追求精选——每个案例都应代表一个独特的品味判断情境。

动态示例选择（retrieval-augmented few-shot learning）提供了缓解路径。通过基于当前输入的相似性检索，从案例库中选择最相关的示例，可在保持context紧凑的同时提升相关性。但此方法需要embedding pipeline和向量存储的基础设施，对个人开发者增加了中等的实现复杂度。

在软件设计品味场景中，案例库的独特价值在于它可能比原则文件更能捕获"模糊地带品味"。当一条案例展示"在类似情境中选择了方案A而非方案B"时，agent不仅学习选择本身，还学习到该选择的上下文敏感性——这是constitution文件难以表达的维度。

#### 1.2.3 角色化Critic Agent：ROI最高，消融实验一致证明+5-15%质量提升

在所有单一方案中，Critic Agent拥有最一致的实证支持。其核心架构是Generator-Critic（Producer-Reviewer）模型——由一个producer agent生成产出，由一个独立的critic agent基于固化的评价标准进行审查。这一模式被描述为"highly effective implementation of the Reflection pattern"，其关键优势在于分离关注点可防止agent"审查自己工作"时的认知偏见[^158^]。

消融实验证据构成了该方案最有力的支撑。表1汇总了跨领域、跨任务类型的关键消融结果。

| 研究 | 领域 | Critic配置 | 有Critic | 无Critic | 质量提升 |
|------|------|-----------|---------|---------|---------|
| INDICT[^158^] | 代码生成 | Multi-critic (safety+helpfulness) | Safety 91%, Helpfulness 79% | Safety 87%, Helpfulness 72% | +4-7pp |
| CVE-Genie[^157^] | 安全漏洞复现 | Critic agent (reproduction验证) | 15/15成功 | 8/15成功 | +47%误报降低 |
| LiveClin[^154^] | 临床内容生成 | Critic agent (事实准确性) | 93.0%准确率 | 84.5%准确率 | +8.5pp |
| STMA[^173^] | 时空规划 | LLM as critic vs planner | Critic准确率 > Planner准确率 | — | Critic > Planner |

表1：Critic Agent消融实验跨领域汇总。pp = percentage points。所有实验均在控制变量条件下进行，"无Critic"条件指移除critic agent或将critic功能合并到producer中。

表1的数据揭示了一个稳定的模式：critic agent的引入通常带来5-15%的质量提升，且这一提升在代码生成、安全验证、医疗内容和规划任务中跨领域复现。INDICT研究进一步表明，多critic协作（分别关注safety和helpfulness两个维度）优于单critic双标准配置[^158^]——这一发现与Insight 2中"打破对称性"的原则形成呼应。

STMA研究提供了一个更深层的洞察：LLM作为critic的表现通常强于作为planner的表现[^173^]。这可能是因为critic的角色本质上是分类（判断一个动作"正确"或"错误"），而planner的角色是生成（创造新计划）。分类任务对当前LLM而言比生成任务更可靠——这一认知对agent团队设计有直接影响：应将品味判断委托给critic角色，而非期望producer agent内嵌完整的品味能力。

Critic Agent的局限性同样值得正视。其有效性取决于prompt中固化标准的质量——本质上仍是prompt engineering的包装。如果品味标准本身难以形式化，critic只能捕捉到显式规则而无法覆盖隐性判断。此外，critic agent本身也可能drift——当critic的标准长期不更新时，其审查质量会逐渐退化[^325^]。

尽管存在这些限制，critic agent的ROI（投入产出比）在五大方案中表现最优：实现复杂度适中（现代agent框架LangGraph、CrewAI已原生支持），维护成本可控（仅需更新critic的prompt和评价标准），而质量提升有稳定的实证支撑。对于个人开发者，建议将critic agent作为品味编译的基础设施层——每个spec/design产出后自动运行审查，审查结果同时作为few-shot案例积累。

#### 1.2.4 偏好学习/RLHF-style：T-POP>AMULET 14.7%，个人开发者难以运行

偏好学习/RLHF-style方案是学术研究最密集的方向，涵盖了从训练时偏好优化到测试时个性化的完整方法谱系。根据2025年最全面的个性化LLM综述，该方法家族包括VPL（变分偏好学习）、PReF（矩阵分解奖励模型）、PPT（上下文学习个性化）、Drift（免训练属性组合）、AMULET（测试时在线解码）和T-POP（在线偏好反馈）[^121^][^124^]。

在学术基准上，该方案家族展示了强劲的性能。T-POP在三个模型（Mistral-7B、Llama-3.1-8B、Qwen2-7B）上平均比AMULET提升14.7%，在Qwen2-7B上提升28.0%，win rate平均94.2%[^128^][^242^]。PROSE（Apple Research）通过迭代精化和跨样本一致性验证推断用户偏好，比CIPHER提升33%；结合ICL可进一步提升9%[^246^]。PReF证明仅需约10-20对偏好比较即可实现有效个性化[^1142^]。

然而，将这些方法应用于个人开发者的软件设计流水线面临三个结构性障碍。

第一，训练基础设施门槛。VPL、PReF等训练时方法需要RL/DPO基础设施，包括奖励模型训练、偏好数据管理和模型微调pipeline——这些对个人开发者而言是重大的工程负担[^1137^][^1142^]。

第二，偏好数据的获取困境。所有偏好学习方法都需要pairwise preference数据（"方案A比方案B更好"的成对比较）。在对话或写作场景中，这种数据可通过自然交互收集；但在软件设计场景中，开发者很少以pairwise形式表达设计偏好，偏好信号通常隐含在代码审查评论、设计文档修订和口头讨论中[^324^]。

第三，领域验证缺失。DPO-f+在代码修复反馈对齐任务上证明了方法的部分可迁移性——Pass@1比baseline提升5.71pp，在SWE-bench Lite上resolution rate比DPO提升1.67pp[^324^]。但"代码修复偏好"与"架构设计品味"之间存在显著差异：前者有明确的正确性标准（修复是否解决了bug），后者涉及多维度的主观权衡（简洁vs完整、类型安全vs灵活性等）。截至2025年，尚无已发表的个性化方法在"软件架构品味"基准上完成验证[^121^]。

对个人开发者而言，测试时方法（AMULET、T-POP）比训练时方法更具可行性——它们无需重训练模型，通过调整解码过程实现个性化[^1141^][^242^]。但即便如此，这些方法需要持续收集在线偏好反馈，在软件设计场景中的反馈频率远低于对话场景，可能导致学习收敛缓慢（T-POP需要20-60轮交互才能达到良好效果[^242^]）。

#### 1.2.5 Memory系统：LangMem的procedural memory是唯一"习得"品味的方案

Memory系统方案通过让agent积累和检索长期经验来实现品味的渐进式内化。根据LangMem SDK的分类，agent memory分为semantic（事实/知识）、episodic（过往经验）和procedural（学习行为/prompt规则）三类[^177^][^538^]。

在该方案家族中，Mem0、Zep和LangMem是三个代表性系统。Mem0 benchmarks显示比full-context prompting降低91%的p95延迟和90%的token使用[^127^]；Zep使用Temporal Knowledge Graph动态综合非结构化对话和结构化业务数据[^325^]。然而，真正与"品味习得"直接相关的是LangMem的procedural memory能力——它是唯一支持agent重写自身system prompt的memory系统[^540^]。

Procedural memory的独特性在于它让agent不仅能"记住"发生了什么，还能"学习"如何改进自己的行为规则。当agent在与人类的交互中反复收到"在这个项目中，优先使用函数式编程风格"的反馈时，LangMem可以将这一偏好转化为system prompt的规则更新，使得后续所有推理都自动遵循这一偏好。这是从"回忆事实"到"习得品味"的关键跃迁[^540^]。

Letta（原MemGPT）的Core Memory提供了相近的能力。Core Memory是一个"always-present, editable in-context memory block"，agent通过tool call自行修改——"memory reflects what the agent has learned, not just what a developer pre-loaded"[^536^]。Letta Code将这种能力扩展到编码场景，支持system prompt learning和skill learning两种持续学习模式[^327^]。

然而，procedural memory引入了新的风险：procedural drift。无管制的自我修改可能导致次优工作流的渐进式强化——agent可能在某次交互中学到了局部有效的规则，随后在没有人类验证的情况下不断强化这一规则，最终导致系统性偏离[^325^]。此外，context rot（长会话中因上下文窗口填满导致的早期指令稀释）是所有长会话agent的结构性问题[^334^]，memory系统虽能缓解但无法根除。

综合评估，memory系统是五大方案中唯一提供"品味习得"能力的方案——constitution和few-shot只能"注入"静态品味，critic只能"检查"是否匹配，偏好学习需要大量数据才能启动，而procedural memory可以在日常交互中持续更新品味表达。但这一能力需要governance机制（如人类审核所有procedural memory的变更）来对冲drift风险[^325^]。

### 1.3 横向对比与推荐

#### 1.3.1 对比表：有效性证据/维护成本/实现复杂度/抗drift/个人开发者可行性

表2从六个维度对五大方案进行量化对比，为技术决策提供结构化依据。

| 方案 | 有效性证据 | 维护成本 | 实现复杂度 | 抗drift | 个人开发者可行性 | 隐性品味覆盖 |
|------|-----------|---------|-----------|---------|----------------|------------|
| Constitution文件 | 中（社区广泛采用，但面临curse of instructions）[^103^] | 低-中 | 低 | 弱（无harness时）[^137^] | **高** | 低 |
| Few-shot案例库 | 中-高（FSPO: 87%/72%胜率）[^129^] | 中 | 低-中 | 中 | **高** | 中 |
| Critic Agent | 高（消融实验一致+5-15%）[^158^][^157^][^154^] | 中 | 中 | 中[^325^] | **中** | 低-中 |
| 偏好学习/RLHF | 高（学术benchmark）[^128^][^242^] | 高（训练）/低（测试时） | 高 | 高（在线方法） | **低-中** | 中 |
| Memory系统 | 中-高（91%延迟降低）[^127^] | 中 | 中-高 | 中（有procedural drift风险）[^325^] | **中** | 高（procedural memory） |

表2：五大品味编译方案六维对比。"隐性品味覆盖"衡量方案捕获"我说不清为什么，但知道这样更好"类判断的能力。个人开发者可行性综合了基础设施成本、学习曲线和运维负担。

表2的数据揭示了几个关键权衡。第一，不存在单一最优方案：constitution在可行性上最优但覆盖范围最窄；偏好学习在学术基准上最强但对个人开发者门槛最高；memory系统是唯一覆盖隐性品味的方案但引入了drift风险。第二，Critic Agent在"有效性证据/实现复杂度"比值上表现最佳——多项独立消融实验支撑其效果，而实现成本适中。第三，隐性品味覆盖与抗drift之间存在张力：procedural memory的自主学习能力同时是其优势和风险来源。

表2的评估应结合一个定性判断：所有方案在"软件设计品味"这一特定domain上的验证都不充分。当前研究集中在对话风格、写作偏好和视觉审美等场景[^121^][^124^]，"architecture taste"的个性化benchmark仍处于空白状态。这意味着表2中的"有效性证据"维度可能高估了各方案在目标场景中的实际表现。

#### 1.3.2 推荐策略：阶段1 Constitution+Critic+案例库 → 阶段2 Core Memory → 阶段3 T-POP/AMULET

基于上述分析，本报告推荐一条渐进式的品味编译路径，分为三个阶段实施。

**阶段1（立即实施）：Constitution + Critic Agent + 渐进式Few-shot案例库**

阶段1的目标是以最低基础设施成本建立品味注入的基础层。具体实施包括：

- **Constitution文件**：创建`constitution.md`，控制在20条原则以内，优先覆盖"不可违反的硬约束"（如安全规范、编码标准）。经验法则是：如果一条原则可以被自动化测试验证，它更适合放在harness中而非constitution中[^137^]。

- **Critic Agent**：在每个spec/design产出后运行独立审查。Critic的prompt应固化显式的评价标准（如"检查spec是否包含所有functional requirement"、"验证design是否与constitution一致"）。利用LangGraph、CrewAI等框架的原生multi-agent支持，实现复杂度可控。

- **Few-shot案例库**：从5-10个个人最满意/最不满意的历史决策开始，建立初始案例集。每次critic审查的结果（approve/reject + 理由）自动追加为案例[^129^]。

阶段1的预期效果是：将agent产出的"明显偏离"率从基线降低50%以上（基于critic agent消融实验的保守估计），同时建立持续收集品味信号的数据pipeline。

**阶段2（有基础设施后）：Core Memory + 在线偏好信号收集**

阶段1运行稳定后（预计1-2个月），引入memory层实现品味的渐进式积累。

- **Core Memory（Letta风格）**：集成Letta或LangMem的procedural memory能力，让agent能够记住高频偏好和约束[^536^][^327^]。例如，当开发者连续3次纠正agent"不要使用class继承，用composition"时，这一偏好应被自动写入core memory并在后续推理中自动应用。

- **Session管理**：定期`/compact`或session reset防止context rot[^334^]。建议每次session结束时将关键决策和偏好更新持久化到memory中。

- **偏好信号收集**：每次agent产出后收集approve/reject信号，作为后续阶段偏好学习的训练数据。

阶段2的核心价值在于将品味从"静态注入"转为"动态习得"。但需建立governance机制：所有procedural memory的变更应记录audit log，关键变更需人类确认[^325^]。

**阶段3（规模化）：T-POP/AMULET风格的在线偏好学习 + Continuous Evaluation**

当偏好信号积累到50-100对时（预计3-6个月），可启动在线偏好学习。

- **测试时个性化**：集成AMULET或T-POP等测试时方法，通过在线成对偏好反馈持续调整解码策略[^1141^][^242^]。这些方法无需重训练模型，对个人开发者更友好。

- **Continuous Evaluation pipeline**：参考ArbiterOS的EDLC模式，建立"Golden Dataset"持续验证品味一致性。当检测到关键回归时自动阻止pipeline继续执行[^332^]。

- **Procedural memory governance**：随着procedural memory的积累，建立定期review机制（如每月审查一次memory变更日志），防止procedural drift的累积[^325^]。

图1展示了这条渐进路径的技术栈演化。横轴为时间（月），纵轴为品味内化深度——从"外部规则约束"（低内化）到"自主适应"（高内化）。三个阶段的交界点并非刚性边界，而是基于数据积累速度的弹性过渡。

```
品味内化深度
    ^
    |                    ┌─────────────────────────────────────┐
    |                    │   阶段3: 在线偏好学习 + 持续评估    │
高  │                    │   (T-POP/AMULET + EDLC pipeline)    │
    │         ┌──────────┴─────────────────────────────────────┤
    │         │   阶段2: Core Memory + 偏好信号收集            │
中  │         │   (Procedural Memory + Audit Governance)       │
    │  ┌──────┴───────────────────────────────────────────────┤
    │  │   阶段1: Constitution + Critic + Few-shot案例库      │
低  │  │   (静态规则注入 + 运行时审查 + 案例驱动)              │
    └──┴───────────────────────────────────────────────────────┴──> 时间(月)
       0        1-2              3-4              6+
```

图1：渐进式品味内化路径。阶段1建立静态约束和审查基础设施；阶段2引入动态记忆和偏好收集；阶段3实现数据驱动的持续个性化。每个阶段的进入条件取决于前一阶段积累的偏好数据量，而非刚性时间表。

这条渐进路径的设计遵循三个核心原则。第一，不要在阶段1等待"完美品味编译"——从constitution和几个few-shot案例即可启动，每轮human review都是收集偏好数据的机会[^332^]。第二，设定合理的escalation rate目标（如20%），而不是追求0%——在品味判断上，适度的human involvement是质量保障而非失败[^288^]。第三，利用个人开发者场景的结构性优势：品味来源单一（不需要多人协调）、反馈闭环短（一个人做所有review）、迭代速度快——这使得10-20对偏好即可启动有效个性化[^1142^]，远低于企业级场景的需求。

从长期视角看，"编译品味"的终极目标是让agent pipeline在面对模糊brief时，做出与人类决策者一致的判断选择。当前技术条件下，这一目标只能部分实现——constitution和critic可以覆盖显式规则，memory和偏好学习可以覆盖统计模式，但"对模糊地带的无言判断"仍是人类的领地。接受这一限制不是妥协，而是务实的工程设计：编译能编译的，escalate不能编译的，在每一次escalation中积累更多品味数据，驱动下一轮的自动化深化[^332^]。
