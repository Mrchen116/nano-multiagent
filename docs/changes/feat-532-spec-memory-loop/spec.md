# feat-532: 面向 Spec 对齐的 Memory Loop

## Relations

- Related: feat-397

## 原始需求

> 我现在想做loop engnieering（你估计不明白这个词，可以上网搜），来找出一个比较好的加memory方案，直接适配现在的spec，design skill。大概是：找到一个方案，用对应的方案做一次历史spec，design的memory挖掘，挖掘完之后在评测集做独立评测。
>
> 明白我要做什么了吗

> 每一轮可以改变的不只是提示词，而包括：
> 从哪些历史证据里挖掘
> 提取什么：用户偏好、产品判断、设计原则、常见纠偏、领域知识等
> Memory 的结构、粒度、冲突与过期处理
> spec/design 阶段分别检索什么、什么时候注入
> Memory 是直接加载、按需检索，还是由专门 Agent 先形成 task-specific context
> 新证据如何写回，以及哪些内容不能进入长期 Memory
>
>
> 我们不用那么复杂的探索空间，就探索memory的存放和消费方式就行了。memory的来源，都统一为过去的spec中我和agent说的原话，都记录在首文档中了。
>
> 另外，初期我觉得可以只做spec阶段的memory消费评测，design阶段也先不评测。因为design阶段还有个design review 的loop很花时间。
>
> 核心指标就，少不少对齐，最终效果是否更好。“懂不懂你”其实已经包含在其中了，不用单独拎出来。然后用到了memory的地方要能溯源具体是用了哪个memory，不然没法做过程分析。最终效果是否更好，这个要注意，评测集的真值不能完全看我之前对齐过的spec，要看当前最新main的代码状态，因为有些unit我之前对齐的时候没想清楚，或者被agent带歪了，导致对出来不合理，后面的unit修正了。所以每个评测集的数据，你要做一次最新的校对，然后跟我对齐，改了哪些东西，这样评测集才是绝对可靠的。
>
>
> 跟我继续对齐。还有没有不理解的

> 纠正下，不探索“记什么”这个不对啊，Memory 如何组织、存放，就包括了记什么啊。
>
> 是否采用 leave-one-lineage-out？我觉得不需要的，其实只要评测和memory提取的步骤是独立的两个信息不泄露的步骤，不需要这样做也没问题。因为不然的话，你要对评测集的每个样本做独立的memory提取，时间、token花销比较大

> 你这个考虑，也对，那就采用 leave-one-lineage-out，你新提这个方案更麻烦。多花点时间，token，获得更准确的评估。

> 这些不正是要实验出来的吗

> 这个你来设计。

> Q3: 完全不引入 Agent Team。完全相同的 change-spec-author❌，完全一样的话，咋消费memory？

> 对的，

> 现在数据量比较小，先不分。后面实际有问题我再调整吧

> 对，广义纳入。“不纳入普通的 Agent 总结性正文，除非它本身是当时对话中的 Agent 原话；避免把后来整理的结论冒充原始 Memory。” 也不用约束太死，只能说，用户的话高价值，但是当时Agent结合语境分析出来、沉淀出来的东西也不一定没价值。你限制的太死了，后面去做Memory采集的时候就可能会效果很差。现在的大模型，它可能会被你一点限制，有很多奇怪的思考。

> 同意

> 使用你校对确认后的 current owner-answer bank

> 不走change-spec-reviewer，就一把
> ```
> change-spec-author 就行了
> ```

> 方案是迭代出来的，肯定要迭代出一版，方案至少和baseline一样好，但是对齐负担明显下降的。这是我们的目标。

> 好，独立unit，并把我们对齐的内容写到spec中

## 澄清记录

- Q1: 为避免历史评测 case 的答案进入 Memory，是否对每个 case 采用 `leave-one-lineage-out`，分别排除目标 unit 及直接延续、修正或复盘该需求的后续 unit？
  A(原话): 你这个考虑，也对，那就采用 leave-one-lineage-out，你新提这个方案更麻烦。多花点时间，token，获得更准确的评估。
  Agent 解读: 接受额外时间和 token 成本，为每个 case 独立生成排除目标 lineage 的 Memory；同一 case 的重复运行复用该方案已经冻结的 Memory，不因运行结果重新挖掘。

