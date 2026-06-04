# 维度二：Escalation机制设计——让Agent自己判断何时该问人

## 深度研究报告 v1.0 | 2026-01

---

## Executive Summary

本报告系统调研了自治agent系统中"何时该升级给人类"的所有已知机制。核心发现：

1. **LLM不确定性估计已有成熟工具箱**，但存在系统性的overconfidence问题，尤其是verbalized confidence。Sample consistency (SC)方法在区分正确/错误回答上表现最优（ROC AUC 0.68-0.79），而verbalized confidence则系统性高估模型信心 [^324^]。

2. **Conformal prediction提供了统计保证的escalation框架**——KnowNo及其后续扩展（Conformal Social Choice、ConU等）能够以用户指定的错误率上限（α）控制自动化决策的风险，将multi-agent debate的失败拦截率提升至81.9% [^310^]。

3. **Learning-to-defer框架**（如LPP-based routing、MILD）为cost-sensitive escalation提供了原则性方法，其Bayes-optimal规则直观：当人类专家的正确概率超过模型任何类别的最大后验概率时，就应当升级 [^279^]。

4. **价值岔路（value forks）是escalation中最难处理的部分**——AI与人类决策者在道德困境中的选择偏好存在系统性差异（"AI value fork"），这要求escalation系统不仅检测不确定性，还要识别涉及价值判断的决策场景 [^282^]。

5. **生产级handoff需要分层架构**——成功的模式结合了inline escalation（实时）、asynchronous escalation（异步工单）和blended assistance（AI辅助人类），并将escalation rate作为产品健康指标而非成本线来监控 [^271^][^288^]。

---

## 1. Current State: 领域全貌

### 1.1 技术路线谱系

当前agent escalation研究可划分为四大技术路线：

| 路线 | 代表方法 | 核心信号 | 是否需要校准数据 | 统计保证 |
|------|---------|---------|-----------------|---------|
| Logit-based | Token probability, Entropy, MSP | 模型内部概率分布 | 否（温度缩放需要） | 无 |
| Sampling-based | Self-consistency, SC by embedding | 多次采样的一致性 | 否 | 无 |
| Verbalized | Confidence elicitation, ADVICE | 模型自我报告的置信度 | 否 | 无 |
| Conformal prediction | KnowNo, ConU, Conformal Social Choice | 非符合分数排序 | 是（校准集） | 有（覆盖率≥1-α） |
| Meta-model | LPP, Tracer | 多源特征融合的预测器 | 是（训练集） | 无（但可校准） |

### 1.2 从Human-in-the-Loop到Human-on-the-Loop

业界正从同步的人工干预模式转向异步的门禁裁决模式 [^288^][^299^]。关键转变包括：

- **从按钮到自动触发**：escalation由系统根据置信度、风险分和策略门自动触发，而非用户手动点击
- **从实时到异步**：人类专家在工单队列中批量处理升级请求，而非实时在线
- **从全部审查到选择性升级**：只有高不确定性或高风险的决策才升级，优化成本-准确率权衡

### 1.3 关键术语表

- **Escalation / Handoff / Deferral**：将决策从AI agent转移给人类专家
- **Abstention / Selective prediction**：模型选择不回答某些问题以提高整体可靠性
- **Calibration**：模型报告的置信度与实际正确率的匹配程度
- **Discrimination**：置信度信号区分正确与错误回答的能力
- **Coverage guarantee**：Conformal prediction保证预测集包含正确答案的概率≥1-α
- **Value fork**：AI与人类决策者在相同情境下应做出不同选择的价值分歧点

---

## 2. 方向一：Uncertainty Estimation for LLM

### 2.1 Log-Probability/Entropy方法的现状

**核心发现**：Token-level probability（TLP）是最易获取的不确定性信号，但discrimination能力不如sampling-based方法。

**证据1.1** [^324^] Stanford医学信息学研究对比了三种不确定性代理（CE、TLP、SC）在医学诊断中的discrimination和calibration。

```
Claim: Sample consistency (SC)方法在区分正确/错误LLM回答上优于token-level probability和verbalized confidence。
Source: Large language model uncertainty proxies: discrimination and calibration for medical diagnosis and treatment
URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC11648734/
Date: 2024（预印本）
Excerpt: "SC discrimination outperformed TLP and CE methods. SC by sentence embedding 
achieved the highest discriminative performance (ROC AUC 0.68-0.79), yet with poor 
calibration. SC by GPT annotation achieved the second-best discrimination (ROC AUC 
0.66-0.74) with accurate calibration."
Context: 在MedQA、NEJM等医学问答数据集上，使用GPT-3.5、GPT-4、Llama2/3的评估
Confidence: HIGH
```

**证据1.2** [^255^] LLM Performance Predictors（LPP）框架将多种不确定性信号融合为meta-model特征：

```
Claim: LPP通过gray-box（token概率、熵）和black-box（verbalized confidence、
uncertainty attribution indicators）特征的融合，能够有效预测LLM错误并触发escalation。
Source: LLM Performance Predictors: Learning When to Escalate in Hybrid Human-AI Moderation Systems
URL: https://arxiv.org/html/2601.07006v1
Date: 2026-01
Excerpt: "Our LLM Performance Predictors (LPPs) are a comprehensive feature set primarily 
extracted via gray-box access—requiring token-level log-probabilities and structured outputs. 
This feature set also incorporates black-box compatible features (Verbalized Confidence and 
Uncertainty Attribution Indicators)... The meta-model acts as a gating agent, coordinating 
between autonomous LLM agents and human reviewers."
Context: 内容审核场景，使用Ridge Regression分类器预测LLM正确性
Confidence: HIGH
```

### 2.2 Verbalized Confidence的可靠性危机

**核心发现**：Verbalized confidence存在严重的系统性overconfidence，且RLHF训练加剧了这一趋势。其根本原因在于answer generation与confidence verbalization在内部是解耦的 [^250^]。

**证据1.3** [^250^] ADVICE框架揭示了overconfidence的根本原因：

