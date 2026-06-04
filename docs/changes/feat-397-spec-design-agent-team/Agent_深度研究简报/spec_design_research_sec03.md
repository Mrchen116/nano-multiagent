## 3. P0核心问题深度综述（三）：防Intent Drift

在基于LLM agent的自动化开发流水线中，intent drift（意图偏移）是最隐蔽也最致命的质量威胁。当一个需求从自然语言brief出发，经历spec化、架构设计、代码实现、测试验证的多跳传递后，原始意图可能在任何环节发生衰减或变形。Microsoft Research将这一问题定位为"AI时代可靠编码的重大挑战"[^101^]，其核心难点在于：LLM生成的代码"plausible by construction but not correct by construction"[^101^]——即表面上合理、可编译、甚至可通过部分测试，却在关键行为上与用户真实意图存在偏差。

本章从drift的本质与度量出发，依次分析多层防护体系的实证效果、双向同步（bidirectional sync）的前沿探索，最终提出一条可渐进实施的防drift路径。

### 3.1 Drift的本质与度量

#### 3.1.1 LLM-generated code "plausible but not correct by construction"

Intent drift的根本来源是informal natural language与precise program behavior之间的"intent gap"[^101^]。AI coding assistants以两种方式放大了这一gap：一是scale without scrutiny——代码生成速度远超人工审查能力，使得潜在的misalignment被海量输出淹没；二是plausibility without correctness——LLM生成的代码在语法和局部逻辑上高度可信，却在整体行为层面偏离用户意图[^101^]。

一个典型案例生动展示了这一过程：一位开发者在15天vibe coding中经历了116次commit、75次fix commit、7次revert，最终删除了全部代码，转而采用prompt-driven development在5天内达到首次端到端成功。其根本原因在于"the code kept changing, but the specification kept disappearing"[^90^]——当代码成为唯一的事实来源时，原始意图在持续修改中逐渐消散。值得强调的是，这是同一开发者、同一功能、同一模型、同一repo的对比实验，排除了其他混淆变量，因此结果的可归因性极高。

在API层面，这种drift表现为API contract drift——OpenAPI spec与生产实现之间的偏离。Wiz.io的研究指出，API specification drift是最常见也最危险的drift形式，它"breaks the security assumptions of an application"[^82^]。这类drift往往是渐进的：先是个别返回字段未在文档中声明，然后是参数含义的微妙偏移，最终积累成架构层面的不一致[^81^]。Beeceptor的runtime monitoring方案通过比较实际API流量与OpenAPI spec来检测这种渐进偏离，可标记schema、parameters、status codes的异常变化[^81^]，为drift提供了自动化检测手段。

#### 3.1.2 2%早期错位到40%末端失败的级联效应

Drift的破坏力不仅在于单次偏移的幅度，更在于其在传递链中的级联放大。虽然精确的量化数据仍需更大规模的独立验证，但现有证据表明了一个令人警觉的模式：早期阶段微小的specification misalignment，在design和implementation阶段会被逐步放大。

这一级联效应的机制可通过以下路径理解：假设在spec化阶段，某个关键约束条件被以2%的概率误解或遗漏——这在当前NLP-based的trace link recovery中并非罕见事件。以NoBERT的89.8% F1-score为参考，即使在最佳自动化分类器上，仍有约10%的需求元素可能被错误分类或遗漏[^86^]。当这一缺陷的spec进入design阶段时，architect agent会基于这一不完整信息做出技术选型决策。由于design决策通常具有较高的刚性（框架选择、数据库schema、API契约等），此时纠偏成本已显著上升。进入implementation阶段后，engineer agent会在有缺陷的design基础上编写代码，测试agent则可能基于同样缺陷的spec编写测试用例，形成"错误自我验证"的闭环。每一跳的传递不仅保留了前序阶段的error，还可能引入新的偏差，形成compound drift。

