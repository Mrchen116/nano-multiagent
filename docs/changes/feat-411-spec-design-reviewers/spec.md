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
| **新增（本体系独有）** | spec：用户可观察红线、澄清原话保真、Requirement/Scenario 结构合规、失败/边界/空态覆盖、grounding 痕迹、bugfix RCA 深度；design：现状分析/契约层 grounding、关键决策完整/拍死/无歧义、符合本 unit spec 全部约束、接口数据流闭合、delta-spec 覆盖、两轨退出标准（[reviewer]/[worker]）、Milestone 反横切拆分、给人审核那层是否直观、方案最优性/非临时凑合（Runbook 已降为常规项） | superpowers 一条都没有——它们对应本项目 spec/design 体系的核心失败模式，是这两个 skill 真正的价值所在。逐条维度写在各自 design.md。 |

一处刻意的非对称（不是疏漏）：**YAGNI / 过度设计在 spec-reviewer 不查、在 design-reviewer 要查**。因为本项目把实现从 spec 剥离了——spec 里没有实现可供评判是否过度，而 design 里「找不到 spec 驱动的决策」正是过度设计的信号。这正是体系拆两份文档的直接结果。

## 落地迭代：据使用反馈新增的要求

两个 skill 落地后，用户在实际打磨中陆续提了新要求，逐条迭代进 skill（尤其 design-reviewer）。关键**原话原样保留**如下，作为这些维度的来源依据（区别于上方「澄清记录」——那是动手前的对齐，这里是落地后的迭代）：

1. **通用性（skill 不焊死本仓架构）**
   > 我的 skill 是通用 skill。
   > 「kernel 视角翻译…」这个描述仅针对本仓。

   → design-reviewer 去掉 kernel / agent.sdk / im / gateway / cli / core / AGENTS.md 等本仓专有名词，泛化为「包 / 模块」「项目既定分层规则」「代码消费者（库 / SDK）」。

2. **反过度强调、守住天平（别因强调"design 不含实现细节"而漏报真缺陷）**
   > 我觉得 …… 写的过于强调"没有代码、没有 step、milestone 目录里没有 tasks.md"这个了。你太过于强调呢，就会导致计划的不细，有歧义，关键设计缺失等问题被漏掉。
   > 也需要有少量的话，来强调两者的天平，不能放过"设计本身太粗"。

   → 砍掉各处重复的反误报强调；在「不要报什么」末尾加一句天平：缺实现细节→不报，缺该拍的决策 / 契约 / 边界→报。

3. **给人直观理解（design 第一目的）**
   > #### 7. Runbook…、#### 8. 双目的分层… 这都不是很重点。对于双目分层，更重点的可能是，到底有没有给人直观的理解。

   → Runbook 降为常规项；双目的分层重构成「给人的那层够不够直观」，头号症状＝没有把方案串起来的整体思路、人看不懂没法 review 方向。

4. **design 常见失败模式（新增三类核心维度的来源）**
   > 设计总是遇到的问题是，方案不是架构最合理的；只是临时方案，不是长远方案；和 spec 要求不一致；前后矛盾，或者和代码、长青 spec 矛盾、不够细节，导致 worker 有歧义，自由发挥。

   → 对照补齐：和代码 / 长青 spec 矛盾（§1）、前后矛盾（§2）、不够细节致歧义（§2 强化）、和 spec 不一致（§3 新增）、非最优 & 临时方案（§9 新增）。

5. **「和 spec 不一致」要写得宽**
   > 符合该 unit 的 spec 要求，因为 unit 的 spec 中不单单包含 requirement。

   → §3 写成「符合本 unit 首文档全部约束」，显式覆盖【用户场景】【澄清记录】【范围与非目标】，不只【验收标准 / Requirement】。

6. **设计品味维度用 WARNING、信任 agent**
   > 这是设计品味问题，需要 WARNING，不用太担心误报。design agent 有自己的判断力。

   → §9（最优性 / 临时凑合）统一报 WARNING，不做"绑死证据 / 降级"的防误报处理。

