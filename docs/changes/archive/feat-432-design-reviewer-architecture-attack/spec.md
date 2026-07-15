# feat-432: design-reviewer 增加「架构进攻」腿,从架构最优视角审设计好坏

> 回顾性 spec:本 unit 的改动在对齐过程中已完成(`change-design-reviewer/SKILL.md`),
> 本文档据用户原话回填,记录「为什么改、改成什么样」,供后续对账与复用。

## Relations

- Related: feat-411-spec-design-reviewers（产出 change-spec-reviewer / change-design-reviewer 两个门禁前评审 skill；本 unit 是对其中 design-reviewer 的能力演进）

## 原始需求

> （反思触发）现在，我要你反思design reviewer skill的问题，之前你没有检查出问题，在我提醒后才检查出来。是不是skill写的有缺失。

> （点破病根）我觉得你窄了，依赖方向只是一个点，以后可能还会有其他的设计不好的地方会被漏。这个skill有没有真正从taste，从架构最优的角度去思考设计的好坏。而不只是判断"这个design是不是基于代码事实，是不是完备的design"。

**背景**：本 unit 的导火索是一次真实漏判——design-reviewer 第一轮对 bugfix-431 的 design 做了详尽台账、逐条 ✓、给出 Approved，却漏掉一个架构最优性缺陷（共享 helper 放在最外层 sdk、却让最内层 core 反向依赖它）。用户提醒"从架构 taste 角度想想"后才被查出。用户由此质疑：skill 是不是只会核"design 完不完备、符不符合代码事实"，而没有真正评判"这设计好不好"。

## 澄清记录

- Q1: 先定位 skill 缺什么——是缺一条具体维度（如依赖方向检查），还是更结构性的东西？
  A(原话): 我觉得你窄了，依赖方向只是一个点，以后可能还会有其他的设计不好的地方会被漏。这个skill有没有真正从taste，从架构最优的角度去思考设计的好坏。而不只是判断"这个design是不是基于代码事实，是不是完备的design"。
  Agent 解读: 病根不是少一条 checklist 项，而是 skill 的认知模式整体偏"核对完备性/合规性"，缺一个主动评判"方案是不是最优"的环节。依赖方向只是这种缺失碰巧具象出的一个点。

- Q2: 修法方向先看历史——
  A(原话): 你先看下当初做这个skill的unit的文档
  Agent 解读: 读 feat-411 spec 后发现：taste 维度（"方案非最优/临时凑合"）当初就有意识地写进去了，但被放在"第三步整体判断"的一个软 WARNING bullet 里。而 feat-411 自己也踩过同构的坑（bugfix-417 首跑漏判架构缺陷），当时的解药是"建台账→逐条核→记证据"。结论：台账治好了"抽查偷懒"，却对 taste 有挤出效应——把注意力全吸到可逐条引证的原子上，"整体方向是不是最优"塞不进台账，沦为一扫而过的软维度。

- Q3: 参考什么形态来补这条腿？
  A(原话): 你这个是一个好idea，你也参考下，/Users/czj/Repos/nano-multiagent/.claude/skills/change-code-review/SKILL.md。每次写完代码这个review是最有效的，能找到大量问题
  Agent 解读: code-review 高产的原因是"多路主动进攻"而非"核对清单"——每个 finder 角度是一个具体的生成式攻击动作，每条候选必带具体 failure_scenario。把这个范式移植到架构层。

- Q4: 还要参考哪些判断"设计好坏"的依据？另外我之前提的"先造影子方案再对赌"这个点子合适吗？
  A(原话): /Users/czj/Repos/opensource-hub/mattpocock-skills/skills/engineering/improve-codebase-architecture/SKILL.md 再参考上这个，也能提供design的好坏的见解。另外，出影子方案这个点子我觉可能不太适合这个场景，还是类似change-code-review这种直接找问题更直接
  Agent 解读: ① 吸收 mattpocock 的架构好坏判据（删除测试、深/浅模块、一处实现别造接缝、就近性）作为进攻角度的判据。② 否决"影子设计对赌"——它是多余的中间层（删掉它，"找架构问题"这个目的不丢），改成像 code-review 一样直接拿 design 找问题。

- Q5: 评审报告落盘策略要不要改？
  A(原话): 落盘 改为都落，Approved也是
  Agent 解读: 无论 Approved 还是 Issues Found，完整报告（含台账 + 架构进攻段）都落盘，不再"Approved 只在对话给、不落盘"。让"真核过、真进攻过"在每次评审都留痕。

- Q6: 这次修改本身怎么收尾？
  A(原话): 改的差不多了，其实这次修改本身也是一个需求，回顾性记录一个spec，注意包含我的原话。然后统一commit
  Agent 解读: 当前 design-reviewer 改动即本 unit 交付；补一份回顾性 spec（含用户原话），与 skill 改动统一 commit。

## 用户场景

**谁**：走本项目 change-* SDD 流程、在门禁 2 前调用 `change-design-reviewer` 的人——架构对齐者，以及把控流程质量的用户本人。

**现状痛点**：design-reviewer 原本只有一套"核对"动作——把 design 拆成承重原子（现状/决策/spec/delta-spec/milestone），逐条问"这条成立吗"。这套机制擅长抓**自洽性、完备性、合规性**缺陷，但有一个结构性盲区：**一个每条原子都成立、整体却绕了远路的方案，逐条核全部通过，照样被判 Approved。**

这不是假想。design-reviewer 第一轮审 bugfix-431 的 design，台账详尽、每条 ✓、结论 Approved；但方案把一个纯逻辑的共享 helper 放在最外层 sdk、又让最内层 core 反向依赖它——一个会撞分层硬规则的架构缺陷。台账查不出它，因为"这个抽象该放哪一层、是不是最好的走法"不是任何一条可逐条引证的原子。直到用户提醒"从架构最优角度看看"，才被查出。