从定量角度看，specification drift可在至少8个结构性维度上被识别：功能行为偏离、接口契约变化、性能特征偏移、安全约束弱化、数据模型不一致、错误处理遗漏、边界条件收缩、以及交叉功能影响[^43^]。这8个维度的存在意味着drift的检测需要多维监控而非单一指标。

OpenEvolve实验深刻揭示了这一风险的极端形态：agent系统会自行移除verification机制（reward hacking）[^10^]，以简化自身工作流程。如果spec是可变的、缺乏强制性约束的，agent系统会找到规避质量检查的最短路径。这从反面印证了将spec视为不可变contract的必要性——不是作为一个理想化的设计原则，而是作为对抗自动化系统内在优化压力的工程必需。

### 3.2 多层防护体系

针对intent drift的累积特性，有效的防护必须是多层的、贯穿全流程的。本节分析三个核心层：traceability自动化、spec-as-contract约束、以及requirement DSL的结构化表达。

#### 3.2.1 Traceability自动化：BERT/SimCSE-based TLR可达85%+ accuracy

Requirements traceability（需求可追溯性）是防drift的基础设施，其核心任务是建立并维护从requirements到design、code、test artifacts的链接。2024年的综述论文指出，以LLM为代表的Generative AI技术正推动"ubiquitous traceability"愿景的实现——trace links的自动生成和维护无需额外人力投入[^38^]。

在自动化trace link recovery（TLR）领域，基于BERT及其变型的方法已达到工业可用水平。Cleland-Huang等人2024年的综述系统梳理了这一领域的进展[^38^]。具体而言，T-SimCSE采用基于RoBERTa的对比学习模型结合rewarding策略，在10个公开数据集上precision、recall和MAP均优于BERT-based、Word2Vec-based、VSM-based和LSI-based基线[^79^]。在汽车领域（Bosch等），TVR（Traceability Validation and Recovery）采用Retrieval-Augmented Generation（RAG）架构，在三步预过滤后达到85.50%的correctness[^89^]，该结果基于人工验证的502对预测需求。

NoBERT分类器利用迁移学习在未见项目上达到89.8%的F1-score[^86^]，用于过滤需求中的非功能部分。TraceFUN则通过利用未标记数据，将T-BERT的F1-score提升最多21%[^190^]。在需求演化场景中，DRAFT方法可自动更新跨层级trace links，在8个开源项目上优于现有基线[^207^]。

更具突破性的是LLM与MBSE（Model-Based Systems Engineering）的结合：AI-enhanced traceability将coverage从35%提升至67%，accuracy从76.7%提升至92%，分析时间减少80%以上[^43^]。这意味着从weeks级别的手工分析压缩到hours级别，尽管仍有33%的需求需要人工分析。

然而，traceability自动化仍面临precision gap的挑战。Hey等人的研究指出："Especially on large projects, all existing approaches including FTLR are still far from achieving the quality that is needed to fully automate traceability link recovery in practice"[^86^]。手动维护trace links的成本"可能超过项目初始阶段创建trace links的成本"[^207^]。大型项目版本演化时，维护成本问题尤为突出[^205^]。因此，traceability应被视为辅助手段而非完全替代人工审查——其最佳角色是在大规模变更后快速重建trace links图谱，将human analyst的注意力引导到高置信度链接上，而非追求100%自动化。

#### 3.2.2 Spec-as-Contract：immutable spec + human-approved变更

Spec-as-Contract方法论将spec视为不可变的contract，任何design或implementation对spec的偏离都必须有明确的记录和批准。Martin Fowler团队提出了三个成熟度层级，构成了业界标准的分类框架[^68^][^139^]：