7. **真实使用后的结构性返工：逐条核 + 台账，杜绝"做做样子"**（首次实跑 design-reviewer 于 bugfix-417，效果不如预期后提出）

   **用户的要求（原话保真）**：
   > 他上来就"这份 design 写得相当扎实"…… 完全没有认真分析整个设计是真正严谨，是否真正符合整个项目的架构，是否真正合理。
   > 他压根就没有真正严谨的充当 reviewer 一个个现状和设计去分析。
   > （正面例子指向 change-code-review）他每次是真的能去找问题，并找到问题的。我不是说要学用 subagent，而说是，至少是要严格把要 review 的内容扎实去 review，而不是做做样子。
   > （改造约束）不要完全照抄 code review 的逻辑，要合理思考是否适用。

   **复盘（取证：session `82abcdde-6dd3-436b-a85f-1e7a4c4fd51f`）**

   *事故现象*：design-reviewer 第一轮（R1）读完 design 第一句就是「这份 design 写得相当扎实」，随后动作是「抽查几处关键 grounding 断言，确认 worker 不会被带偏」——**抽查，然后定调"扎实"**，结论 0 CRITICAL / 1 WARNING。真正让整个 C 层（M2）+ B 层 bash 心跳（M3）报废、逼出事后追加 M4 重构的架构缺陷，R1 一个字没碰；R2–R3 找到的 CRITICAL 全在 delta-spec 记账（ADDED/MODIFIED、Req 覆盖）那一档；致命缺陷直到**实现阶段验收 FAIL** 才被撞出，导致"实现完发现新问题→design author 又改设计"。

   *缺陷当时就可见*：被审的 R1 原版 design.md（commit `0b41a86a`）现状分析表第 21 行写「`bash_runner.py` 是 bash 执行引擎，C 主改」，整个 C 层建在这条前提上。但生产经 `build_kernel → wiring.py:61 = ShellRunner` 跑的是 `shell_runner.py`，`bash_runner.py` 是 `wiring is None` 才走的**死路（仅单测命中）**。R1 的「grounding 核实」核的是"`bash_runner.py:80` 那个 Popen 在不在"——**行号全对、断言全真、文件全错**。reviewer 在第四轮（实现后）自己 5 分钟就从 `wiring.py:61` 追出真相；这条追踪 R1 完全做得到，wiring 当时就在仓里。

   *结构性根因（这才是要改的）*：病根不是"维度不够"，而是 skill 的**形**允许偷懒。原 skill 给的是一张「检查维度」清单——描述**要嗅的品质**（"现状扎实吗""决策拍死了吗"），不是**要逐条执行的动作**，于是 reviewer 天然可以"抽查几处 + 凭印象给整体结论"。更致命的是**输出无 proof-of-work**：报告只要 Issues，于是「认真核过 8 个决策确认没问题」和「扫一眼感觉不错」产出**长得一模一样**（都是 Approved 或几条小 WARNING），skill 没有任何机制区分这两者，也就没有任何压力逼 reviewer 选前者——"做做样子"在结构上既隐形又被"少报为佳"的基调奖励。对照 change-code-review：它把审定义成**逐 hunk / 逐行 / 逐函数的强制遍历 + 每条候选必带 file/line/failure_scenario 的留痕**，没真走遍就交不出东西，"做做样子"被结构挡死。

   **改造（只移植治本纪律，不照抄机制）**：
   - ① 两个 skill 重构成三步：**建台账（枚举承重原子）→ 逐条核（每条一个具体动作）→ 记证据（引你追到的 `文件:行` 或文档原句，不是打勾——打勾本身又是做做样子）**。原散在各处的检查维度全折进"对每条原子该做什么"。
   - ② **台账即便结论是 Approved 也必须随结论交出**——这是让"认真核过"和"扫一眼"产出不同东西的反"做做样子"机制，正面对治"输出无 proof-of-work"这个结构根因。
   - ③ **合理裁剪不适用的部分**（"是否适用"的落点）：不抄 subagent fan-out / 7 角度 / ≤8 条 / 投票（用户明示不学 subagent，且那是代码 diff 的降噪机制，与 design/spec 已有的 CRITICAL/WARNING + Approved 契约重复）；**design-reviewer 追代码**——承重动作含「从入口/wiring 正向追实际路径，核现状前提在生产是否成立」（直击本次漏判）；而 **spec-reviewer 显式不追代码**——spec 是实现前纯用户视角文档、无代码可追，核实动作是文档内对齐 + 引用户原话。同一套纪律在两个 skill 上的这处分叉，就是"合理思考是否适用"而非照搬的体现。

   对应参考源：本条新增的「逐条核 + 留痕」纪律**继承自 `change-code-review` 的强制遍历结构**（继承骨架，非照搬其 subagent/投票机制）——这是继 superpowers 之后本 unit 的第二个评审骨架参考源。

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