- Q2: Memory 语料是否需要预先规定用户原话、Agent 原话和 Agent 沉淀结论的权重，或限制哪些内容可以成为 Memory？
  A(原话): 这些不正是要实验出来的吗
  Agent 解读: “记什么”、不同来源的权重、是否提炼以及如何组织均属于候选方案的实验空间，不能在评测协议里预先替方案作答。

- Q3: “少不少对齐”如何计量？
  A(原话): 这个你来设计。
  Agent 解读: 主指标采用 Owner contribution units：用户必须提供的每个独立信息、判断或纠正计一个 unit；批量包装不减少 unit，重复询问和 Gate 1 前的实质纠正也计入。对齐轮数、重复问题、Memory 本可解决却仍询问的问题，以及错误使用 Memory 引入的额外纠正作为诊断指标。质量与负担保持二维报告，不用任意权重合成总分。

- Q4: 首阶段是否引入 feat-397 Agent Team；Treatment 是否要求与原版 `change-spec-author` 完全相同？
  A(原话): Q3: 完全不引入 Agent Team。完全相同的 change-spec-author❌，完全一样的话，咋消费memory？
  Agent 解读: 首阶段只评当前 spec author 的 Memory 增益，不引入 Agent Team。Baseline 使用当前原版 `change-spec-author`；Treatment 以它为 backbone，允许增加候选方案所需的 Memory 存放、检索、消费、上下文和溯源能力。

- Q5: 候选方案能否顺手改变与 Memory 无关的 grounding、澄清策略、首文档结构或其他 spec 工作流规则？
  A(原话): 对的，
  Agent 解读: 确认不允许。Treatment 的行为差异必须能归因到 Memory 的存放、消费或溯源；不能把实验变成一次无关的 spec skill 重写。

- Q6: 当前 8 个 case 是否拆分 loop development set 与 locked holdout set？
  A(原话): 现在数据量比较小，先不分。后面实际有问题我再调整吧
  Agent 解读: 当前阶段全部 case 都可向下一轮暴露评测反馈，因此结果只支持“在当前 exploratory benchmark 上更好”，不宣称对未见需求具有已确认的普遍增益。后续数据量扩大或出现过拟合问题时再增加 holdout。

- Q7: Memory 原始语料池是否广义纳入不同类型、不同生命周期首文档中的内容；是否只允许用户原话或 Agent 对话原话？
  A(原话): 对，广义纳入。“不纳入普通的 Agent 总结性正文，除非它本身是当时对话中的 Agent 原话；避免把后来整理的结论冒充原始 Memory。” 也不用约束太死，只能说，用户的话高价值，但是当时Agent结合语境分析出来、沉淀出来的东西也不一定没价值。你限制的太死了，后面去做Memory采集的时候就可能会效果很差。现在的大模型，它可能会被你一点限制，有很多奇怪的思考。
  Agent 解读: 语料池广义覆盖 `spec.md`、`motivation.md`、`incident.md`、`fix.md` 及 active/archive/retired 生命周期的首文档完整内容。用户原话通常高价值，但 Agent 当时结合语境形成的提问、推荐、解读、场景、边界和验收沉淀同样可以被候选方案采用；协议只保留来源与位置，不预判其价值。

- Q8: 最新 `main` 的代码行为与 current docs、后续修正 unit 或当前 owner 判断冲突时，代码是否自动成为最高产品真值？
  A(原话): 同意
  Agent 解读: 确认“代码是当前实际行为的最强证据，但不自动等于正确产品意图”。每个冲突进入 truth delta，列明证据与建议变更，由 owner 确认评测应奖励的结论后再冻结。

- Q9: 评测运行中 spec author 提问时，应重放历史旧回答还是 latest-main 校对后的当前回答？
  A(原话): 使用你校对确认后的 current owner-answer bank
  Agent 解读: 每例在运行前冻结 owner 确认的中性回答库；只有 run 实际提出等价问题时才返回答案。Baseline 与所有 Treatment 共用同一回答库，未提问的答案不主动暴露。

