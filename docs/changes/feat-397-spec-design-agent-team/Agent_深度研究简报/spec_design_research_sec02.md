## 2. P0核心问题深度综述（二）：Escalation——何时该问人

当agent pipeline在spec对齐或design对齐环节遇到不确定性时，一个核心决策浮现：是自主推进还是升级给人类？Escalation（升级）机制的设计质量直接决定了两个关键指标——自动化率（影响效率）和错误率（影响质量）。一个过度保守的系统（over-asking）将人类拖入大量本可自主处理的决策，消磨pipeline的价值；一个过度自信的系统（overstepping）则在agent不应擅自做主的场景中盲目推进，积累结构性风险[^288^][^302^]。本章系统梳理escalation技术的五条路线，提炼confidence-gated escalation的最佳实践，并覆盖价值判断场景的特殊挑战与生产级handoff设计。

### 2.1 技术路线谱系

#### 2.1.1 Logit-based/Verbalized/Sampling-based/Conformal Prediction/Meta-model五条路线

当前LLM不确定性估计研究可划分为五条技术路线，每条路线依赖不同的信号源、具有不同的假设前提和适用场景。表3提供了结构化对比。

| 路线 | 代表方法 | 核心信号 | 是否需要校准数据 | 统计保证 | 关键局限 |
|------|---------|---------|-----------------|---------|---------|
| Logit-based | Token probability, Entropy, MSP | 模型内部概率分布 | 否（温度缩放需要） | 无 | 需要logit访问；discrimination较弱[^324^] |
| Verbalized | Confidence elicitation, ADVICE | 模型自我报告的置信度 | 否 | 无 | 系统性overconfidence；ECE可达0.377+[^250^][^329^] |
| Sampling-based | Self-consistency, SC by embedding | 多次采样的一致性 | 否 | 无 | 计算开销高（多次前向传播）[^324^] |
| Conformal prediction | KnowNo, ConU, Conformal Social Choice | 非符合分数排序 | 是（校准集） | 有（覆盖率 $\geq 1-\alpha$）[^260^][^310^] |
| Meta-model | LPP, Tracer | 多源特征融合的预测器 | 是（训练集） | 无（但可校准）[^255^][^305^] |

表3：LLM不确定性估计五条技术路线对比。MSP = Maximum Softmax Probability；SC = Sample Consistency；LPP = LLM Performance Predictors。统计保证指是否提供覆盖率等可证明的可靠性边界。

表3的核心洞察在于：**没有单一信号足以支撑生产级escalation决策**。Logit-based方法虽然获取成本低（单次前向传播即可提取token probability），但其区分正确与错误回答的能力（discrimination）不如sampling-based方法。斯坦福医学信息学研究在MedQA、NEJM等医学问答数据集上的系统评估显示，Sample Consistency（SC）by sentence embedding在区分正确/错误LLM回答上表现最优（ROC AUC 0.68-0.79），SC by GPT annotation次之（ROC AUC 0.66-0.74），而token-level probability和verbalized confidence的discrimination均弱于SC方法[^324^]。

这一发现对agent pipeline设计有直接影响：当模型访问权限允许时（white-box或gray-box场景），应优先融合SC和logit信号；当仅能通过API访问模型输出时（black-box场景），则需依赖verbalized confidence或外部meta-model——但这会显著牺牲可靠性。

Meta-model路线提供了融合多种信号的路径。LPP（LLM Performance Predictors）框架通过gray-box特征（token概率、熵）与black-box特征（verbalized confidence、uncertainty attribution indicators）的融合，训练轻量级分类器（如Ridge Regression）预测LLM回答的正确性，充当"gating agent"协调自主agent与人类审查者之间的决策[^255^]。Tracer系统则将这一思路扩展到生产环境，通过在历史日志上训练surrogate model，实现83-100%的自动路由覆盖率[^305^]。

#### 2.1.2 Verbalized confidence的系统性overconfidence问题（ECE可达0.377+）

在所有不确定性信号中，verbalized confidence（直接询问模型"你有多确定"）因其black-box兼容性而被广泛采用，但它是可靠性最低的选项。多项独立研究确认了该方法的系统性缺陷。

ADVICE框架揭示了overconfidence的根本机制：answer generation与confidence verbalization在LLM内部是解耦的——模型在报告置信度时没有充分依赖自己生成的答案[^250^]。换言之，模型生成答案的电路与报告置信度的电路之间存在结构性分离，导致后者无法准确反映前者的真实不确定性。这一发现的 mechanistic 验证来自电路追踪研究：verbalized overconfidence由中间到后层的少量MLP块和attention heads驱动，这些组件在final token位置写入confidence-inflation信号[^251^]。

