# feat-411: spec / design 门禁前独立评审 skill

## Relations

- Related: 既有 SDD 流程 skill（change-spec-author / change-design-author / change-verifier / change-reviewer / change-code-review）

## 原始需求

> （最初）/Users/czj/Repos/opensource-hub/superpowers /Users/czj/Repos/opensource-hub/OpenSpec 都是 sdd 的 skill。我的 .claude/skills 中也是，但是我现在缺一个 review spec 和 design 的 skill，帮我看看开源的这两个里面有没有？

> （确认动手）好，新增这两个 reviewer skill。注意，不用模仿现有的 skill 的结构，如何写最合理，按最合理的写法。写中文。

> （补 spec 时的强调）写完要补一个 unit spec，特别注意，写上参考源，哪些不参考他的，以及新增了什么。

## 澄清记录

- Q1: 你特别强调的「参考源 / 哪些不参考 / 新增了什么」，在这份 spec 里写到什么粒度？
  A(原话): 高层定位+对照表概览
  Agent 解读: spec 用叙事讲清三原则（继承骨架 / 排除有害维度 / 新增本体系维度），配一张参考源对照表给概览；每条检查维度的逐条出处留给 design.md。符合 spec/design 分层。

- Q2: 这个 unit 的范围边界怎么定？
  A(原话): 只两个新 skill
  Agent 解读: 范围 = 新增 change-spec-reviewer / change-design-reviewer 两个独立 skill；非目标 = 不改造 author skill 让其自动派发、不跑量化 eval。

- Q3: 还要补充或澄清什么？
  A(原话): 没有，继续吧

## 用户场景

**谁**：走本项目 change-* SDD 流程的人——写完 spec.md 的需求对齐者、写完 design.md 的架构对齐者，以及把控整条流程的用户本人。

**现状痛点**：SDD 流程现在有三道验收闸，但它们**全部在实现之后**——`change-verifier` 审代码是否匹配 spec/design、`change-reviewer` 走产品旅程验收、`change-code-review` 看 PR diff。而**门禁前**（spec.md / design.md 刚定稿、还没交给下一阶段时），只有作者自己的收尾自审（spec-author §5、design-author §5）。

作者自审有结构性盲区：人难免给自己写的东西签字，写作时的思维惯性会让他看不见自己的歧义和矛盾。结果是文档缺陷被带着往下走，直到实现后才被 verifier/reviewer 撞出来——那时返工要连带改代码、改测试，成本比在门禁前改一句话高得多。尤其本项目 spec 有一条致命线：验收标准里只要混进实现/协议条目，会让**整轮** `change-reviewer` 产品验收作废；这种错越早拦越省。

**憧憬场景**：作者写完 spec 或 design、自审过一遍后，调用一个**独立第三方** reviewer——它没有写作时的思维惯性，当陌生人重新读一遍，在门禁前给出「能不能进下一阶段」的判断 + 一份按严重度排序的致命问题清单。作者据此就地修，或放心推进。spec 进 design 之前过 `change-spec-reviewer`，design 进 orchestrator 之前过 `change-design-reviewer`，补上门禁前这道一直空着的闸。

### 设计依据：参考源、不参考什么、新增什么

这次先调研了用户点名的两个开源 SDD skill 库，结论决定了本 unit 怎么造：

- **OpenSpec**：没有内容级评审 skill，只有 CLI `openspec validate` 做结构校验（章节齐不齐、schema 对不对），不审内容质量。对本需求无可借鉴的评审逻辑。
- **superpowers**：没有独立 reviewer skill，但其 brainstorming / writing-plans 内嵌两个 reviewer prompt 模板（`spec-document-reviewer` / `plan-document-reviewer`），用于作者写完文档后派 subagent 复核——定位正是本需求要的。**但 superpowers 是「spec+design 合一、且 plan 是逐行可执行 TDD 脚本」的体系**，而本项目把需求（spec.md，纯用户视角）和方案（design.md，架构对齐、逐步实现下沉给 worker）拆成两份，约束模型完全不同。所以它的 prompt 不能照搬，要分三类处理：

| 处理 | 内容 | 为什么 |
|---|---|---|
| **继承骨架** | ① 精确率校准（只 flag 会让下游真出问题的，措辞/风格一律不报）② `Approved\|Issues Found` + Issues + Recommendations 输出契约 ③ 独立第三方 / subagent 视角定位 | 这三样与文档体系无关，是好评审的通用骨架，直接复用。 |
| **不参考（显式排除）** | superpowers plan-reviewer 的 Completeness（缺 task/step）、Task Decomposition（step 可执行性）、Buildability（零上下文工程师照脚本敲）、No-Placeholder 极端标准；spec 侧的 YAGNI/过度工程、"single plan / 拆 sub-project" 的 Scope 动作 | 这些预设「文档=逐行实现计划」。本项目 design 故意不含代码/step、milestone 目录故意空（worker 自己填 tasks.md）；spec 故意不含任何实现。照搬会把**故意下沉/分层**的内容系统性误报成缺陷。所以不仅不继承，还要在 skill 里**显式钉住「不要报这些」**。 |
| **新增（本体系独有）** | spec：用户可观察红线、澄清原话保真、Requirement/Scenario 结构合规、失败/边界/空态覆盖、grounding 痕迹、bugfix RCA 深度；design：现状分析/契约层 grounding、delta-spec 覆盖、两轨退出标准（[reviewer]/[worker]）、Milestone 反横切拆分、Runbook 可照搬、双目的分层是否崩 | superpowers 一条都没有——它们对应本项目 spec/design 体系的核心失败模式，是这两个 skill 真正的价值所在。逐条维度写在各自 design.md。 |