- Q10: 首期 spec 评测是否运行可选的 `change-spec-reviewer → author 修订` 循环？
  A(原话): 不走change-spec-reviewer，就一把
  ```
  change-spec-author 就行了
  ```
  Agent 解读: 每个 run 仅运行一次 `change-spec-author`。Author 完成必要对齐并自认首文档达到 Gate 1 后立即冻结，由实验 blind judge 评估；不运行 workflow reviewer，也不允许 reviewer 修复掩盖 Memory 差异。

- Q11: 当最终质量和对齐负担出现 trade-off 时，是否选择一个折中方案？
  A(原话): 方案是迭代出来的，肯定要迭代出一版，方案至少和baseline一样好，但是对齐负担明显下降的。这是我们的目标。
  Agent 解读: 不以折中方案作为完成。Loop 继续迭代，直到候选方案同时满足“最终 spec 至少不劣于 baseline”和“对齐负担明显下降”两道门禁。

- Q12: 本工作继续放在 feat-397 内，还是建立独立 change unit？
  A(原话): 好，独立unit，并把我们对齐的内容写到spec中
  Agent 解读: 建立独立 unit；复用 feat-397 的评测数据与 clean-room 基础设施，但不把当前 spec skill 的 Memory treatment 混入 Agent Team treatment。

## 用户场景

用户是 nano-multiagent 的唯一产品 owner，也是每个复杂需求中产品判断、范围取舍和长期偏好的主要来源。当前 `change-spec-author` 能把一次需求逐步对齐成首文档，但仍经常需要用户重复解释历史上已经表达过的判断。用户希望为当前 spec 流程找到一种真正有效的 Memory 方式，使 Agent 能从历次首文档积累的语境中复用有价值的信息，减少用户再次回答，同时不因为错误记忆而写出更差的 spec。

这不是先拍板一种 Memory 格式再实现，而是一条可反复运行的探索闭环：候选方案自己决定在允许的历史首文档语料中记什么、如何组织和存放，以及 `change-spec-author` 如何消费；随后用历史 case 的 clean-room 仓和独立评价检验效果。每一轮评测完成后，用户能看到最终 spec 质量、对齐负担，以及从具体产物判断回溯到具体 Memory 和原始首文档证据的过程链路。未达到双门禁的方案作为失败证据进入下一轮分析，继续迭代。

历史 case 不能机械地拿当年的最终 spec 当标准答案。正式运行之前，系统逐例检查最新 `main` 的代码和 current docs，并追踪后来修正、替代或澄清原决定的 unit。发现历史 gold 与当前证据不一致时，先向用户提交 truth delta，说明原结论、当前证据、建议变化和理由；只有用户确认后的 private truth 与 current owner-answer bank 才能用于评价和交互重放。

为了区分“有 Memory”与“整体换了一套更强 Skill”，Baseline 保持当前原版 `change-spec-author`；每个 Treatment 仍以当前 Skill 为主体，只允许加入该候选 Memory 方案实际需要的存放、检索、消费和溯源行为。每个 run 只走一次 author，不使用 Agent Team，也不调用 `change-spec-reviewer` 修正结果。

当前数据量较小，八个 case 暂时全部用于循环探索，不另切最终 holdout。用户接受这意味着当前结论是 exploratory benchmark 结论；未来扩充数据或发现过拟合后再调整分层。

## 验收标准

### Requirement: 候选方案可以完整探索“记什么、怎么存、怎么消费”

#### Scenario: 方案从广义首文档语料中形成 Memory
- **GIVEN** 历史 change units 包含不同类型、不同生命周期的首文档
- **WHEN** 一个候选 Memory 方案开始挖掘
- **THEN** 它可以自行判断用户原话、Agent 原话、Agent 解读和首文档沉淀结论中哪些有价值，并决定其粒度、组织和存放方式
- **AND** 系统不会用预设权重或过窄过滤规则替候选方案作出这些判断