RLHF训练进一步恶化了这一问题。对比分析显示，监督微调（SFT）模型的Expected Calibration Error（ECE）约为0.034，而经过RLHF训练的模型ECE恶化到0.135——约4倍的calibration退化[^329^]。这一发现具有讽刺意味：让模型"更好对话"的训练过程同时让它"更不诚实于自己的无知"。在生产环境中，这意味着使用RLHF训练模型的agent pipeline必须对verbalized confidence持高度怀疑态度，不应将其作为escalation决策的唯一依据。

Calibration与discrimination的独立性增加了复杂性。医学诊断领域的研究表明，不确定性代理可以展现强discrimination但弱calibration——能成功区分正确和错误回答，但预测的确信数值与实际准确率不匹配[^324^]。对于escalation决策，discrimination（能否"抓对"错误）往往比calibration（数值精确匹配）更关键，但两者都需要被监控。

持续fine-tuning引入了额外的维护负担。在lifelong learning场景中，conformal coverage（覆盖率保证）的退化可以远快于accuracy的退化——模型在"变得广泛错误"之前先"变得自信地错误"。极端案例中，Llama-3 8B在5个持续学习任务上的coverage从0.92降至0.61，而accuracy仅偏离baseline 3个百分点[^312^]。这要求每次fine-tuning后重新校准escalation阈值，否则系统将在不知不觉中丧失其统计保证。

### 2.2 最佳实践：Confidence-Gated Escalation

#### 2.2.1 KnowNo+Conformal Prediction：统计保证的escalation框架

KnowNo框架开创了将conformal prediction（共形预测）应用于LLM escalation的先河。其核心设计将规划任务转化为multiple-choice问题，使用conformal prediction校准LLM规划者的预测集：当预测集缩小到单个选项时自主执行，否则向人类求助[^260^]。在真实UR5机器人上的实验表明，KnowNo实现了最高的success-to-clarification比率——在相同成功率下向人类求助的次数最少。

Conformal prediction的理论吸引力在于它提供**可证明的统计保证**：给定一个用户指定的错误率上限 $\alpha$（如5%），系统保证预测集包含正确答案的概率不低于 $1-\alpha$。这一保证不依赖于LLM的底层架构或训练数据分布假设，仅需一个交换性（exchangeable）的校准集即可成立。

KnowNo的后续扩展解决了原始框架的多个限制。LofreeCP将方法扩展为兼容logit-free模型（纯black-box API场景）[^292^]。Introspective Planning通过引入知识库搜索增强了模型对真正ambiguous场景的区分能力，在保持相同统计保证的同时显著降低了over-asking率——因为KnowNo在unambiguous场景中也过于保守地求助人类[^257^]。ConU在7个LLM和4个free-form NLG数据集上实现了严格的correctness coverage rate控制，预测集平均大小仅1.03（TriviaQA上LLaMa-3-70B），意味着大多数预测集退化为单点决策，仅在真正不确定时膨胀[^319^]。

对于spec/design对齐场景，conformal prediction的应用路径如下：将design决策（如"选择方案A还是方案B"）形式化为multiple-choice问题，在校准集上估计非符合分数（non-conformity score），运行时根据阈值决定是自主执行还是escalate。校准集的收集可以通过历史human-approved决策自动完成，维护成本可控。

然而，conformal prediction的coverage guarantee是marginal（总体水平）而非conditional（条件水平）的——对于特定subgroup或特定类型的决策，实际覆盖率可能远低于 $1-\alpha$[^310^]。这意味着在设计safety-critical的escalation逻辑时，不能将conformal guarantee视为绝对安全边界。

#### 2.2.2 LLM Performance Predictors：gray-box+black-box特征融合

当conformal prediction的严格假设（交换性校准集、multiple-choice形式）难以满足时，LPP框架提供了更灵活的替代方案。LPP的核心创新在于融合多源不确定性信号为meta-model特征集，训练轻量级预测器估计LLM回答正确的概率[^255^]。

特征集包括两个层次。Gray-box特征需要token-level log-probabilities访问权限：softmax probability分布的统计量（均值、方差、熵）、序列级aggregated confidence、以及structured outputs的格式一致性指标。Black-box特征仅需要模型输出文本：verbalized confidence数值、uncertainty attribution indicators（如模型是否自发表达不确定性）、以及response style markers（长回答是否掩盖低confidence）。

