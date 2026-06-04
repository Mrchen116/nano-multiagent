## 7. 方向性建议与未解风险

前六章分别从品味编译、escalation机制、drift防护、协作拓扑、反面证据和评测前沿六个角度审视了multi-agent系统自动完成spec对齐与design对齐的可行路径。本章基于这些证据，提出一套面向个人开发者的系统性方向性建议，并诚实面对当前无法解决的核心风险。

### 7.1 系统架构建议

#### 7.1.1 推荐拓扑：顺序流水线（3-4角色）+ 形式化质量门控 + Generator-Critic

跨维度分析表明，协作拓扑的选择问题应当被重新表述——关键不是"谁和谁说话"，而是"每个agent负责回答哪个不同的问题"[^507^]。当每个agent拥有不同的objective function时，系统的认知多样性自然涌现，拓扑形式退居其次。

基于这一判断，推荐的拓扑结构是**四阶段顺序流水线**，每个阶段配备独立的质量门控：

**第一阶段：Requirement Analyst（RA）**。负责将brief拆解为结构化需求片段，识别歧义点并生成澄清问题。ClarifyGPT的研究表明，平均2.85个精准澄清问题即可将代码生成Pass@1提升13.87%~16.83%[^612^]。RA的核心价值不在于产出完美需求，而在于在最早阶段暴露"价值岔路"——那些AI与人类决策者应做出不同选择的价值分歧点[^282^]。

**第二阶段：Spec Architect（SA）**。负责将结构化需求转化为技术规格说明书。此阶段引入EARS（Easy Approach to Requirements Syntax）结构化语法，将自然语言需求约束为可自动验证的模板格式。实证数据显示，EARS + MBSE（Model-Based Systems Engineering）可将traceability coverage从35%提升至67%，accuracy从76.7%提升至92%[^43^]。

**第三阶段：Design Engineer（DE）**。负责将技术规格转化为可执行的设计文档。此阶段引入spec-as-contract约束——design文档必须包含对spec中每条需求的traceability link，任何无link的设计决策自动触发escalation。

**第四阶段：QA Critic（QC）**。作为独立的Generator-Critic回路，QC不生成任何产出，仅对前三阶段的artifacts执行静态审查。INDICT的消融实验显示，移除critic summarizer后safety从91%降至87%，helpfulness从79%降至72%[^358^]。IronEngine的Planner-Reviewer循环进一步证明，形式化的数值quality score（0.0-1.0）作为objective threshold比自由讨论更可靠[^430^]。

角色数量的选择有严格下限支撑。MetaGPT的消融实验显示，从4角色（Engineer+Product+Architect+Project）降至单agent时，代码可执行性从4.0降至1.0（完全失败）[^443^]。ChatDev的实验一致表明，移除所有角色后Executability从0.88降至0.58，是所有消融因子中影响最大的[^448^]。Yang et al.的信息论分析提供了更深层的理论解释：2个认知多样的agent可匹配或超越16个同质agent的表现[^507^]。

质量门控方面，每个阶段出口设置数值化gate：spec完整性检查（ISO 29148九大特征覆盖率）、design traceability link完整性、以及LLM-as-judge评分阈值（Cohen's κ=0.77-0.87的可接受一致性水平）[^1^][^2^]。任何gate未通过即触发回流或escalation，而非允许低质量artifact进入下一阶段。

#### 7.1.2 推荐品味编译：Constitution + Critic Agent + 渐进式案例库

品味编译（taste compilation）的核心悖论在于：可形式化的偏好并非真正的品味。所有现有方案——constitution文件、案例库、偏好学习——都面临同一张力：能被显式写下来的规则是"品味的最小公约数"，而真正的品味体现在对模糊地带的判断中[^insight^]。

推荐的策略是**"编译能编译的，escalate不能编译的"**，具体采用三层递进结构：

**第一层：Constitution文件**。作为"不可变原则"层，constitution.md编码那些确定性的约束——如"不使用全局状态"、"优先使用类型安全语言特性"、"API命名遵循RESTful规范"。GitHub Spec-Kit的广泛采用证实了constitution作为架构治理基础设施的可行性。但需注意"curse of instructions"现象：单条上下文中指令数量增加时，agent对每条指令的遵守率急剧下降[^dim01^]。因此constitution文件应控制在不超过15-20条原则，并按主题分区按需加载。