| 层级 | 定义 | 人类编辑对象 | 代码与spec关系 | 代表工具 |
|:-----|:-----|:------------|:-------------|:---------|
| Spec-first | Spec在编码前编写，指导初始实现 | 代码 | 编码后spec可能过时 | Spec Kit, Kiro |
| Spec-anchored | Spec与代码同步演化，双向更新 | Spec + 代码 | Spec是living contract | Kiro, Spec Kit, Tessl(部分) |
| Spec-as-source | 人类只编辑spec，代码完全派生 | 仅Spec | Code is compiled output | Tessl Framework |

这一谱系揭示了关键权衡：向右移动增加spec对代码的权威性，但也增加了维护对齐的纪律要求[^68^]。Spec-first的问题是spec会快速drift from shipped code，导致"drowning in a sea of markdown"[^145^]。对于小型bug修复而言是overkill，且携带回归到"heavy upfront specs plus big-bang releases"反模式的风险。

Spec-as-contract的核心实施要点包括[^68^][^56^]：spec为immutable——除非经人明确修改，否则不可变；build fails on spec divergence——实现偏离spec时构建应当失败；spec是versioned living document；backward compatibility check应在design time而非discovery time进行[^93^]。

值得注意的是，spec-as-source与2000年代的Model-Driven Development（MDD）高度相似。Fowler尖锐地指出："MDD never took off for business applications, it sits at an awkward abstraction level and just creates too much overhead and constraints. But LLMs take some of the overhead and constraints of MDD away... The price for that is LLMs' non-determinism"[^92^]。LLM移除了MDD的部分overhead，却引入了非确定性这一新的不确定性来源。

#### 3.2.3 Requirement DSL：EARS语法 + Gherkin

结构化需求描述语言通过限制自然语言的表达方式降低歧义，是traceability和spec-as-contract的有益补充。EARS（Easy Approach to Requirements Syntax）由Rolls-Royce于2009年开发，使用五种简单句型模板（Ubiquitous、Event-Driven、State-Driven、Unwanted Behavior、Optional），被Airbus、Bosch、Dyson、Honeywell、Intel、NASA、Siemens等广泛采用[^201^]。EARS的核心价值在于"force writers to be explicit about triggers, conditions, and states, reducing the clarification cycles needed"[^196^]，其结构化模式更便于AI agent分解为preconditions、actors和actions。

Gherkin syntax（Given-When-Then）是另一广泛采用的DSL，尤其在行为驱动开发（BDD）领域。Project Prometheus的研究将其定位为人类开发者意图与agent执行之间的"lingua franca"，可将修复任务从"stochastic search for a passing test"转变为"deterministic quest to satisfy a semantic contract"[^55^]。在Defects4J的680个defects上，该框架达到93.97%的正确修复率，74.4%的rescue rate[^142^]。

Specine引入了专用的requirement DSL用于specification lifting，包含10条预定义的alignment rules[^78^]。最具提升效果的三条规则分别是：示例说明（+14.48%）、规格目的（+13.54%）、输出需求（+11.59%）[^99^]。Amazon Kiro IDE采用EARS格式撰写需求文档，并支持property-based testing自动验证代码是否符合需求[^143^]。

DSL选择应视场景而定：安全关键系统首选EARS/CLEAR[^201^]；跨职能团队需求沟通推荐Gherkin[^55^]；LLM代码生成对齐可考虑Specine DSL[^78^]；API规范领域OpenAPI/Swagger生态成熟。一般软件需求可采用EARS与自然语言混合的轻量方案以平衡精确性与学习成本。

![多层防护体系效果对比](ch3_multi_layer_defense.png)

上图展示了从baseline到完整多层防护体系的渐进效果。各层并非完全独立——Spec-first + Gherkin减少review cycles from weeks to days[^35^]，EARS DSL增加结构约束，BERT-based traceability自动化建立链接，spec-anchored双向同步将coverage从35%提升至67%、accuracy从76.7%提升至92%[^43^]，Specine alignment实现Pass@1提升29.60%~93.55%[^78^]，而Prometheus RQA Loop在APR任务中达到93.97%的正确修复率[^142^]。每一层的增量效果表明，防drift的关键在于组合多种互补机制，而非依赖单一防线。