LPP meta-model（如Ridge Regression或轻量级神经网络）在标注数据上训练后，可以作为gating agent动态路由决策：当预测P(correct)高于阈值时自主执行，低于阈值时escalate to human。这种方法的优势在于不依赖multiple-choice形式化，适用于open-ended的design review场景。

I-CALM框架从成本效益角度量化了escalation的经济学。研究表明，允许4.1%的abstention rate增加可带来13%的成本降低和5%的错误率降低[^274^][^275^]。这一反直觉的发现说明，escalation不仅是安全措施，也是效率优化手段——通过在不确定性高的决策点上主动请求人类介入，系统避免了错误的累积和后续修复成本。

生产级部署的关键实践在于阈值的校准方式。行业分析明确指出："任何凭直觉设定confidence threshold的系统都会miscalibrated。正确方法是在domain-specific标注数据上评估每个confidence level的正确率，基于可接受的错误率设定阈值"[^273^]。对于个人开发者的spec/design pipeline，这一校准可以通过历史human review数据自动完成——每次human approve/reject都是更新阈值估计的数据点。

#### 2.2.3 Conformal Social Choice：multi-agent场景中拦截81.9%的wrong-consensus

在multi-agent debate场景中，escalation面临一个独特的挑战：social reinforcement导致的wrong-consensus。当多个agent通过debate converge到一致但错误的结论时，传统的individual-level uncertainty detection失效——每个agent都"自信"，但集体是错误的。

Conformal Social Choice框架针对这一问题提供了统计保证的解决方案。它将multi-agent debate的输出转化为有marginal coverage guarantee的prediction sets，在 $\alpha=0.05$ 时拦截81.9%的wrong-consensus案例[^310^]。拦截机制的工作原理如下：当debate的共识答案被conformal set标记为"不确定"（set size > 1）时，系统自动escalate to human；当conformal set退化为单点（size = 1）时，自主执行。由于这一选择性拦截，remaining singletons的accuracy提升高达22.1个百分点（从约68%提升到90.0-96.8%）[^310^]。

这一结果对multi-agent spec/design pipeline有重要设计启示。在第4章将详细讨论的协作拓扑中，multi-agent debate被用于提高design quality——但如果debate的consensus被盲目信任，pipeline可能在debate参与者集体偏离时产生系统性错误。Conformal Social Choice提供了"debate后的安全网"：不依赖consensus本身，而是依赖conformal set的大小判断是否足够确定。

该方法的关键限制在于校准集必须是exchangeable的——如果debate参与者的组成或domain分布发生变化，calibration可能失效。此外，81.9%的拦截率虽高但非100%，意味着仍有约18%的wrong-consensus案例可能逃逸。在safety-critical场景中，应将此作为多层防御的一层而非唯一防线。

### 2.3 价值岔路识别与Ask-vs-Act

#### 2.3.1 Value Forks——AI与人类在价值判断上的系统性分歧

上述所有技术路线处理的是epistemic uncertainty（认知不确定性）——模型"不知道正确答案"。然而，在spec/design对齐中，一个同等重要但技术成熟度更低的挑战是value uncertainty（价值不确定性）：AI与人类在涉及偏好、权衡和伦理的决策中可能做出不同的选择，且这种差异是合理的。

FAccT 2025的研究首次系统量化了这一现象，提出"AI value forks"概念：在道德困境中，人们期望AI比人类更偏离utility-maximizing course——公平性在AI决策中比在人类决策中更重要[^282^]。该研究基于N=1029参与者的实验，覆盖医疗和军事道德困境。核心发现是：aligning AI with human values may require that an AI act differently from what a human agent should do[^282^]。这一结论对escalation设计有深远影响：当检测到value fork（价值岔路）时，系统不应尝试"推断人类会怎么做"然后自主执行，而应认识到AI的决策逻辑与人类期望在本质上的分歧，将决策权无条件交还给人类。

价值判断与事实判断的区分本身是一个open problem。当前的uncertainty quantification方法无法自动识别"这是价值判断而非事实判断"。Moral alignment框架提出的"Metaethical Awareness"标准为agent提供了部分指导：信号不确定性、承认合法道德冲突、避免过度自信的规约性[^276^]。但在软件设计场景中，价值岔路通常表现为更微妙的权衡——如"简洁性vs完整性"、"类型安全vs灵活性"——而非显式的道德困境。