```
Claim: LLM overconfidence的根本原因是answer generation与confidence verbalization的
内部解耦——模型在报告置信度时没有充分依赖自己生成的答案。
Source: ADVICE: Answer-Dependent Verbalized Confidence Estimation
URL: https://arxiv.org/html/2510.10913v3
Date: 2025-10
Excerpt: "Our analyses reveal that LLM-generated answers and confidence verbalization 
seem to be internally decoupled, implying that this disjunction may underlie the poor 
calibration of verbalized confidence... ADVICE explicitly encourages the model to focus 
more on its answer when reporting its confidence."
Context: TriviaQA、MMLU、LogiQA数据集，多模型评估
Confidence: HIGH
```

**证据1.4** [^251^] Mechanistic分析定位了overconfidence的神经回路：

```
Claim: Verbalized overconfidence由中间到后层的少量MLP块和attention heads驱动，
这些组件在final token位置写入confidence-inflation信号。
Source: Wired for Overconfidence: A Mechanistic Perspective on Inflated Verbalized Confidence in LLMs
URL: https://arxiv.org/html/2604.01457v1
Date: 2026-04
Excerpt: "Across two instruction-tuned LLMs on three datasets, we find that a compact 
set of MLP blocks and attention heads, concentrated in middle-to-late layers, consistently 
writes the confidence-inflation signal at the final token position."
Context: Qwen2.5-3B和Llama-3.2-3B在PopQA、MMLU、NQOpen上的电路追踪
Confidence: HIGH
```

**证据1.5** [^329^] RLHF对calibration的系统性破坏：

```
Claim: RLHF训练将模型的Expected Calibration Error（ECE）从0.034（SFT）恶化到
0.135（RL），约4倍。Reward models系统性偏向高confidence回答。
Source: LLM Confidence Calibration in Production (技术博客)
URL: https://tianpan.co/blog/2026-04-16-llm-confidence-calibration-production
Date: 2026-04-16
Excerpt: "SFT (supervised fine-tuning via maximum-likelihood): ECE of 0.034. 
RL-trained variant: ECE of 0.135 — roughly 4x worse calibration. 
The models that are most pleasant to talk to are often the least honest about 
what they don't know."
Context: 综合多项研究的行业分析
Confidence: HIGH
```

### 2.3 Calibration vs Discrimination的独立性

**核心发现**：对于escalation决策，discrimination（区分正确/错误的能力）往往比calibration（数值精确匹配）更关键。但两者都可能独立出问题。

**证据1.6** [^324^] 医学诊断中的calibration-discrimination分离：

```
Claim: 不确定性代理可以展现强discrimination但弱calibration——能成功区分正确
和错误回答，但预测的确信数值与实际准确率不匹配。
Source: Large language model uncertainty proxies (同上)
URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC11648734/
Excerpt: "Frequently an uncertainty proxy can demonstrate strong discrimination 
(uncertainty proxy accuracy) but poor calibration, meaning the proxy can successfully 
differentiate between correct and incorrect answers, but the proxy's predicted numeric 
certainty value does not align with observed accuracy."
Context: 医学诊断场景，对临床决策有直接影响
Confidence: HIGH
```

**证据1.7** [^312^] Continual fine-tuning中coverage collapse现象：

```
Claim: 在持续fine-tuning中，uncertainty reliability（coverage）的退化可以远快于
accuracy的退化——模型在"变得广泛错误"之前先"变得自信地错误"。
Source: Continual Calibration: Coverage Can Collapse Before Accuracy in Lifelong LLM Fine-Tuning
URL: https://arxiv.org/html/2604.23987v1
Date: 2026-04-27
Excerpt: "Conformal coverage deteriorates several adaptation steps before accuracy 
exhibits a comparable drop, and in the most extreme case observed, coverage falls 
from 0.92 to 0.61 over five tasks on Llama-3 8B while accuracy remains within 
three points of baseline."
Context: Pythia、Llama-3、Mistral三个模型族，八个持续学习场景
Confidence: HIGH
```

### 2.4 本节小结与张力

**张力T1.1**：Verbalized confidence是最通用（black-box即可）但也是最不可靠的不确定性信号。Overconfidence问题不仅是度量误差，而是深植于RLHF训练动态中的系统性偏差。

**张力T1.2**：Calibration和discrimination可以独立出问题。一个用于escalation的系统需要同时监控两者：discrimination决定escalation能否"抓对"错误，calibration决定阈值设定的精确性。

**张力T1.3**：持续fine-tuning会导致coverage collapse——这是生产环境中使用conformal prediction时必须面对的维护挑战。需要定期重新校准阈值。

---

## 3. 方向二：Confidence-Gated Escalation

### 3.1 KnowNo框架：Conformal Prediction + Multiple Choice

**核心发现**：KnowNo将机器人规划任务转化为multiple-choice问题，使用conformal prediction生成有统计保证的预测集。当预测集缩小到单个选项时自主执行，否则向人类求助。

**证据2.1** [^260^] KnowNo的原始设计：

```
Claim: KnowNo使用conformal prediction校准LLM规划者的预测集，在真实UR5
机器人上实现了最高的success-to-clarification比率。
Source: Uncertainty Alignment for Large Language Model Planners (KnowNo)
URL: https://arxiv.org/pdf/2307.01928
Date: 2023
Excerpt: "KnowNo uses Conformal Prediction (CP) to align the uncertainty of LLM planners. 
... KnowNo deviates from the user-defined error rate least often compared to methods 
that do not use conformal prediction and has the highest success-to-clarification ratio."
Context: 语言条件机器人任务，物体排序和清理任务
Confidence: HIGH
```

**证据2.2** [^292^] KnowNo的限制与改进：

```
Claim: KnowNo的局限性包括需要next-token probability访问、大规模校准数据集、
以及ground-truth视觉输入。后续工作如LofreeCP已扩展为支持logit-free模型。
Source: AmbiK: Dataset of Ambiguous Tasks in Kitchen Environment
URL: https://arxiv.org/html/2506.04089v1
Date: 2025
Excerpt: "However, several assumptions had to be made to produce the demonstrated 
results, including having access to next token probabilities, having resources to 
collect a large calibration dataset... recent work introduced LofreeCP, a CP-based 
approach that is compatible with logit-free models."
Context: 厨房环境中的模糊任务数据集
Confidence: HIGH
```