#### Scenario: delta-spec 缺失
- **WHEN** design 有对外行为变化的包却没产 delta-spec
- **THEN** reviewer 报 CRITICAL，说明收尾无法对账（动了常驻服务却没写可照搬 Runbook 属常规项，报 WARNING，不再单列致命）

#### Scenario: 偏离本 unit spec 的要求 / 范围
- **WHEN** design 漏覆盖 spec 的某条 Requirement / 用户场景、或决策与 spec 要求或【澄清记录】里用户拍板的意图相抵、或做了 spec 列为【非目标】的东西
- **THEN** reviewer 报 CRITICAL（越界夹带按程度），点出与 spec 哪一处冲突 / 漏覆盖

#### Scenario: 关键决策悬而未决或有歧义
- **WHEN** design 的关键决策停在「待定 / 看情况」、本该拍的板缺位、或边界 / 接口含糊到两个 worker 会建出不兼容的东西
- **THEN** reviewer 报 CRITICAL，指出 worker 会被迫猜、不同的猜导致不同架构

#### Scenario: 方案非最优 / 临时凑合（设计品味）
- **WHEN** design 选了明显绕路 / 重复造轮子 / 不沿用既有模式，或是 hardcode、绕过抽象、留债无计划的临时方案
- **THEN** reviewer 报 WARNING，点出更优走法或长远代价（品味判断，放手提、不过度防误报）

### Requirement: 不误报「故意下沉 / 分层」的内容

#### Scenario: design 无代码无 step 不报
- **GIVEN** 一份合格的 design.md 不含实现代码、不含逐步 task、milestone 目录为空
- **WHEN** 用户调 `change-design-reviewer`
- **THEN** 它**不**把这些报成「不完整 / 缺步骤 / 没法照着做」——识别这是设计本身

#### Scenario: spec 无技术方案不报
- **GIVEN** 一份合格的 spec.md 不含模块划分、接口签名、选型
- **WHEN** 用户调 `change-spec-reviewer`
- **THEN** 它**不**报「缺技术方案 / 缺实现」，也不对 spec 评判 YAGNI/过度工程

#### Scenario: 但「设计本身太粗」不被豁免（天平另一端）
- **GIVEN** design 缺的是该拍的决策 / 契约 / 边界（而非实现细节）
- **WHEN** 用户调 `change-design-reviewer`
- **THEN** 它**照常报**，不因「不误报故意下沉」而放过——界线：缺实现细节→不报，缺设计决策→报

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
  - 两个 skill 保持**通用**：只依赖 change-* 方法论概念，不焊死本仓具体架构名词（包名 / SDK / 分层名），可随这套 SDD 流程复用到别的仓

- **非目标**：
  - **不改造 author skill**（change-spec-author / change-design-author）让其在收尾自动派发 reviewer——保持最小侵入，是否接入由用户后续决定
  - **不跑量化 eval**——评审类 skill 输出主观，量化 benchmark 价值低；验证靠拿真实文档试跑
  - **不审代码 / 不走产品旅程 / 不替作者改文档**——这些分别归 change-verifier / change-reviewer / 作者本人，本 unit 不重叠
  - **不覆盖 bugfix lite 的 fix.md**——lite 无独立 design 阶段，design-reviewer 不适用；fix.md 的 spec 部分由 spec-reviewer 的 bugfix 维度兜（按需）
