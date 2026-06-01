# feat-391: change workflow skill 立角色目标为北极星 + 放松协作沟通

> 回顾性 spec：本 unit 的改动已先行落地在三个 SKILL.md，本文档补记"做什么 / 为什么"，供后人对账。

## Relations

- Related: feat-341（change workflow skills 立项，本 unit 改的就是它产出的三个 skill）
- Related: feat-350（dispatch-checkin-clarify，本 unit 放松的"报信/澄清"机制由它引入）

## 原始需求

> 现在 change-orchestrator、change-impl-worker，change-reviewer这些skill，我觉得有个问题，讲了一堆流程，规范。但是没有清晰简明的讲清楚他的角色目标，导致容易变成流程机器，而不是实质干好工作。然后change-impl-worker和orchestrator沟通，不需要定那么死，当他决定需要找leader做决策的时候，可以直接提问，不用限制3 轮，也不是只能开工才能沟通，后续干到一半发现需要决策，无法自我决策，也可以沟通

补充：

> 补充一点，流程不可能面面俱到，所以关键还是目标，有了自己的目标，他在流程不明确的情况下，能按目标去走。就像公司的员工一样。

> 目标，或者说是职责。都是一个意思

## 澄清记录

本 unit 为回顾性补 spec，改动在对话中已与用户对齐并落地，无独立澄清轮次。对话中确立的关键点：

- Q1: "角色目标"和"职责"是否同一概念，文档该怎么定性流程与目标的关系？
  A(原话): "目标，或者说是职责。都是一个意思" / "流程不可能面面俱到，所以关键还是目标，有了自己的目标，他在流程不明确的情况下，能按目标去走。就像公司的员工一样。"
  Agent 解读: 目标=职责，是 agent 的北极星；流程与硬规则是支撑职责的手段，不是目的。流程必然有覆盖不到的情形，那时 agent 应回到职责自主判断，像对结果负责的员工，而非"没写到就卡住 / 机械套最近一条规则"的执行器。

- Q2: 沟通约束放松到什么程度？
  A(原话): "不需要定那么死，当他决定需要找leader做决策的时候，可以直接提问，不用限制3 轮，也不是只能开工才能沟通，后续干到一半发现需要决策，无法自我决策，也可以沟通"
  Agent 解读: worker→leader 的咨询应是一条常开通道——任意时刻（含实施中途）、任意轮数，撞上自己拍不了板的决策都能直接发起；同时保留"design 缺口走升级流程"的既有边界。

- Q3: 本 unit 范围是否只限点名的三个 skill？"目标即职责"理念要不要顺带推广到其他 change skill（spec-author / design-author / verifier）？
  A(原话): "回顾性写进去就行，前面已经对齐了"
  Agent 解读: 范围严格只限用户点名的 orchestrator / worker / reviewer 三个 skill（与已落地改动一一对应）；不再走交互式澄清、按已对齐内容回顾性补记；其他 change skill 是否补目标段属本 unit 非目标，留作后续独立判断。

## 用户场景

这套 change workflow（spec → design → orchestrator 派 worker / reviewer / verifier）由项目作者通过派发 agent 实例驱动。每个 skill 是一个 agent 角色的工作说明书。此前三份说明书都以一两句话带过角色定位，紧接着就是十几条硬规则与多段流程——结果 agent 容易把"走完流程、勾完格子"当成目的本身，在流程没覆盖到的灰区要么卡住、要么机械套最近一条规则，而不是回到"我这个角色到底要把什么事做成"去判断。

改动后，打开三个 skill 中任意一个，开篇先读到一段简明的「你的目标」：它先讲清这个角色实质要做成什么（orchestrator：把需求高质量做成并交付；worker：把这一个 milestone 真正做好；reviewer：诚实回答用户能不能干成事），把后面的流程与硬规则明确定性为"支撑判断的脚手架/手段"，并点明"流程不可能面面俱到，缺口处以职责为准绳自己判断，像对结果负责的员工"。agent 因此带着北极星进入流程，而不是被流程牵着走。