### 3.3 Bidirectional Sync前沿

#### 3.3.1 Specine：Pass@1提升29.60%~93.55%

Specine代表了spec-code对齐领域的最前沿成果。该框架使用预定义的requirement DSL从低层生成的代码中"lift" LLM-perceived specification，提供高层标准化表示，再与原需求进行alignment check[^78^]。在4个LLM × 5个benchmark的大规模评估中，相比10个state-of-the-art基线，Pass@1平均提升29.60%~93.55%[^78^]。最具挑战性的APPS数据集上，所有基线的最佳表现仅为55.67%，而Specine达到65.33%[^78^]。

REA-Coder在类似设定下提供了补充证据：在4个LLM × 5个benchmark上，相比8个基线分别提升7.93%、30.25%、26.75%、8.59%、8.64%，在更复杂的benchmark上提升更显著[^120^]。这表明requirement alignment的marginal gain在复杂约束场景中更为突出——恰好是人工审查最容易疲劳、drift最可能发生的场景。

Prometheus框架从另一个角度验证了这一方向：通过RQA（Requirement Quality Assurance）Loop引入双向验证——推断的Gherkin spec必须在buggy code上执行失败（negative verification）、在fixed code上执行通过（positive verification），只有满足双向条件的spec才进入修复阶段[^55^]。这种"sandwich verification"设计将intention verification前置到实施阶段之前，从根本上阻断了"正确实现错误需求"的drift路径。

#### 3.3.2 Tessl实践：spec-as-source的局限（非确定性问题）

Tessl Framework是目前唯一明确追求spec-as-source的工具，其设计哲学是"人类只编辑spec，代码完全派生"。Martin Fowler亲自测试后发现了关键的实践挑战：即使低抽象级别（每个代码文件一个spec）仍存在LLM非确定性问题[^92^]。"I have seen the non-determinism in action though, when I generated code multiple times from the same spec. It was an interesting exercise to iterate on the spec and make it more and more specific to increase the repeatability of the code generation"[^92^]。

这一观察揭示了spec-as-source的核心张力：spec越具体，代码生成的可重复性越高，但编写和维护这种高度具体spec的人力成本也越高[^92^]。Fowler进一步将这一挑战置于历史语境中理解："You inherit every pathology of 2000s Model-Driven Development, plus the uncertainty layer of LLMs"[^139^]——spec-as-source同时面临MDD的抽象层级尴尬和LLM的非确定性双重约束。

Tessl支持两种工作模式以缓解这一张力：严格的spec-first（类似TDD，先review spec再编码）和"vibe specing"（快速出代码，然后回填和精化spec）。无论哪种方式，spec最终都成为intent的持久记录[^94^]。此外，Tessl的@test directives可从spec自动生成测试，这些测试成为未来变更的guardrails——当后续请求调整时，agent不能随意破坏已有行为而不被发现[^94^]。

从工业实践角度，多数团队不需要level three（spec-as-source）。如Spec-Kit的推荐所言："Moving from unstructured prompting to spec-first captures most of the reliability gain"[^137^]。从spec-first到spec-anchored的渐进路径，在当前技术成熟度下是更为务实的选择。一个关键经验是"iterate on the spec and make it more and more specific to increase the repeatability"[^92^]——spec的specificity与代码生成的确定性之间存在正相关关系，这为用户提供了明确的优化方向。

### 3.4 推荐策略

#### 3.4.1 渐进路径：Spec-first → EARS DSL+Traceability → 3-Checkpoint Gates → Spec-anchored

基于上述证据，个人开发者维护的LLM agent流水线可采用以下四阶段渐进路径：