#### Scenario: Memory 进入当前 spec 流程
- **WHEN** 候选方案运行一个评测需求
- **THEN** 它可以为当前 `change-spec-author` 增加该方案所需的 Memory 检索、加载、消费和上下文行为
- **AND** 用户最终仍得到符合当前首文档契约、可进入 Gate 1 的产物

### Requirement: 每个历史 case 都在无自身答案的 Memory 上评测

#### Scenario: 为单个 case 挖掘 Memory
- **GIVEN** 某个历史 case 有自己的目标 unit，以及直接延续、修正或复盘它的后续 lineage
- **WHEN** 系统为该 case 构建候选方案的 Memory
- **THEN** 目标 unit 和该答案 lineage 不参与本次挖掘
- **AND** Memory 挖掘阶段看不到该 case 的公开任务、private truth、rubric 或校对结果

#### Scenario: 更准确的隔离需要额外成本
- **WHEN** 不同 case 需要分别进行 `leave-one-lineage-out` Memory 挖掘
- **THEN** 系统承担相应的额外时间和模型成本，而不会为了省成本退回可能包含目标答案的一份全局 Memory

### Requirement: Memory 对最终判断的影响可以逐项追溯

#### Scenario: Memory 帮助形成 spec 内容
- **WHEN** spec author 使用 Memory 形成一个产品判断、范围边界、推荐或验收场景
- **THEN** 用户能追溯到实际使用的 Memory 条目，以及支撑该条目的首文档位置

#### Scenario: Memory 改变澄清行为
- **WHEN** spec author 因 Memory 决定不再询问、改变问题、预填推荐、拒绝或覆盖某条记忆
- **THEN** 过程记录能显示对应 Memory、采取的动作和它影响的 spec 决策

#### Scenario: Memory 被检索但未采用
- **WHEN** 某条 Memory 被提供给 spec author、但没有被采用或被明确判为不适用
- **THEN** 过程分析能够区分“检索到”与“实际使用”，不把所有召回内容都冒充成有效帮助

### Requirement: Memory 是 Treatment 中唯一的工作流变量

#### Scenario: Baseline 与 Treatment 接收同一需求
- **GIVEN** Baseline 与一个候选 Memory Treatment 处理同一 case
- **WHEN** 两者开始 spec 对齐
- **THEN** 它们面对相同的 brief、产品世界、current owner-answer bank、模型工具条件、预算和 Gate 1 产物要求
- **AND** Treatment 只增加该候选方案需要的 Memory 存放、消费和溯源行为

#### Scenario: 候选方案试图顺手重写 spec 工作流
- **WHEN** 候选方案改变与 Memory 无关的 grounding 责任、澄清原则、首文档契约或 Gate 1 标准
- **THEN** 本轮不能归因为 Memory 方案的有效评测，也不能据此宣布胜出

### Requirement: 每个 run 只评一次 change-spec-author 的直接产出

#### Scenario: Author 完成必要对齐
- **WHEN** `change-spec-author` 根据 brief、仓库事实、Memory（Treatment 适用时）和按需返回的 current owner answers 完成首文档
- **THEN** Author 自认达到 Gate 1 后产物立即冻结并交给独立 blind judge
- **AND** 运行不引入 Agent Team 或 `change-spec-reviewer → author` 修订循环

#### Scenario: Agent 没有询问某项 owner 判断
- **WHEN** current owner-answer bank 中存在一项相关判断，但 spec author 没有询问
- **THEN** runner 不主动泄露答案
- **AND** Author 自行得出正确结论时减少对齐负担，得出错误结论时由最终质量评价如实反映

### Requirement: 对齐负担按用户实际贡献计量

#### Scenario: 一次消息包含多个判断
- **WHEN** spec author 在一次交互中要求用户提供多个独立信息、判断或纠正
- **THEN** 每个独立语义贡献分别计入 Owner contribution units，不因批量包装而只算一次

#### Scenario: 重复询问或在收尾时返工
- **WHEN** 用户需要重复回答同一判断，或在 Author 自认完成前纠正其错误 Memory 判断
- **THEN** 这些实际贡献继续计入对齐负担
- **AND** 报告同时展示对齐轮数、重复问题和错误 Memory 引入的纠正，帮助用户理解负担来源