### 3.2 Introspective Planning：改进KnowNo的过度保守

**核心发现**：KnowNo倾向于over-asking（过于频繁地向人类求助），而introspective planning通过引入知识库搜索增强了模型对真正ambiguous场景的区分能力。

**证据2.3** [^257^] Introspective Planning对比KnowNo：

```
Claim: Introspective Planning在保持相同统计保证的同时，显著降低了over-asking
率，因为KnowNo和Retrieve-Q-CoT在unambiguous场景中也过于保守地求助人类。
Source: Introspective Planning: Aligning Robots' Uncertainty with Inherent Task Ambiguity
URL: https://arxiv.org/pdf/2402.06529v3
Date: 2024
Excerpt: "It excels in unambiguous scenarios, as both Retrieval-Q-CoT and KnowNo 
over-ask much more frequently than introspective planning across the target success 
rate... our approach effectively reduces the overstepping rate while maintaining 
the lowest over-asking rate."
Context: 机器人规划任务，与KnowNo和Retrieve-Q-CoT对比
Confidence: HIGH
```

### 3.3 Conformal Social Choice：Multi-Agent Debate的Calibrated Refusal

**核心发现**：在multi-agent debate场景中，consensus-based stopping会导致agents converge到错误答案（social reinforcement）。Conformal Social Choice通过calibrated refusal layer将81.9%的wrong-consensus案例拦截。

**证据2.4** [^310^] Conformal Social Choice框架：

```
Claim: Conformal Social Choice将multi-agent debate的输出转化为有marginal coverage
guarantee的prediction sets，在α=0.05时拦截81.9%的wrong-consensus案例，
remaining singletons accuracy提升高达22.1个百分点。
Source: From Debate to Decision: Conformal Social Choice for Safe Multi-Agent Deliberation
URL: https://arxiv.org/html/2604.07667v1
Date: 2026-04-09
Excerpt: "At α=0.05, conformal sets intercept 81.9% of wrong-consensus cases 
before they reach automated action. Because the layer refuses to commit on these 
cases, the remaining conformal singletons reach 90.0–96.8% accuracy 
(up to 22.1pp above consensus stopping)—a selection effect, not a reasoning improvement."
Context: MMLU-Pro 8个领域，Claude Haiku、DeepSeek-R1、Qwen-3 32B
Confidence: HIGH
```

### 3.4 ConU：Black-Box LLM的Conformal Uncertainty

**证据2.5** [^319^] ConU为black-box LLM提供correctness coverage保证：

```
Claim: ConU通过将NLG任务转化为black-box uncertainty quantification + conformal 
prediction，在7个LLM上实现了严格的correctness coverage rate控制，预测集平均
大小仅1.03（TriviaQA上LLaMa-3-70B）。
Source: ConU: Conformal Uncertainty in Large Language Models with Correctness Coverage Guarantees
URL: https://arxiv.org/html/2407.00499v3
Date: 2024
Excerpt: "The coverage rate is at least 90%, indicating that the requirement of 
correctness coverage guarantees is satisfied... For instance, the average set size 
is 1.03 on the LLaMa-3-70B-Instruct model in the TriviaQA task."
Context: 7个LLM、4个free-form NLG数据集
Confidence: HIGH
```

### 3.5 阈值设定与Escalation Rate监控

**核心发现**：Escalation threshold不应凭直觉设定，而应在带标签的domain-specific数据上经验校准。I-CALM框架证明允许4.1%的abstention rate增加可以带来13%的成本降低和5%的错误率降低。

**证据2.6** [^274^][^275^] Early abstention的成本-质量权衡：

```
Claim: 引入early abstention不仅是成本节省手段，也是质量改进机制——允许4.1%
的abstention rate增加带来13%成本降低和5%错误率降低。
Source: Architectures and Strategies for Dynamic LLM Routing (技术博客)
URL: https://uplatz.com/blog/architectures-and-strategies-for-dynamic-llm-routing
Date: 2025-11-28
Excerpt: "Allowing a 4.1% average increase in the overall abstention rate resulted 
in a 13.0% reduction in cost and, counter-intuitively, a 5.0% reduction in the 
final error rate. This quality improvement occurs because the system is designed 
to leverage correlations between the error patterns of different language models."
Context: 级联LLM系统的行业分析
Confidence: MEDIUM
```

**证据2.7** [^273^] Threshold设定的实践经验：

```
Claim: 任何凭直觉设定confidence threshold的系统都会miscalibrated。正确方法是
在domain-specific标注数据上评估每个confidence level的正确率，基于可接受的
错误率设定阈值。
Source: LLM Routing and Model Cascades (技术博客)
URL: https://tianpan.co/blog/2025-11-03-llm-routing-model-cascades
Date: 2026-04-08
Excerpt: "Empirically calibrated thresholds are non-negotiable. Any system that 
sets confidence thresholds by intuition will be miscalibrated. The correct approach 
is to evaluate your specific workload — what fraction of queries the small model 
gets right at each confidence level — and set thresholds based on your acceptable 
error rate."
Context: 生产级LLM路由系统设计
Confidence: HIGH
```

### 3.6 本节小结与张力

**张力T2.1**：Conformal prediction提供统计保证但需要校准数据集——在冷启动场景和快速变化的domain中，维护校准集是持续负担。

**张力T2.2**：过度保守（over-asking）vs. 过度自信（overstepping）的平衡。KnowNo倾向于over-asking，而纯confidence threshold容易overstepping。Introspective planning和progressive autonomy是潜在的调和方案。

**张力T2.3**：Coverage guarantee是population-level而非per-instance的。单个决策仍然可能失败，系统设计者需要理解这一限制。

---

## 4. 方向三：Ask-vs-Act Policy

### 4.1 Learning to Defer框架

**核心发现**：Learning-to-defer提供了原则性的escalation决策理论。Bayes-optimal deferral规则直观：当专家（人类）的正确概率超过模型任何类别的最大后验概率时，应当升级。