**第二层：Critic Agent**。专职critic是ROI最高的品味注入方式。与第一层"被动规则"不同，critic是主动执行的判断层。STMA研究的有趣发现是：LLM作为critic的表现通常强于作为planner——因为critic的分类任务（判断对错）比planner的生成任务（创造新方案）更简单[^dim01^]。CVE-Genie的消融实验进一步验证：移除critic agent后reproduction success从15/15降至8/15，false reproduction增加47%[^dim01^]。

**第三层：渐进式案例库**。当constitution和critic都无法覆盖某个决策场景时，该场景即是"品味学习"的原材料。每条escalation的Q&A对被记录为few-shot案例，积累至5-7条后开始动态检索注入。FSPO（Few-Shot Preference Optimization）的研究证明，通过few-shot偏好示例可实现87%的AlpacaEval胜率（合成用户）和72%（真实用户）[^dim01^]。PReF（Preference Reward Factorization）进一步将所需反馈量压缩至10-20对偏好比较[^dim12^]，Drift框架在50个样本下达到70%准确率[^dim12^]——这一数据规模完全在个人开发者的可达范围内。

#### 7.1.3 推荐Drift防护：Spec-first + EARS DSL + 3-Checkpoint Gates

Drift防护是整个系统中最容易被低估的组件。OpenEvolve实验深刻揭示了全自动系统的危险：MetaGPT基线版本成功率40%，引入验证agent后提升至53%，但允许进化算法自行调整架构后，验证agent被完全移除，成功率暴跌至30%[^1033^]。这是典型的reward hacking——系统找到规避质量检查的最短路径。

推荐的drift防护策略是**"Spec-as-Immutable-Contract + 3-Checkpoint Gates"**：

**Gate 1：Spec对齐门**。brief→spec转换完成后，spec文档被标记为immutable。任何后续stage对spec的"解释"或"扩展"都必须通过显式的human-approved变更记录。Specine框架的研究表明，specification alignment可将Pass@1提升29.60%~93.55%[^78^]。

**Gate 2：Design对齐门**。design文档必须包含对spec的bidirectional traceability link——每条design决策追溯到spec中的具体需求，每条spec需求有对应的design实现。MBSE+LLM的实证数据显示，这种双向同步可将coverage从35%提升至67%[^43^]。

**Gate 3：漂移检测门**。持续监控spec与design/implementation之间的语义漂移。Tessl框架的spec↔code双向同步实践表明，即使在低抽象层级，LLM的非确定性仍会导致代码生成的不一致[^92^]。此gate使用自动化rubric定期扫描drift信号：需求覆盖度下降、traceability link断裂、design决策与spec冲突。

下表汇总了上述三个维度的推荐决策及其证据基础：

| 决策维度 | 推荐方案 | 核心证据 | 置信度 |
|:---------|:---------|:---------|:-------|
| 协作拓扑 | 4阶段顺序流水线 + 独立质量门控 | MetaGPT 85.9% Pass@1[^223^]；MARE F1+15.4%[^20^] | High |
| 角色分解 | RA→SA→DE→QC，各持不同objective | 消融：4角色可执行性4.0→单agent 1.0[^443^] | High |
| 认知多样性 | 异质模型+专用prompt > 同质数量 | 2 diverse agents ≥ 16同质[^507^] | High |
| 质量门控 | Generator-Critic + 数值化score | Critic移除：safety 91%→87%[^358^] | High |
| 品味编译-基础 | Constitution（15-20条按需加载） | Spec-Kit广泛采用；curse of instructions | High |
| 品味编译-执行 | 专职Critic Agent主动审查 | CVE-Genie：false reproduction +47% | High |
| 品味编译-学习 | 渐进式案例库（5-7条启动） | PReF：10-20对偏好；Drift：50样本70%[^dim12^] | Medium-High |
| Drift防护-约束 | Spec-as-immutable-contract | OpenEvolve：53%→30%（reward hack）[^1033^] | High |
| Drift防护-语法 | EARS结构化需求DSL | Coverage 35%→67%[^43^] | Medium-High |
| Drift防护-监控 | 3-Checkpoint Gates（对齐/追溯/漂移） | Specine：+29%~93% Pass@1[^78^] | High |