### Requirement: 最终 spec 由 latest-main 校准后的真值评价

#### Scenario: 历史 spec 与当前产品世界一致
- **WHEN** 最新代码、current docs、后续 unit 和历史结论相互一致
- **THEN** 该结论可以进入本 case 的校准真值，并保留当前证据

#### Scenario: 当前证据之间存在冲突
- **WHEN** 最新代码行为与 current docs、后续修正 unit 或当前 owner 判断不一致
- **THEN** 系统向用户展示 truth delta，而不是自动把代码或历史 spec 当作最高真值
- **AND** 只有用户确认后的结论才进入 private truth 和 current owner-answer bank

#### Scenario: Run 请求一个已校准的 owner 判断
- **WHEN** Baseline 或 Treatment 实际提出与回答库中某项等价的问题
- **THEN** runner 只向该 run 返回同一份 owner 已确认的当前答案
- **AND** 不再机械重放后来被证明不合理的历史旧回答

### Requirement: Loop 只在质量不降且对齐负担明显下降时成功

#### Scenario: 在看到候选结果前固定双门禁
- **GIVEN** 八个 case 的真值已经校对、Baseline 对齐负担已经测得
- **WHEN** 第一份候选 Memory Treatment 的评测结果即将产生
- **THEN** 系统已经固定“质量不劣于 Baseline”和“对齐负担明显下降”的判定口径
- **AND** 后续不能为了让某个候选方案胜出而修改成功门槛

#### Scenario: 候选方案只减少问题但降低质量
- **WHEN** 一个候选方案减少了 Owner contribution units，却产生新的关键遗漏、错误产品判断或越权决定
- **THEN** 该方案不能通过质量门禁，也不能被宣布为成功

#### Scenario: 候选方案质量提高但负担没有明显下降
- **WHEN** 一个候选方案最终 spec 不差于 baseline，但对齐负担没有明显下降
- **THEN** 它保留为实验结果，Loop 继续寻找下一版方案

#### Scenario: 候选方案同时通过双门禁
- **WHEN** 一个候选方案在当前评测集上的最终 spec 至少与 baseline 一样好，且 Owner contribution units 明显下降
- **THEN** 用户获得一版达到本阶段目标的 Memory 方案，以及逐 case 质量、负担和 Memory 使用证据

### Requirement: 当前结果保持探索性结论边界

#### Scenario: 八个 case 被反复用于方案迭代
- **GIVEN** 当前数据量较小、尚未划分 locked holdout
- **WHEN** 系统汇报方案效果
- **THEN** 结论明确限定为“在当前八例 exploratory benchmark 上优于 baseline”
- **AND** 不把该结果表述为已经证明对所有未见需求普遍有效

## 范围与非目标

- 在范围：
  - 当前 `change-spec-author` 的 Memory 存放与消费方案探索。
  - 广义首文档语料池，以及候选方案自主决定记什么、如何提炼和组织。
  - 每个 case 的 `leave-one-lineage-out` Memory 挖掘。
  - Memory 检索与实际消费的逐项证据链。
  - Baseline、候选 Treatment、current owner-answer bank 和一次 author run 的公平比较。
  - 以 Owner contribution units 为主的对齐负担评价。
  - 基于 latest `main`、current docs、后续 unit 与 owner 确认的逐例 truth 校对。
  - 质量不降且对齐负担明显下降的迭代停止条件。
  - 复用 feat-397 评测数据与 clean-room 基础设施。
- 非目标：
  - design 阶段的 Memory 消费和 design 质量评测。
  - `change-design-reviewer` 或任何 design review loop。
  - feat-397 Agent Team treatment。
  - `change-spec-reviewer → author` 修订循环。
  - 与 Memory 无关的 `change-spec-author` 重写或首文档契约变更。
  - 从代码、design、评测 private truth 或其他非首文档来源直接构建个人 Memory。
  - 当前阶段划分 locked holdout，或宣称已经获得对未见需求的普遍因果结论。
  - 在 spec 阶段拍板 Memory 的具体存储技术、检索算法、数据结构或实现模块。