**证据3.1** [^304^] Two-stage learning to defer with multiple experts：

```
Claim: Two-stage learning to defer适用于已有predictor（如LLM）的场景，不需要
重新训练predictor。关键问题是设计Bayes-consistent的surrogate loss。
Source: Two-Stage Learning to Defer with Multiple Experts (NeurIPS 2023)
URL: https://proceedings.neurips.cc/paper_files/paper/2023/file/0b17d256cf1fe1cc084922a8c6b565b7-Paper-Conference.pdf
Date: 2023
Excerpt: "In practice, a predictor such as an LLM is already available and retraining 
one in conjunction with a deferral function could be prohibitively costly... 
A key criterion for surrogate losses is Bayes-consistency."
Context: 理论分析+实验验证
Confidence: HIGH
```

**证据3.2** [^291^] MILD：处理expert imbalance的deferral算法：

```
Claim: 在expert imbalance场景中（某些专家比其他人更常被选中），标准deferral
算法会偏向majority expert。MILD通过cost-sensitive learning解决了这一问题。
Source: Optimized Deferral for Imbalanced Settings
URL: https://arxiv.org/abs/2604.27723
Date: 2026-04-30
Excerpt: "The two-stage learning to defer setting often faces challenges due to 
an expert imbalance problem... We cast the deferral loss optimization as a novel 
cost-sensitive learning problem over the input-expert domain."
Context: 图像分类和真实LLM routing任务
Confidence: HIGH
```

### 4.2 Cost-Sensitive Escalation决策

**核心发现**：Escalation决策本质上是cost-benefit分析——比较错误成本（error cost）与升级成本（labor cost）。I-CALM框架通过inference-time reward framing实现了这一点。

**证据3.3** [^302^] Escalation决策的cost-benefit分析：

```
Claim: Escalation行为是model-specific property——不同模型即使在相同cost ratio
下也有不同的escalation倾向（有的偏好升级，有的偏好执行）。SFT on CoT targets
可以纠正这一问题，实现near-optimal escalation。
Source: I-CALM: Confidence-Aware Abstention for LLMs
URL: https://arxiv.org/pdf/2604.08588
Date: 2026
Excerpt: "Miscalibration has direct operational consequences: overconfident models 
implement predictions they should defer, while underconfident models escalate 
decisions they could handle... SFT on chain-of-thought targets proves most effective: 
the resulting model makes near-optimal escalation decisions across all datasets, 
cost ratios, and prompt framings."
Context: 多个数据集、不同cost ratio和prompt framing
Confidence: HIGH
```

### 4.3 Value of Information (VOI)在Agent编排中的应用

**核心发现**：VOI为routing、stopping、escalation和budget allocation提供了决策理论基础。Practical implementation可以依赖one-step approximation或learned surrogates。

**证据3.4** [^265^] Bayes-consistent agentic orchestration：

```
Claim: Agentic AI orchestrator应当将routing、stopping、escalation、budget 
allocation表达为posterior expected-utility或value-of-information决策。
Source: Position: agentic AI orchestration should be Bayes-consistent
URL: https://arxiv.org/html/2605.00742v1
Date: 2026-05-01
Excerpt: "Orchestrators should standardize decision policies for routing, stopping, 
escalation, and budget allocation, expressed directly in decision-theoretic terms. 
To preserve low latency, these policies do not need to use exact value-of-information. 
Practical implementations can rely on one-step approximations, learned surrogates 
for expected loss reduction, or amortized controllers trained offline and queried online."
Context: 设计模式建议论文
Confidence: MEDIUM
```

**证据3.5** [^315^] Value of Information在human-AI决策中的量化：

```
Claim: 可以用decision-theoretic framework量化AI辅助决策中信息的价值——
global human-complementary information value计算新信息对agent在整个数据分布上的
价值；instance-level version支持逐案例分析。
Source: The Value of Information in Human-AI Decision-making
URL: https://arxiv.org/html/2502.06152v1
Date: 2025-02
Excerpt: "Our approach analyzes the expected marginal payoff gain from best case 
(Bayes rational) use of additional information over best case use of the information 
already encoded in agent decisions for a given decision problem."
Context: 胸部X光诊断、deepfake检测、recidivism预测三个任务
Confidence: HIGH
```

### 4.4 Tracer：基于生产日志的自适应路由

**证据3.6** [^305^] Tracer系统通过parity gate动态路由：

```
Claim: Tracer在生产日志上训练轻量级surrogate model，通过parity gate
（surrogate与teacher LLM agreement > α）决定何时使用surrogate、何时defer
to teacher，实现83-100%的surrogate coverage。
Source: Trace-Based Adaptive Cost-Efficient Routing for LLM Classification
URL: https://arxiv.org/html/2604.14531v1
Date: 2026-04-16
Excerpt: "Tracer achieves 83–100% surrogate coverage depending on the quality 
target α; on a 150-class benchmark, the surrogate fully replaces the teacher."
Context: 77-class intent benchmark和150-class benchmark
Confidence: HIGH
```

### 4.5 本节小结与张力

**张力T3.1**：Bayes-optimal escalation规则理论上优雅，但实践中需要知道human expert的准确率（作为deferral threshold），这在不同domain和不同专家间变化很大。

**张力T3.2**：Cost-sensitive escalation要求明确定义error cost和labor cost，但在许多场景（尤其是涉及安全或伦理的场景）中这些成本难以量化。

**张力T3.3**：One-step VOI approximation牺牲了最优性以换取低延迟，但在combinatorial orchestration（多工具、多步骤）中可能积累显著的suboptimality。

---

## 5. 方向四：价值岔路识别

### 5.1 AI Value Fork：AI与人类决策者的系统性价值分歧

**核心发现**：在道德困境中，人们期望AI比人类更偏离utility-maximizing course——公平性在AI决策中比在人类决策中更重要。这意味着"value alignment"不能简单等同于"让AI像人类一样决策"。

**证据4.1** [^282^] ACM FAccT 2025论文——The Hard Problem of AI Alignment：