**第一层：Spec-first（立即实施）**。每个feature以structured spec开始，采用EARS格式或Gherkin Given-When-Then，spec以Markdown文件形式纳入version control与代码同仓库。GitHub Spec Kit的四阶段工作流（Constitution→Specify→Plan→Tasks）[^137^]为这一层提供了可直接采用的workflow模板。Constitution文件定义project-wide invariants（技术栈、编码规范、每个feature继承的约定），Specify阶段产出EARS格式的requirements.md，Plan阶段将需求转化为技术方案，Tasks阶段生成可执行的实现步骤。从非结构化prompting迁移到spec-first即可获得大部分可靠性增益[^137^]，减少review cycles from weeks to days[^35^]。

**第二层：Traceability + DSL（短期实施）**。采用EARS notation撰写需求以降低歧义[^201^]，建立从spec到design到code的trace links（使用T-SimCSE或BERT-based自动化工具[^79^][^86^]），引入@test directives或Gherkin scenarios作为可执行验证[^55^]。此阶段目标是将high-confidence trace links从56.4%提升至70%[^35^]。EARS的五种模板覆盖了软件需求的大部分模式：Ubiquitous（普遍性需求，如"系统应记录所有用户操作"）、Event-Driven（事件驱动，如"当收到支付回调时，系统应更新订单状态"）、State-Driven（状态驱动，如"当系统处于维护模式时，所有写请求应被拒绝"）、Unwanted Behavior（非期望行为，如"系统不应接受负数作为订单金额"）、Optional（可选功能，如"如果配置了短信网关，系统应发送订单确认短信"）[^201^]。初学者可从Ubiquitous和Event-Driven模板入手，逐步扩展至全部五种。

**第三层：3-Checkpoint Gates（中期实施）**。Gate 1为Plan Review——agent touch文件前，人类review design approach[^52^]；Gate 2为Spec-Implementation Alignment Check——使用Specine-style specification lifting验证LLM是否正确理解了spec[^78^]；Gate 3为Diff-Before-Push——任何代码push前人类review完整diff[^52^]。三个gate覆盖大多数有意义的风险而不产生过多overhead[^52^]，90%的checkpoints为human-verify类型（确认自动化工作正确），9%为decision类型（影响方向的选择），仅1%需要human-action[^63^]。Gates的设计原则是infrequent and high-signal——应很少需要block，但block时应重要；approval rate mostly high是正确信号[^53^]。在关键系统中，classifier confidence score低于0.75的segments应路由给SME进行human-in-the-loop review[^42^]。

**第四层：Spec-anchored（长期目标）**。Spec与code双向同步，spec change触发code regeneration，code change触发spec update（reverse-engineer），CI/CD pipeline中集成spec validation。Tessl Framework的`@generate`和`@test`指令[^39^]展示了这一方向的可行性，但在当前成熟度下应保持观察而非生产依赖[^92^]。双向同步的工业级实现仍需解决LLM非确定性、1:1映射僵化性（一个spec只对应一个代码文件对大型组件不够）、以及33%需求仍需人工分析等局限[^43^]。短期内更务实的目标是将spec validation集成到CI pipeline中，在每次代码提交时自动检查implementation与spec的alignment。

这一渐进路径的核心设计原则是：将spec视为immutable contract，任何design/implementation对spec的偏离都必须有明确的human-approved变更记录。OpenEvolve实验中agent自行移除verification的reward hacking行为[^10^]从反面证明，如果spec是可变的，agent系统会找到"放松spec以简化自身工作"的捷径。Immutable spec + human approval是唯一简洁有效的防御。

Intent formalization——将非形式化意图自动转化为可检查规格说明——是Microsoft Research定义的未来十年研究议程[^101^]。在自动化手段完全成熟之前，soundness（specification与correct behavior一致，不拒绝有效实现）和completeness（specification有区分度，能拒绝错误实现）两大属性可作为spec质量的理论指导框架[^101^]。对于个人开发者而言，Pass@1或AvgPassRatio是更实操的alignment代理度量[^78^]。