一处刻意的非对称（不是疏漏）：**YAGNI / 过度设计在 spec-reviewer 不查、在 design-reviewer 要查**。因为本项目把实现从 spec 剥离了——spec 里没有实现可供评判是否过度，而 design 里「找不到 spec 驱动的决策」正是过度设计的信号。这正是体系拆两份文档的直接结果。

## 验收标准

> 说明：本 unit 的「产品」是两个评审 skill，「用户可观察」= 用户对一份文档调用 reviewer 后，从对话/落盘报告里看到的评审行为与结论。

### Requirement: 门禁前评审入口存在且定位清晰

#### Scenario: 审 spec 时触发 spec-reviewer
- **WHEN** 用户对一份定稿的 spec.md / 首文档说「门禁 1 前独立审一遍」
- **THEN** `change-spec-reviewer` 被触发，并以独立第三方视角只审该文档（不读实现代码、不走产品旅程）

#### Scenario: 审 design 时触发 design-reviewer
- **WHEN** 用户对一份定稿的 design.md 说「这个 design 能开干吗」
- **THEN** `change-design-reviewer` 被触发，只审该方案文档

#### Scenario: 与实现后的闸不混淆
- **WHEN** 用户要的是「验证代码有没有匹配 spec」或「走旅程验收功能」
- **THEN** 这两个 reviewer 不揽活，把用户指向 `change-verifier` / `change-reviewer`

### Requirement: spec-reviewer 报对致命问题

#### Scenario: 验收标准混入实现层条目
- **GIVEN** 一份 spec 的某个 Scenario 的 THEN 写了协议字段 / 内部函数名 / 「与某实现逐字一致」
- **WHEN** 用户调 `change-spec-reviewer`
- **THEN** 它报 CRITICAL，并点破后果（会让下游 change-reviewer 整轮产品验收作废），给出改成用户可观察结果的方向

#### Scenario: 结构缺失 / 边界漏覆盖
- **WHEN** spec 出现空 Requirement（有标题无 Scenario）、或某能力只有正常路径没有失败/空态 Scenario、或澄清 A 段疑似被概括
- **THEN** reviewer 分别报出对应 CRITICAL/WARNING，并说明对下游的影响

### Requirement: design-reviewer 报对致命问题

#### Scenario: Milestone 横切拆分
- **GIVEN** 一份 design 把 milestone 拆成 M1=后端 / M2=前端（或 实现/测试/文档）
- **WHEN** 用户调 `change-design-reviewer`
- **THEN** 它报 CRITICAL，指出横切拆分让 worker 串行等前置、连锁波及，建议退回单 M1 或按垂直切片重拆

#### Scenario: delta-spec / Runbook 缺失
- **WHEN** design 有对外行为变化的包却没产 delta-spec、或动了常驻服务却没写可照搬的 Runbook
- **THEN** reviewer 分别报 CRITICAL，并说明收尾无法对账 / reviewer 走旅程会卡住

### Requirement: 不误报「故意下沉 / 分层」的内容

#### Scenario: design 无代码无 step 不报
- **GIVEN** 一份合格的 design.md 不含实现代码、不含逐步 task、milestone 目录为空
- **WHEN** 用户调 `change-design-reviewer`
- **THEN** 它**不**把这些报成「不完整 / 缺步骤 / 没法照着做」——识别这是设计本身

#### Scenario: spec 无技术方案不报
- **GIVEN** 一份合格的 spec.md 不含模块划分、接口签名、选型
- **WHEN** 用户调 `change-spec-reviewer`
- **THEN** 它**不**报「缺技术方案 / 缺实现」，也不对 spec 评判 YAGNI/过度工程

### Requirement: 评审输出契约一致

#### Scenario: 给出结论与可执行清单
- **WHEN** 任一 reviewer 完成评审
- **THEN** 输出固定为 `Approved | Issues Found` 结论 + 按 CRITICAL>WARNING 排序、每条带「不改→下游出什么坏事」+ 具体定位的 Issues + 不阻断门禁的 Recommendations

#### Scenario: 落盘策略
- **WHEN** 结论是 Issues Found
- **THEN** 报告落盘到 `docs/changes/<unit_dir>/spec-review.md` 或 `design-review.md` 供作者对照修改 + 留痕；结论是 Approved 时只在对话给结论、不落盘

## 范围与非目标

- **在范围**：
  - 新增两个独立 skill：`change-spec-reviewer`、`change-design-reviewer`
  - 各自继承 superpowers 评审骨架 + 显式排除其有害维度 + 新增本项目 spec/design 体系的检查维度
  - 定位为门禁前（spec 进 design 之前、design 进 orchestrator 之前）的独立第三方评审
  - 输出：inline 结论 + Issues Found 时落盘评审报告

- **非目标**：
  - **不改造 author skill**（change-spec-author / change-design-author）让其在收尾自动派发 reviewer——保持最小侵入，是否接入由用户后续决定
  - **不跑量化 eval**——评审类 skill 输出主观，量化 benchmark 价值低；验证靠拿真实文档试跑
  - **不审代码 / 不走产品旅程 / 不替作者改文档**——这些分别归 change-verifier / change-reviewer / 作者本人，本 unit 不重叠
  - **不覆盖 bugfix lite 的 fix.md**——lite 无独立 design 阶段，design-reviewer 不适用；fix.md 的 spec 部分由 spec-reviewer 的 bugfix 维度兜（按需）