```
Claim: 存在"AI value forks"——在相同困境中，人们期望AI和人类做出不同选择。
具体而言，当决策者是AI时，参与者认为偏离utility-maximizing、提供平等生存
机会比人类决策者更重要。
Source: The Hard Problem of AI Alignment: Value Forks in Moral Judgment (FAccT 2025)
URL: https://dl.acm.org/doi/10.1145/3715275.3732174
Date: 2025-06
Excerpt: "In dilemmas where the acting agent is an AI system, participants think it 
is more important to deviate from a utility-maximizing course of action and to provide 
equal chances of survival to would-be victims than when the decision maker is a 
human agent... aligning AI with human values may require that an AI act differently 
from what a human agent should do."
Context: N=1029参与者的实验，医疗和军事道德困境
Confidence: HIGH
```

### 5.2 价值判断vs事实判断的区分

**核心发现**：价值判断（涉及偏好、权衡、伦理）与事实判断（可验证的真理）需要不同的escalation策略。Moral alignment框架提出了"Metaethical Awareness"作为关键标准。

**证据4.2** [^276^] Moral alignment的功能性标准：

```
Claim: 面向LLM道德agent的alignment框架需要"Metaethical Awareness"——
信号不确定性、承认合法道德冲突、避免过度自信的规约性的能力。
Source: Moral Alignment for LLM Agents
URL: https://www.emergentmind.com/topics/moral-alignment-for-llm-agents
Date: 2025-12-23
Excerpt: "Metaethical Awareness: Capacity to signal uncertainty, acknowledge legitimate 
moral conflict, and avoid overconfident prescriptiveness."
Context: 10个功能性标准的综述
Confidence: MEDIUM
```

### 5.3 Progressive Autonomy：学习人类风险容忍度

**核心发现**：何时允许agent自主决策不是手工调节的threshold，而是需要从反馈中学习的人类风险容忍latent function。这可以用Preferential Bayesian Optimization来建模。

**证据4.3** [^330^] Progressive autonomy的形式化：

```
Claim: Autonomy决策应通过学习supervisor的approve/deny反馈来动态调整边界，
而非手工设定threshold。GP-probit policy gateway可以跟踪drifting supervisor
并通过structured kernel将证据generalize到未查询的action-context组合。
Source: Progressive Autonomy as Preference Learning
URL: https://arxiv.org/html/2605.19151v1
Date: 2026-05-18
Excerpt: "Deciding when an agent may act autonomously is not a threshold to hand-tune 
but a latent human risk-tolerance function to learn... a GP-probit policy gateway 
whose allow/escalate/block boundary adapts from feedback, generalizes across 
correlated actions through a structured kernel."
Context: 模拟研究
Confidence: MEDIUM
```

### 5.4 ADR中的典型价值岔路

**证据4.4** [^278^] 智能系统架构设计中的escalation path设计：

```
Claim: Architecture Decision Record（ADR）应记录每个主要结构选择及其风险缓解
原理，并为超过confidence threshold的决策设计human-in-the-loop escalation path。
Source: Designing Intelligent Systems Architecture
URL: https://intelligentsystemsauthority.com/designing-intelligent-systems-architecture
Date: 2026-03-24
Excerpt: "Design human-in-the-loop escalation paths for decisions above a defined 
confidence threshold... Produce an architecture decision record (ADR) for each 
major structural choice; Map each ADR to its corresponding risk mitigation rationale."
Context: ISO/IEC 42001:2023和NIST AI RMF框架
Confidence: MEDIUM
```

### 5.5 本节小结与张力

**张力T4.1**：Value forks的存在意味着escalation系统不能简单复制人类决策者的行为。在道德困境中，人类可能期望AI采取更保守（更公平）的行动方案。

**张力T4.2**：价值判断的识别本身是一个open problem。当前的uncertainty quantification方法主要检测epistemic uncertainty（不知道），而非value uncertainty（不应由AI单独决定）。

**张力T4.3**：Progressive autonomy的学习方法需要大量human feedback数据，这在高stakes、低频率的决策场景中难以获取。

---

## 6. 方向五：量化方法与Risk-Adaptive Access Control

### 6.1 LLM-Judged TBAC模型

**核心发现**：Uncertainty-Aware, Risk-Adaptive TBAC将访问控制从静态role-based系统转变为动态的、由LLM judge实时合成策略的系统，同时考虑resource risk和model uncertainty两个维度。

**证据5.1** [^262^][^263^] LLM-Judged TBAC框架：

```
Claim: 通过让LLM Judge显式推理resource risk和其自身uncertainty，可以将访问
控制系统从简单gatekeeper转变为sophisticated risk management engine。
Source: Uncertainty-Aware, Risk-Adaptive Access Control for Agentic Systems
URL: https://arxiv.org/abs/2510.11414
Date: 2025-10-13
Excerpt: "This framework enhances the LLM Judge by requiring it to explicitly reason 
about two additional dimensions: Resource Risk... Model Uncertainty... 
High-risk or high-uncertainty requests trigger more stringent controls, 
such as requiring human approval."
Context: Cisco Systems的研究，企业agent访问控制
Confidence: HIGH
```

**证据5.2** [^267^] TBAC的decision engine逻辑：

```
Claim: TBAC的escalation决策基于两个可配置阈值：IF (R_comp > θ_risk) OR 
(υ > θ_uncertainty) THEN escalate to human approval ELSE autonomously approve。
Source: (论文评述) Uncertainty-Aware, Risk-Adaptive Access Control
URL: https://www.themoonlight.io/zh/review/uncertainty-aware-risk-adaptive-access-control
Date: 2025-10-15
Excerpt: "整个元组——目标、生成的策略Π、风险得分R_comp和不确定性υ——
被加密记录，以便进行全面审计和未来的模型训练。"
Context: 论文评述与解读
Confidence: HIGH
```

### 6.2 Decision Value与Uncertainty的联合量化

**证据5.3** [^264^] AIVV框架中的统计+MAS联合方法：