更深一层：这种漏判在 feat-411（产出这个 skill 的 unit）就以同构形态发生过一次（bugfix-417 首跑，漏掉让整层报废的架构缺陷，拖到实现验收才炸）。当时的解药"建台账→逐条核→记证据"治好了"抽查偷懒"，却没给"评判最优性"配一个同等强制的动作——taste 维度一直停留在"整体通读时一扫而过的软 WARNING"，从没真正生效。

**憧憬场景**：用户对一份 design 调用 `change-design-reviewer`，它除了逐条核对自洽/完备/合规，还**主动拿每个架构选择去攻**——像写完代码后那个"每次都能挖出一堆问题"的 code-review 一样，直接对 design 的每个新增/搬动的模块、抽象、职责、间接层发问："这是不是最好的走法？"它会用一组具体判据（归属放对没、删掉这层复杂度是集中还是只搬走、接口是不是浅得没换来简化、是不是补丁掩症状）找出绕路、多余抽象、重造轮子、临时凑合，每条都说清"不改→长远付什么代价"。一个看着完备、实则绕路的方案，不再因为"台账全 ✓"就被放行。评审结论需要**两条腿都过**：核对无硬伤 **且** 进攻挖不出存活的最优性缺陷。每次评审的台账和进攻记录都落盘留痕。

## 验收标准

> 本 unit 的"产品"是 `change-design-reviewer` skill，"用户可观察"= 用户对一份 design 调用它后，从对话 / 落盘报告里看到的评审行为与结论。

### Requirement: 评审包含主动的「架构进攻」环节，而非只核对完备性

#### Scenario: 每条原子都成立但整体绕路的方案被抓出
- **GIVEN** 一份 design，逐条核对（现状/决策/spec/delta-spec/milestone）全部成立，但某个架构选择绕了远路（如把共享逻辑放错层、让内层反向依赖外层）
- **WHEN** 用户调 `change-design-reviewer`
- **THEN** 它在核对之外主动做一轮架构进攻，报出这个最优性缺陷、指出更优走法，而不是因为"台账全 ✓"就直接 Approved

#### Scenario: 评审产出里能看到进攻确实逐角度走过
- **WHEN** 任一次 design 评审完成
- **THEN** 报告里有独立的"架构进攻"记录，逐角度给出结论；某角度没发现也显式写"走完无存活发现"，不允许整段省略（让"真进攻过"和"没进攻"产出不同的东西）

### Requirement: 进攻覆盖多类设计劣化，不止依赖方向

#### Scenario: 多余抽象被删除测试挑出
- **GIVEN** 一份 design 新增了一个间接层 / 包装 / 工厂，而它包装的实现只有一处
- **WHEN** 用户调 `change-design-reviewer`
- **THEN** 它指出这层是多余的（删掉后复杂度只是搬个地方）或是为"将来可能"预造的假想接缝，建议去掉

#### Scenario: 浅封装 / 重造轮子 / 补丁掩症状被分别挑出
- **WHEN** design 里出现"接口几乎和实现一样复杂的无谓封装"、"该复用既有能力却新造一套"、或"在共享设施上叠特例 / 打补丁掩盖症状"
- **THEN** reviewer 分别报出对应问题，并指出根上的更优走法

### Requirement: 进攻发现精确率导向，带具体长远代价

#### Scenario: 报出的进攻发现都说清长远代价
- **WHEN** reviewer 报出一条架构进攻发现
- **THEN** 该发现带"不改→长远付什么代价"（多余抽象的维护税、错放归属的复发、补丁的债、浅模块的认知摩擦）；说不出具体代价的口味洁癖不报

### Requirement: Approved 是「核对 + 进攻」双闸

#### Scenario: 进攻挖出致命缺陷时不得 Approved
- **GIVEN** 一份 design 的核对台账全部通过，但架构进攻挖出一个会让 worker 实施时撞分层硬规则 / 依赖边界的 CRITICAL
- **WHEN** 用户调 `change-design-reviewer`
- **THEN** 结论是 Issues Found（不是 Approved）——两条腿任一有未化解的 CRITICAL 都不能放行

### Requirement: 评审报告一律落盘

#### Scenario: Approved 也落盘
- **WHEN** 评审结论是 Approved
- **THEN** 完整报告（结论 + 台账 + 架构进攻段）落盘到 `docs/changes/<unit_dir>/design-review.md`，而不是只在对话里给结论

#### Scenario: Issues Found 落盘
- **WHEN** 评审结论是 Issues Found
- **THEN** 完整报告同样落盘到 `design-review.md`，供作者逐条对照修改 + 留痕

## 范围与非目标

- **在范围**：
  - 给 `change-design-reviewer` 增加与台账平级的"架构进攻"环节（四个进攻角度：归属 / 该不该存在 / 深还是浅 / 治本还是补丁），吸收 code-review 的"直接找问题 + 必带后果"范式与 mattpocock 的架构好坏判据，用本土语言表达、不挂外部术语
  - Approved 改为"核对 + 进攻"双闸
  - 评审报告一律落盘（含 Approved）

- **非目标**：
  - **不引入 subagent fan-out / 多角度投票**——直接在主评审里走进攻角度，不复制 code-review 的并行机制
  - **本期不改 `change-spec-reviewer`**——它是否配一个对称的"需求最优性"进攻闸、落盘是否同步改为一律落，留待后续决定（已向用户标注为待定）
  - **不放弃既有核对台账**——进攻是补一条腿，不替代逐条核
  - **不改其他验收闸**（change-verifier / change-reviewer / change-code-review）