Progressive autonomy框架提供了一种学习路径：何时允许agent自主决策不是手工调节的阈值，而是需要从人类supervisor的approve/deny反馈中学习的latent function。GP-probit policy gateway可以跟踪drifting supervisor的risk tolerance，并通过structured kernel将证据generalize到未查询的action-context组合[^330^]。但该方法在高stakes、低频率决策场景中的样本效率有限——如果agent每月只遇到一次涉及架构范式选择的决策，学习human risk tolerance可能需要极长时间。

对spec/design pipeline的实践启示是：应将escalation分为两个逻辑通道。事实通道处理技术判断（如"这个API设计是否满足所有functional requirements"），使用confidence-gated escalation；价值通道处理偏好权衡（如"简洁性和完整性哪个更重要"），使用rule-assisted detection（关键词匹配+模式识别）触发无条件escalate。

#### 2.3.2 Learning-to-defer的Bayes-optimal规则

Learning-to-defer框架为escalation决策提供了原则性的数学基础。Two-stage learning to defer设置适用于已有predictor（如LLM）的场景，不需要重新训练predictor，仅需学习一个deferral function决定何时将决策交给人类专家[^304^]。

Bayes-optimal deferral规则在直觉上十分清晰：当人类专家的正确概率超过模型任何类别的最大后验概率时，应当升级。形式化表达为：

$$\text{defer} \iff \max_{y} P(Y=y|x) < P(\text{human correct}|x)$$

这一规则的经济学解释是：escalation决策本质上是cost-benefit分析——比较错误成本（error cost）与升级成本（labor cost）。当人类专家在高不确定性决策上的期望收益超过自主执行的期望收益时，升级是最优选择。

在expert imbalance场景中（某些专家比其他人更常被选中），标准deferral算法会偏向majority expert。MILD（Optimized Deferral for Imbalanced Settings）通过cost-sensitive learning解决了这一问题[^291^]。对于个人开发者的单stakeholder场景，expert imbalance不显著，但cost-sensitive的逻辑仍然适用：不同设计决策的错误成本差异巨大——一个数据库schema选择的错误可能比一个函数命名的错误成本高10-100倍。

Value of Information（VOI）理论将escalation决策扩展到多步骤场景。Agentic AI orchestrator应当将routing、stopping、escalation、budget allocation表达为posterior expected-utility或value-of-information决策[^265^]。在实践中，这些决策不需要使用精确的VOI计算——one-step approximation或learned surrogates在保持低延迟的同时提供了足够好的近似[^315^]。

### 2.4 生产级Handoff设计

#### 2.4.1 Inline/Async/Blended三种模式

Escalation的最终环节是将决策从agent handoff给人类。生产级系统通常采用三种模式的组合，每种模式适用于不同的场景特征[^271^]。

**Inline escalation**（实时升级）适用于time-sensitive的实时渠道。当agent在spec生成过程中检测到高不确定性时，立即中断pipeline并向人类呈现当前上下文、候选选项和不确定性理由，等待人类输入后继续执行。该模式的优势是latency最低，劣势是打断人类当前工作流，可能导致context switching成本。

**Asynchronous escalation**（异步工单）适用于非实时场景。当不确定性被检测到时，系统生成一个包含完整上下文的工单（goal + proposed decision + risk score + uncertainty metric + reasoning trace）并放入队列，人类在方便时批量处理[^271^]。该模式的优势是不打断人类工作流，劣势是增加整体pipeline latency。对于个人开发者的overnight batch pipeline，这是推荐的主要模式。

**Blended assistance**（混合辅助）是最高级的模式——AI实时辅助人类agent处理复杂决策，而非完全移交控制权。研究表明该模式可将agent productivity提升30-50%[^271^]。在spec/design场景中，该模式表现为：当人类审查一个design decision时，AI提供多维度分析（技术可行性、与constitution一致性、与历史案例的相似性），但最终判断权在人类手中。