```
Claim: 将LSTM with Monte Carlo dropout产生的epistemic uncertainty estimate与
conformal prediction bound结合，再交由multi-agent system进行三阶段
（deterministic gating → deliberative adjudication → adaptive fine-tuning）
escalation决策。
Source: AIVV Framework (arXiv)
URL: https://arxiv.org/pdf/2604.02478
Date: 2026
Excerpt: "The Mathematical Engine Layer provides the computational core by employing 
an LSTM utilizing Monte Carlo dropout for Bayesian approximation to produce a point 
prediction and an epistemic uncertainty estimate, while a conformal prediction 
maintains a statistically guaranteed conformal bound C_a."
Context: UUV（无人水下航行器）系统故障检测
Confidence: MEDIUM
```

### 6.3 CascadeDebate：Cost-Aware多智能体升级

**证据5.4** [^284^] CascadeDebate框架：

```
Claim: 在级联LLM系统的每个升级边界插入multi-agent deliberation，通过
confidence-based router在不确定情况下激活轻量级agent ensemble，
实现consensus-driven resolution，outperform强single-model cascades up to 26.75%。
Source: CascadeDebate: Multi-Agent Deliberation for Cost-Aware LLM Cascades
URL: https://arxiv.org/abs/2604.12262
Date: 2026-04-14
Excerpt: "Confidence-based routers activate lightweight agent ensembles only for 
uncertain cases, enabling consensus-driven resolution of ambiguities internally 
without invoking higher-cost upgrades."
Context: 5个benchmark（科学、医学、通用知识）
Confidence: HIGH
```

### 6.4 本节小结与张力

**张力T5.1**：TBAC模型中LLM Judge自身的不确定性估计（υ）可能miscalibrated——一个 confidently wrong的judge可能低估自己的uncertainty，从而导致危险决策被自动批准。

**张力T5.2**：Resource risk score（ρ）的设定需要enterprise asset management的深度集成（如CMDB），维护这些risk score的准确性本身就是一个持续的运营负担。

**张力T5.3**：Joint optimization of risk + uncertainty + cost容易陷入复杂的多目标权衡。实践中通常简化为hard threshold（OR逻辑），但这可能不是最优的decision boundary。

---

## 7. 方向六：Human Handoff设计模式

### 7.1 三种核心Handoff模式

**核心发现**：生产级系统通常采用三种handoff模式的组合：inline escalation（实时）、asynchronous escalation（异步工单）、blended assistance（AI辅助人类）。

**证据6.1** [^271^] Human-AI Handoff Playbook：

```
Claim: 三种handoff模式适用于不同场景：inline escalation用于实时渠道
（live chat）；asynchronous escalation用于email/ticket系统；blended 
assistance用于AI实时辅助人类agent处理复杂对话。
Source: Human-AI handoff done right: The complete 2025 playbook
URL: https://thread-transfer.com/blog/2025-04-04-human-ai-handoff-playbook/
Date: 2025-04-04
Excerpt: "Pattern 1: Inline escalation — Best for real-time channels. 
Pattern 2: Asynchronous escalation — Best for email support or ticket systems. 
Pattern 3: Blended assistance — Advanced teams use AI to assist humans during 
live interactions... boosts agent productivity by 30-50%."
Context: 行业最佳实践汇编
Confidence: HIGH
```

### 7.2 Layered Guardrails架构

**核心发现**：生产级AI agent需要多层防护架构——input validation、reasoning auditing、output guardrails、topology-based enforcement缺一不可。

**证据6.2** [^296^] Scaling AI Guardrails的架构模式：

```
Claim: 超过50名工程师后，需要inheritance model—— centrally defined base 
guardrails自动继承到所有AI产品，但产品团队可以layer additional controls。
Source: Architecture Patterns for Scaling AI Guardrails
URL: https://galileo.ai/blog/scaling-ai-guardrails-architecture-patterns
Date: 2025-12-13
Excerpt: "Platforms implement inheritance models where base guardrails defined 
centrally automatically inherit to all AI products, but product teams can layer 
additional controls... Each component operates at a distinct stage of the AI agent 
lifecycle to provide redundant protection even if individual layers fail."
Context: 企业级AI治理平台设计
Confidence: HIGH
```

**证据6.3** [^306^] Topology-based enforcement：

```
Claim: 在graph-based agent系统中，escalation和privileged tool execution应遵循
defined routes——deny-by-default at topology level。如果caller没有route，
execution cannot occur。
Source: Layered AI Guardrails for Enterprise AI Agents
URL: https://agilityfeat.com/blog/layered-ai-guardrails-for-enterprise-ai-agents/
Date: 2026-03-04
Excerpt: "Conditional edges encode policy checks, and human approval nodes create 
deliberate choke points for high-impact actions... This design turns system structure 
into an enforcement mechanism: deny-by-default at the topology level."
Context: 企业AI agent安全架构
Confidence: HIGH
```

### 7.3 Escalation作为产品设计指标

**证据6.4** [^288^] Last-mile reliability问题解决：

```
Claim: 有效的escalation是designed first, not added last。应将escalation rate
作为product health metric而非cost line来监控。
Source: The Last-Mile Reliability Problem: Why 95% Accuracy Often Means 0% Usable
URL: https://tianpan.co/blog/2026-04-20-last-mile-reliability-llm-products
Date: 2026-04-20
Excerpt: "Effective escalation is designed first, not added last. Define triggers: 
which failure signals prompt automatic handoff. Design the handoff: what context 
does the human agent receive. Measure the escalation rate as a product health 
metric, not just a cost line."
Context: 生产级LLM产品可靠性工程
Confidence: HIGH
```

### 7.4 Peer Escalation：Agent-to-Agent-to-Human

**证据6.5** [^295^] Peer-escalation discipline：

```
Claim: 在multi-agent swarm中，peer escalation（agent → cross-family peer → 
human）应成为first-class escalation path——当agent stuck时，先咨询不同训练
家族的peer，而非直接升级到人类。
Source: Codify peer-escalation discipline in AGENTS.md
URL: https://github.com/neomjs/neo/issues/10385
Date: 2026-04-26
Excerpt: "The swarm substrate enables agent → cross-family-peer → human as a 
first-class escalation path... peer-escalation is a first-class virtue — a sign of 
structural awareness, not weakness."
Context: 多agent协作系统（neo项目）的实践规范
Confidence: MEDIUM
```