第二处场景在 worker 与 orchestrator（leader）的协作上。此前 worker 只有"开工报信"那一刻能提澄清，且封顶 3 轮；一旦实施到中途才发现一个自己负不起责任拍板的理解歧义，就没有顺畅的咨询渠道，只能要么按猜测硬写、要么动用偏重的"design 修订"升级流程。改动后，worker 多了一条常开的咨询通道（§2.5.1）：任意时刻撞上拍不了板的决策都能直接找 leader，不限开工时机、不限轮数，谈到清楚为止；leader 一侧（orchestrator §3.1.1）相应改为随时接得住的常开通道，reviewer 对验收口径的疑问也同样不再受固定轮数限制。同时保留清晰边界——属于 design 缺口（design 写错/漏/行不通）的，仍走既有的停手升级流程，不被当成普通咨询答掉。

## 验收标准

### Requirement: 每个 change workflow skill 开篇有清晰的角色目标段

#### Scenario: 打开任一 skill 读到目标段
- **WHEN** 读 change-orchestrator / change-impl-worker / change-reviewer 任一 SKILL.md
- **THEN** 在硬规则与流程之前，先看到一段简明的「你的目标」，明确陈述该角色实质要做成什么

#### Scenario: 目标段把流程定性为手段
- **WHEN** 读该「你的目标」段
- **THEN** 段内明确把流程与硬规则称为支撑判断的脚手架/手段，并指出"流程不可能面面俱到、缺口处以职责为准绳自主判断"，而非要求机械执行

### Requirement: worker 可在任意时刻向 leader 发起决策咨询，不受轮数限制

#### Scenario: 实施中途发起咨询
- **GIVEN** worker 已开工并实施到一半
- **WHEN** 它撞上一个自己负不起责任拍板的理解歧义
- **THEN** 它能直接向 orchestrator 发起咨询并得到回应，不被"只有开工时才能问"阻断

#### Scenario: 多轮往返谈拢
- **WHEN** 同一歧义需要多次往返才能谈清
- **THEN** 沟通不会因为达到某个固定轮数（如 3 轮）被强制中断、逼 worker 按猜测推进

#### Scenario: design 缺口走升级而非普通咨询
- **WHEN** worker 遇到的是 design 写错/漏/行不通（而非既有意图框架内的理解歧义）
- **THEN** 它走 Pause-on-design-issue 停手升级流程，而不是当作普通咨询被 leader 直接答掉

### Requirement: leader 与 reviewer 一侧的沟通约束与之一致

#### Scenario: orchestrator 接住中途决策请求
- **WHEN** orchestrator 收到 worker 在实施中途发来的决策请求
- **THEN** 它按常开咨询通道处理、给出基于全局的答复，不以固定轮数上限切断对话

#### Scenario: reviewer 口径疑问不受轮数限制
- **WHEN** reviewer 对某条验收标准的预期结果有疑问并向 orchestrator 求证
- **THEN** 它能问到清楚为止，不受固定 3 轮上限；始终对不齐时按最合理理解走并把存疑项标注，让 orchestrator 收口

## 范围与非目标

- 在范围：
  - change-orchestrator / change-impl-worker / change-reviewer 三个 skill 顶部新增「你的目标」段
  - worker→leader 协作沟通放松为常开通道（worker §2.5.1 + §2.5、orchestrator §3.1.1 及其在 §3.2 监控表 / §5 的相关引用、reviewer §2.6）一致化
- 非目标：
  - 不改 change-spec-author / change-design-author / change-verifier（本次只触三个角色）
  - 不放松任何质量类硬规则：三提交、测试门禁、范围边界、真实入口验证、reviewer 零写入与三道闸、越界处置、后台派发 / team 等一律不动
  - 不改派发包字段、worktree / 分支 / 集成路径等机制
  - 不引入新流程阶段或新文档产物