图2展示了一个multi-agent spec pipeline中的escalation决策流程。该流程整合了前述所有技术组件：多源不确定性信号采集、conformal prediction决策、value fork检测、以及分层handoff路由。

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Escalation决策流程                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐            │
│  │ Logit-based  │   │ Sampling SC  │   │ Meta-model   │            │
│  │ (entropy,    │   │ (self-       │   │ (LPP fusion) │            │
│  │  MSP)        │   │ consistency) │   │              │            │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘            │
│         └─────────────────┬─────────────────┘                        │
│                           ▼                                          │
│              ┌────────────────────────┐                              │
│              │ 多信号融合 & 阈值判断    │                              │
│              │ (Conformal Prediction) │                              │
│              └───────────┬────────────┘                              │
│                          ▼                                           │
│              ┌───────────────────────┐                               │
│              │ 决策类型分类           │                               │
│              ├───────────────────────┤                               │
│              │ • 事实判断? → CP gating│                               │
│              │ • 价值判断? → Value fork│                               │
│              │   detection → 强制escalate                              │
│              └───────────┬───────────┘                               │
│                          ▼                                           │
│         ┌────────────────┼────────────────┐                         │
│         ▼                ▼                ▼                         │
│   ┌──────────┐    ┌──────────┐    ┌──────────────┐                 │
│   │ 自主执行  │    │ Inline   │    │ Async Ticket │                 │
│   │ (CP set=1)│    │ Escalate │    │ (context     │                 │
│   │          │    │ (realtime)│   │  bundle)     │                 │
│   └──────────┘    └──────────┘    └──────────────┘                 │
│                                                                      │
│  Multi-agent场景: Conformal Social Choice 拦截wrong-consensus       │
│  └─ 若consensus但CP set > 1 → 强制escalate                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

图2：Multi-agent spec pipeline中的escalation决策流程。上游采集多源不确定性信号，经conformal prediction融合后进行决策类型分类——事实判断使用confidence-gated routing，价值判断触发无条件escalation。Multi-agent场景中额外插入Conformal Social Choice拦截wrong-consensus。

图2的流程设计遵循三个原则。第一，所有escalation决策必须有audit trail——记录触发信号、阈值比较结果和选择的handoff模式，用于后续分析和模型改进。第二，value fork检测优先于confidence gating——即使模型在高confidence下做出价值判断，也应escalate。第三，multi-agent场景中consensus本身不是充分条件——Conformal Social Choice提供了额外的安全层。

Layered guardrails架构为escalation提供了系统级支撑。生产级AI agent需要多层防护：input validation（验证输入的合规性）、reasoning auditing（审计推理过程的可追溯性）、output guardrails（验证输出的安全性）和topology-based enforcement（在agent graph的conditional edges中编码escalation policy checks）[^296^][^306^]。在graph-based agent系统中，escalation和privileged tool execution应遵循deny-by-default原则——如果caller没有预定义的route到human approval node，execution cannot occur[^306^]。

#### 2.4.2 Escalation rate作为product health metric（目标<20%）

Escalation rate（升级率）——agent pipeline向人类求助的决策占总决策的比例——是衡量系统健康的核心指标，但其解读需要 nuanced 分析。

行业最佳实践明确指出："有效的escalation是designed first, not added last。应将escalation rate作为product health metric而非cost line来监控"[^288^]。这一视角转变至关重要：escalation不是系统失败的标志，而是系统对自身不确定性诚实表达的标志。一个0% escalation rate的系统不是完美的——它是危险的过度自信。

从实证角度看，合理的escalation rate目标应低于20%。高于20%表明系统过度保守（over-asking），人类负担过重，pipeline的自动化价值被削弱；低于5%则表明系统可能过度自信（overstepping），存在大量未被拦截的错误风险。理想的escalation rate落在10-20%区间，表明系统在大多数决策上自主执行，但在真正不确定时诚实求助。

监控escalation rate的drift同样重要。如果escalation rate在短期内显著上升（如从15%跳升至30%），可能表明：输入分布发生了shift（新类型的design决策agent未见过）、模型calibration退化[^312^]、或constitution/critic层需要更新。如果escalation rate持续下降，则可能表明agent在学习中变得更自信——但也可能变得更盲目自信。

I-CALM框架的实证数据为escalation rate的经济学提供了量化支撑：4.1%的abstention rate增加带来13%的成本降低和5%的错误率降低[^274^][^275^]。这一counter-intuitive的结果说明，escalation不仅是"安全投入"，也是"效率投资"——通过在不确定性高的决策点上早期介入，避免了错误级联和后续修复的更高成本。

对于个人开发者的spec/design pipeline，建议实施以下escalation指标dashboard：

- **Escalation rate**：目标10-20%，按decision type（事实/价值）分别追踪
- **Escalation accuracy**：escalate的决策中人类确实不同意agent建议的比例，反映escalation的precision
- **Missed escalation**：人类事后发现agent应escalate但未escalate的案例数，反映escalation的recall
- **Human resolution time**：人类处理escalation请求的平均时间，反映handoff效率
- **Escalation rate trend**：周/月级别的escalation rate变化趋势，用于检测drift

该dashboard的数据应自动从pipeline日志中提取，每次human review都是更新指标的数据点。设定合理的escalation rate目标，并持续优化escalation的precision和recall，是将escalation从"应急机制"提升为"产品健康基础设施"的关键步骤。