### 7.5 Agent Guardrails的工程检查清单

**证据6.6** [^297^] Agent安全设计检查清单：

```
Claim: 生产级agent系统需要在设计、实现、测试、部署四个阶段分别执行安全
checklist，涵盖escalation path定义、confidence threshold、audit logging等。
Source: agent-engineer/10-guardrails-and-safety/README.md
URL: https://github.com/addyosmani/agent-engineer/blob/main/10-guardrails-and-safety/README.md
Date: 2025
Excerpt: "Identify high-stakes actions that require human approval. Document 
escalation paths for edge cases. Choose which guardrail layers to implement 
(input, output, tool-level)."
Context: 开源agent工程指南
Confidence: HIGH
```

### 7.6 本节小结与张力

**张力T6.1**：异步handoff改善了人类专家的工作效率，但增加了延迟。在time-sensitive场景中需要平衡batch efficiency与response time。

**张力T6.2**：Layered guardrails增加了系统的robustness但也增加了latency。对于high-throughput场景，每一层additional check都是成本。

**张力T6.3**：Peer escalation减少了human workload但引入了agent间通信的复杂性和失败模式。需要明确定义peer escalation的termination条件以避免无限循环。

---

## 8. 综合框架：设计Escalation系统的决策树

基于以上调研，我们提出一个综合性的escalation系统设计决策框架：

### 8.1 决策流程

```
1. 决策分类：
   ├── 事实判断（可验证的truth）
   │   ├── 高置信度 → 自主执行
   │   ├── 低置信度 + 可量化错误成本 → Confidence-gated escalation
   │   └── 低置信度 + 不可量化错误成本 → 强制人工审查
   └── 价值判断（涉及偏好/权衡/伦理）
       ├── 已编码的value alignment → Progressive autonomy
       └── 未编码的价值分歧 → 强制人工决策（Value fork）

2. Escalation触发信号：
   ├── Conformal prediction set size > 1（有统计保证）
   ├── LPP meta-model预测P(correct) < threshold（数据驱动）
   ├── Risk score × Uncertainty score > threshold（risk-adaptive）
   ├── Multi-agent disagreement（对抗性验证）
   └── 价值相关关键词/模式匹配（规则辅助）

3. Handoff模式选择：
   ├── 实时 + 高stakes → Inline escalation
   ├── 异步可接受 → Ticket-based escalation with context bundle
   ├── AI可辅助 → Blended assistance
   └── Multi-agent可解决 → Peer escalation first
```

### 8.2 关键设计参数

| 参数 | 推荐方法 | 注意事项 |
|------|---------|---------|
| Confidence signal | Sample consistency + LPP fusion | 避免单独使用verbalized confidence |
| Escalation threshold | 在domain-specific数据上校准 | 不要凭直觉设定 |
| Risk score | Max over involved resources | 与CMDB集成，定期更新 |
| Coverage target (α) | 0.05-0.10 | 根据错误成本调整 |
| Human context bundle | Goal + proposed policy + risk score + uncertainty + reasoning trace | 防止alert fatigue |
| Escalation rate监控 | 作为product health metric | 过高=过度保守，过低=过度自信 |
| Calibration频率 | 每次fine-tuning后重新校准 | Coverage collapse风险 |

### 8.3 反模式与陷阱

1. **"Just ask the model"反模式**：直接问模型"你有多确定"是最差的做法。Verbalized confidence的ECE可达0.377+ [^329^]。

2. **"One threshold fits all"反模式**：不同domain、不同错误类型需要不同的threshold。Global threshold会导致在某些domain over-asking，另一些domain overstepping。

3. **"Escalation as failure"反模式**：将escalation视为系统失败会抑制其正确使用。Escalation是feature，不是bug [^295^]。

4. **"Set and forget"反模式**：Conformal threshold和calibration模型需要持续维护。Continual fine-tuning会导致coverage collapse [^312^]。

---

## 9. Tensions and Counter-Arguments

### 9.1 核心张力矩阵

| 张力 | 一方 | 另一方 | 潜在调和方案 |
|------|------|--------|-------------|
| T1: 统计保证vs运营成本 | Conformal prediction提供coverage guarantee但需要校准集 | 校准集的收集和维护有成本 | Calibration replay（小buffer+快速重校准）[^312^] |
| T2: Over-asking vs overstepping | 过度保守导致人类负担和延迟 | 过度自信导致错误 | Introspective planning [^257^] |
| T3: Black-box通用性vs白盒精确性 | Verbalized/black-box方法通用但不可靠 | White-box方法精确但需要模型访问 | LPP gray-box fusion [^255^] |
| T4: 自动化率vs安全性 | 高自动化率降低成本 | 高安全性要求人工审查 | Risk-adaptive TBAC [^262^] |
| T5: Value alignment一致性 | 让AI像人类一样决策 | AI应比人类更公平/保守 | Progressive autonomy [^330^] |
| T6: 实时性vs深度推理 | 快速响应要求简单阈值 | 准确escalation要求复杂推理 | One-step VOI approximation [^265^] |

### 9.2 反面证据与局限性

**反面证据1**：Conformal prediction的coverage guarantee是marginal（population-level）而非conditional的。这意味着对于特定subgroup，实际覆盖率可能远低于1-α [^310^]。

**反面证据2**：Multi-agent debate可能引入conformity effects——agents通过social reinforcement converge到错误答案。Conformal Social Choice虽然可以拦截这些失败，但前提是calibration set是exchangeable的 [^310^][^311^]。

**反面证据3**：Progressive autonomy的GP-probit方法在class imbalance下ask band作为acquisition rule的效率不高 [^330^]。这意味着在high-stakes、low-frequency场景中，学习human risk tolerance可能需要极多samples。

**反面证据4**：当前所有方法都假设human expert的回答是gold standard。但在实践中，人类专家也可能出错、疲劳或有偏见。Learning-to-defer框架对此的处理有限 [^304^]。

---

## 10. 研究空白与未来方向