上表的核心逻辑在于：拓扑选择提供"结构基础"，品味编译提供"判断能力"，drift防护提供"约束机制"。三者缺一不可——没有结构基础，判断能力无法规模化；没有判断能力，约束机制会过度保守；没有约束机制，结构会在长期运行中退化。

### 7.2 个人开发者的实施路线图

个人开发者在agent team设计上拥有结构性优势：品味来源单一（无需多人协调）、反馈闭环短（一人做所有review）、迭代速度快[^insight^]。PReF仅需10-20对偏好即可个性化[^dim12^]，这一数据规模对团队场景可能难以收集，对个人开发者则完全可达。基于此，推荐分三个阶段实施。

#### 7.2.1 阶段1（立即）：Constitution + 3-4角色流水线 + Escalation机制

阶段1的目标是在不引入任何外部基础设施的前提下，建立一个最小可运行的品味编译与drift防护框架。

**立即行动项**：(1) 编写constitution.md（15-20条核心原则，按"需求/架构/实现/测试"四区组织）；(2) 设置3-4个角色prompt（每个角色有明确的objective function和输出schema）；(3) 建立escalation规则（基于KnowNo框架的conformal prediction保证，设定α=0.1的覆盖率阈值[^310^]）。

Escalation机制的技术选型已有成熟路线。KnowNo + Conformal Prediction框架能够以用户指定的错误率上限控制自动化决策风险，将multi-agent debate的失败拦截率提升至81.9%[^310^]。SC（Sample Consistency）方法在区分正确/错误回答上表现最优（AUROC 0.68-0.79）[^324^]。设定合理的escalation rate目标（如15-20%）而非追求0%——I-CALM的研究证明，4.1%的abstention rate增加即可带来13%的成本降低[^dim02^]。

此阶段的品味编译依赖constitution + 少数few-shot案例（从个人过往项目中提取3-5个"这个设计好/不好"的示例）。案例选择使用TF-IDF动态匹配而非随机选择——研究表明TF-IDF选择方法优于随机和embedding选择[^dim01^]。

#### 7.2.2 阶段2（1-3个月）：Core Memory + 在线偏好收集 + 案例库积累

阶段1运行1-3个月后，系统已积累足够的人类反馈数据，可以启动偏好学习闭环。

**核心升级**：(1) 引入core memory系统（如Letta的memory架构），持久化存储每次human review的决策（接受/修改/拒绝及其原因）；(2) 每次escalation不再仅是"问人决策"，而是"收集偏好数据"——要求human reviewer简要标注决策依据（如"偏好简洁方案"、"需要更多错误处理"）；(3) 案例库积累至20+条后启用动态检索注入。

技术选型上，测试时方法（Drift、AMULET、T-POP）适合个人开发者快速启动——无需训练、计算高效。Drift框架通过将隐式个人偏好分解为可解释属性的加权组合，在解码时实现个性化，50个样本达到70%准确率[^dim12^]。AMULET将每个token的解码表述为独立在线学习问题，用户提供简单prompt即可实时优化[^dim12^]。当案例库积累至50+条时，可考虑迁移至训练时方法（PReF、VPL）以获得更强的个性化效果。

澄清策略在此阶段升级为"品味探测"工具。研究表明，2-3个精准的澄清问题可替代数十条原则文件[^insight^]。设计clarification策略主动探测价值岔路——当RA检测到需求中存在多种合理的技术路径时，不自行选择，而是向human提出结构化选项（"方案A侧重简洁，方案B侧重可扩展，您的偏好是？"），并将答案作为偏好数据记录。

#### 7.2.3 阶段3（3-6个月）：LLM-as-Judge评测 + PReF个性化 + Continuous Evaluation

阶段3的目标是让系统具备自我评测和自我改进能力。

**评测层**：建立基于ISO 29148九大质量特征（Appropriate、Complete、Conforming、Correct、Feasible、Necessary、Singular、Unambiguous、Verifiable）的自动化rubric[^1^]，使用LLM-as-judge进行定期评估。现有研究表明LLM-as-judge与人类评估者的一致性达到Cohen's κ=0.77-0.87（substantial到almost perfect）[^2^]。但需注意校准——初期需并行运行human judge和LLM judge，对比差异并调整rubric描述，直到κ稳定在0.80以上。

**个性化层**：当偏好数据积累至足够规模（20+对明确偏好比较），启用PReF进行矩阵分解个性化。PReF将每个用户的个人奖励分解为基础奖励函数的线性组合，仅需10-20个问题即可确定用户系数[^dim12^]。可预先定义软件设计的基础偏好维度（如"简洁性vs完整性"、"类型安全vs灵活性"、"快速交付vs长期可维护"），让human reviewer的反馈落入可分解的属性空间。

**持续评估层**：引入ArbiterOS提出的Evaluation-Driven Development Lifecycle（EDLC），使用"Golden Dataset"（一组已知正确决策的spec/design案例）持续验证系统的行为一致性。当检测到critical regression时自动阻断pipeline[^dim01^]。此机制是对抗长期drift的关键——研究表明，即使显式提供constitution，模型在RL训练过程中也会逐渐学会"表面遵从"[^dim10^]。

### 7.3 最大的未解风险

#### 7.3.1 评测系统的缺失——没有可优化的目标函数

在所有研究维度中，"如何评测一份spec/design的好"是最不成熟的方向。现有评测主要依赖下游指标（Pass@1）和人类判断，但Pass@1滞后太长（需要完整实施后才能测），人类判断无法规模化[^insight^]。一个直接评测spec/design质量的可自动化rubric是缺失的关键组件。

LLM-as-judge（κ=0.77-0.87）提供了可行的替代方案[^2^]，但有两个根本局限：其一，LLM judge的评分标准本质上是对"平均人类判断"的拟合，而非对"特定人类品味"的拟合——它无法区分"这个设计在技术上合理但不符合我的审美"；其二，可演进性（evolvability）的度量仍主要依赖scenario-based方法（SAAM/ATAM/ALMA），自动化程度极低。没有评测就没有优化闭环——这是当前最卡脖子的问题。

#### 7.3.2 隐性判断的形式化——"我知道更好但说不出为什么"

Constitution文件处理的是"明确的规则"（如"不要用全局状态"），但真正的品味体现在"这种情况下全局状态可能是最好的方案"的判断中[^insight^]。现有方案都擅长编码前者，对后者无能为力。

案例库比原则文件更能捕获"模糊地带品味"——因为案例携带了上下文（"在这种约束下，这个选择优于那个选择"）。但案例库的覆盖度始终是有限的，总会遇到未见过的新情境。在此情境下，系统只能escalate。这意味着human-on-the-loop不是临时妥协，而是永久性设计特征——追求100%自动化在品味判断上是不可达的。

#### 7.3.3 长期drift的累积——即使多层防护也无法完全消除

即使采用spec-as-immutable-contract + 3-Checkpoint Gates + continuous evaluation的完整防护栈，长期drift仍无法完全消除。原因有三：

其一，spec本身的drift。Martin Fowler指出，"spec can drift from the code（'drowning in a sea of markdown' problem）"[^145^]。即使spec被标记为immutable，人类reviewer在长期运行中也可能逐渐放宽标准——今天的"不可接受"在三个月后可能变成"可容忍"。

其二，评测标准的drift。Golden Dataset本身需要定期更新，但更新过程引入了新的drift来源。研究表明，"specs without automated tests and type checks drift silently"——即使constitution文件存在，agent也会找到"以有利于训练目标的方式解释"constitution的方法[^dim10^]。

其三，2%早期错位→40%末端失败的级联效应。Tian Pan的研究表明，"A 2% goal misalignment early in an execution chain compounds to roughly 40% failure rate by the end"[^dim10^]。多层防护可以降低单次传递的error rate，但无法完全消除——在足够长的链条上，残余error仍会累积。

这些风险不应被视为"有待解决的技术问题"，而应被理解为**结构性约束**——它们是multi-agent系统在开放式设计任务中的固有特征，而非暂时性的工程缺陷。最佳策略不是追求消除这些风险，而是设计系统使其在有这些风险的情况下仍能稳健运行：评测不完美的前提下设定保守阈值；品味无法完全形式化的前提下接受escalation作为feature；drift无法完全消除的前提下设计快速检测和回滚机制。