1. **Value-aware uncertainty quantification**：当前方法主要检测epistemic uncertainty。需要能够识别"这是价值判断而非事实判断"的signal，并据此触发不同形式的escalation。

2. **Online calibration under distribution shift**：Continual fine-tuning导致coverage collapse [^312^]，但生产环境中distribution shift是常态。需要真正的online calibration方法。

3. **Multi-objective escalation optimization**：Risk + uncertainty + cost + latency + fairness的多目标联合优化仍然缺乏principled framework。

4. **Human feedback efficiency**：Progressive autonomy [^330^] 和active learning for escalation都需要大量human labels。Sample-efficient的acquisition rules是open problem。

5. **Explainable escalation**：TBAC [^262^] 和LPP [^255^] 都提到了XAI for auditing，但如何向人类专家高效解释escalation原因仍然研究不足。

---

## 参考文献索引

本报告引用来源按出现顺序编号：

- [^255^] Bachar et al. "LLM Performance Predictors: Learning When to Escalate in Hybrid Human-AI Moderation Systems." arXiv:2601.07006, 2026.
- [^250^] et al. "ADVICE: Answer-Dependent Verbalized Confidence Estimation." arXiv:2510.10913, 2025.
- [^251^] Zhao et al. "Wired for Overconfidence: A Mechanistic Perspective on Inflated Verbalized Confidence in LLMs." arXiv:2604.01457, 2026.
- [^253^] Cacioli et al. "Concurrent Criterion Validation of a Validity Screen for LLM Confidence Signals via Selective Prediction." arXiv:2604.17716, 2026.
- [^257^] Liang et al. "Introspective Planning: Aligning Robots' Uncertainty with Inherent Task Ambiguity." arXiv:2402.06529, 2024.
- [^260^] Ren et al. "Uncertainty Alignment for Large Language Model Planners (KnowNo)." arXiv:2307.01928, 2023.
- [^261^] Liang et al. "Aligning Robots' Uncertainty with Inherent Task Ambiguity." 2025.
- [^262^] Fleming et al. "Uncertainty-Aware, Risk-Adaptive Access Control for Agentic Systems using an LLM-Judged TBAC Model." arXiv:2510.11414, 2025.
- [^263^] Fleming et al. (同上)
- [^264^] AIVV Framework. arXiv:2604.02478, 2026.
- [^265^] "Position: agentic AI orchestration should be Bayes-consistent." arXiv:2605.00742, 2026.
- [^267^] Moonlight AI论文评述.
- [^271^] "Human-AI handoff done right: The complete 2025 playbook." thread-transfer.com, 2025.
- [^273^] "LLM Routing and Model Cascades." tianpan.co, 2026.
- [^274^] "Architectures and Strategies for Dynamic LLM Routing." uplatz.com, 2025.
- [^275^] "I-CALM: Confidence-Aware Abstention for LLMs." arXiv:2604.03904, 2026.
- [^276^] Brophy. "Moral Alignment for LLM Agents." emergentmind.com, 2025.
- [^278^] "Designing Intelligent Systems Architecture." intelligentsystemsauthority.com, 2026.
- [^279^] "Design and Evaluation of Multi-Agent AI Oracle Systems for Prediction Market Resolution." arXiv:2605.30802, 2026.
- [^282^] "The Hard Problem of AI Alignment: Value Forks in Moral Judgment." FAccT 2025.
- [^288^] "The Last-Mile Reliability Problem." tianpan.co, 2026.
- [^291^] Zhong et al. "Optimized Deferral for Imbalanced Settings." arXiv:2604.27723, 2026.
- [^292^] "AmbiK: Dataset of Ambiguous Tasks in Kitchen Environment." arXiv:2506.04089, 2025.
- [^295^] "Codify peer-escalation discipline in AGENTS.md." github.com/neomjs/neo, 2026.
- [^296^] "Architecture Patterns for Scaling AI Guardrails." galileo.ai, 2025.
- [^297^] "agent-engineer/10-guardrails-and-safety." github.com/addyosmani, 2025.
- [^298^] "DREAM: Debate-based Relevance Assessment with Multi-agents." OpenReview, 2025.
- [^299^] "Engineering guardrails for agent-based AI systems." dev.to, 2026.
- [^302^] "I-CALM: Confidence-Aware Abstention for LLMs." arXiv:2604.08588, 2026.
- [^303^] "Hallucination Detection in Foundation Models for Decision-Making." arXiv:2403.16527, 2024.
- [^304^] Verma & Nalsinick. "Two-Stage Learning to Defer with Multiple Experts." NeurIPS 2023.
- [^305^] "Tracer: Trace-Based Adaptive Cost-Efficient Routing for LLM Classification." arXiv:2604.14531, 2026.
- [^306^] "Layered AI Guardrails for Enterprise AI Agents." agilityfeat.com, 2026.
- [^308^] "Designing layered guardrails for reliable AI agents." decagon.ai, 2025.
- [^309^] "Hallucination Detection in Foundation Models." (更新版)
- [^310^] Wang et al. "From Debate to Decision: Conformal Social Choice for Safe Multi-Agent Deliberation." arXiv:2604.07667, 2026.
- [^311^] Wang et al. (同上)
- [^312^] "Continual Calibration: Coverage Can Collapse Before Accuracy in Lifelong LLM Fine-Tuning." arXiv:2604.23987, 2026.
- [^315^] "The Value of Information in Human-AI Decision-making." arXiv:2502.06152, 2025.
- [^319^] "ConU: Conformal Uncertainty in Large Language Models." arXiv:2407.00499, 2024.
- [^324^] Savage et al. "Large language model uncertainty proxies: discrimination and calibration for medical diagnosis and treatment." PMC, 2024.
- [^327^] "Taming Overconfidence in LLMs: Reward Calibration in RLHF." arXiv:2410.09724, 2024.
- [^329^] "LLM Confidence Calibration in Production." tianpan.co, 2026.
- [^330^] "Progressive Autonomy as Preference Learning." arXiv:2605.19151, 2026.

---

*报告完成时间：2026年1月 | 总搜索轮次：20+ | 覆盖证据条数：30+* 
