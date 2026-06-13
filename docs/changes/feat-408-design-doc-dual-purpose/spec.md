# feat-408: design.md 双目的——可人审 + 无二义指导实施

> 备注：本 unit 改的是 SDD 流程工具本身（`change-design-author` skill），不是产品代码。
> 实现（SKILL.md / assets 模板 / 新增 references/diagrams.md）已随本次对话讨论落地，
> 本 spec 是对该需求的事后存档与验收基线（参照 feat-407 的同类 retroactive 模式）。

## Relations

- Related: feat-407（同属 change-* skill 的 SDD 流程改进；feat-407 防实现视角泄漏进契约层/测试，
  本 unit 提升 design.md 的可读性与双目的清晰度）

## 原始需求

> 现在本仓做sdd出现问题，我现在的 ./.claude/skills/change-design-author skill 我觉得他产生的 design
> 文档不好，不好读，一堆文字，很少图，让人很不直观看到变化了啥，增加了啥，架构啥咋样的。
> ~/Repos/opensource-hub/superpowers/ ~/Repos/opensource-hub/OpenSpec/，他们都有 design 环节，
> 他们怎么呈现的，你帮我学习下。

本次（retroactive）触发：

> ok，我微调了下，现在已经都 git add 了，帮我回顾性补个 spec，一并提交

## 澄清记录

- Q1: design 呈现方向——要不要走 delta（OpenSpec 式 ADDED/MODIFIED/REMOVED）？
  A(原话): 「这都不好，我不希望 design 是个 delta，他应该就是针对本需求的设计。一般人类做设计会画哪些图？」
  Agent 解读: design 不做成 diff 语义，而是针对本需求的自洽设计；改善可读性靠「按需求难点选图」，
  不靠 delta 表达。

- Q2: 画哪几张图，要不要跟用户确认？
  A(原话): 「画什么图不需要跟用户确认，直接画就行」
  Agent 解读: 选图是 skill 的技术判断，直接画；只在画完确认架构大方向，不就「画哪张」征询用户。

- Q3: 「先识别难点再选图」的具体目录/骨架放哪？
  A(原话): 「你说的很对，应该让 skill 先识别本需求的难点类型，据此决定画哪几张图。这些具体信息应该放在
  reference 文档中？然后 skill 中引用？」
  Agent 解读: 选图速查表 + 各类图的本项目 mermaid 骨架放 `references/diagrams.md`，SKILL.md 正文只留
  决策机制并引用它（progressive disclosure）。

- Q4: skill 整体偏长，压缩哪里？
  A(原话): 「现在整体 skill 过长了，你分析下，哪些地方可以压缩」「ok，先做 1+2」
  Agent 解读: 删整段「§7 反 anti-pattern」（与 §0 硬规则正反重复，零信息损失）、压 §0.2 长括注、风险
  空话例子并入 §3.4。

- Q5: design skill 有没有讲清 design.md 的目的？
  A(原话): 「当前 design skill 有没有讲清楚。这个 design 输出有两个目的，一个是给人看，来审核设计的
  合理性，所以要容易看得懂，一个是给后续的 agent 明确的指导开发，后要有二义性，模糊性」
  Agent 解读: skill 原先只讲「给 worker 实施」，吞掉了「给人审核要可略读」；两目的有张力，需在开篇显式
  点破 + 用「文档分层」化解。

- Q6: 强调条款的写法？
  A(原话): 「太长了，没必要写这么长去强调，这只是个小问题」（针对 Changelog 卫生一段）
  Agent 解读: 小问题用一句话约束即可，不堆长段强调。

## §3.0 grounding（事后记录）

- 现状：`change-design-author/SKILL.md` 原 §3.1 仅泛泛「画一张图」、无「何时画/画哪张」判据；开篇产物
  定义只写「让 worker 看完就能动手实施」，未提「给人审核」目的；§3.2 决策模板结论与取证混写；Changelog
  无「design 阶段留空」约束。真实样本 `refactor-406` 的 design.md 印证问题：图到位但 Changelog 堆了
  v2→v9 自我纠错史、决策段是密集散文。
- 参考：superpowers 的可读性来自 brainstorming `visual-companion`（按「see vs read」逐问判断是否可视化）
  + design 文档用命名 Design Principles 与 condition→action 决策表；OpenSpec 靠「拆 4 文档 + design.md
  可选且短」。两者都不靠堆 mermaid——共同点是「该可视化的可视化、决策用表/命名原则压缩散文」。

## 用户场景

作为 SDD 流程的 owner，希望未来跑 `change-design-author` 产出的 design.md 同时满足两个目的、不再是
「一堆文字、很少图、看不出变了啥」：

- 人打开它审核设计合理性时，**几分钟能读懂骨架**判断方向——架构总览有图，每条关键决策第一行就是一句话
  结论，不必逐字读完细节。
- worker 拿它实施时，**精确细节无二义**——接口、字段、退出标准、delta-spec 完整保留在文档下层，不因
  「求简」被删。
- 配图**按本需求的难点来选**：默认打底一张静态结构图 + 一张主流程时序图，再按最尖锐难点（状态/数据/
  分支）决定是否加一张专门图；不是六类全画，也不是无图。选图由 skill 直接判断并画，不就「画哪张」征询
  用户。
- 关键决策段**结论上浮、取证下沉**：第一行 bold 结论给人扫，grounding 佐证归 §现状分析，不内联进决策
  把上层淹没。
- Changelog 在 design 阶段**留空**：对齐期推翻重来直接原地重写，不记成自我纠错流水账。

结果：design.md 成为「上层给人审核可略读、下层给 agent 实施无二义」的分层文档，而非精确但没人能 review
的文字墙。

## 验收标准

### Requirement: design.md 双目的在 skill 中被显式定义

#### Scenario: skill 开篇点破双目的与张力
- **WHEN** 读 `change-design-author` 的 SKILL.md 开篇
- **THEN** 明确写出两类读者/两个目的（给人审核要可略读、给 agent 实施要无二义）、它们的张力，以及用
  「文档分层」化解的原则，而非只讲「给 worker 实施」

### Requirement: 配图按需求难点选，不堆砌也不缺位

#### Scenario: 默认打底 + 按难点加专门图
- **WHEN** design-author 为一个 unit 配图
- **THEN** 默认产出静态结构图 + 主流程时序图，并按本需求最尖锐难点决定是否再加一张专门图（状态机/数据
  模型/流程图），既不是六类全画也不是无图

#### Scenario: 画哪张图不征询用户
- **WHEN** design-author 选定画哪几张图
- **THEN** 直接画，不就「画哪张」问用户；仅在画完确认架构大方向（有无遗漏的子系统/接入点）

### Requirement: 决策段结论上浮、取证下沉

#### Scenario: 一条关键决策的写法
- **WHEN** design-author 写一条关键决策
- **THEN** 第一行是 bold 的一句话结论（人扫这行即懂选了啥），理由/拒绝/风险在下；grounding 取证不内联，
  归 §现状分析

### Requirement: Changelog 在 design 阶段留空

#### Scenario: 对齐期推翻重来
- **WHEN** design 阶段与用户来回对齐、推翻方案
- **THEN** 直接在对应段落原地重写，Changelog 全程留空，只留给 orchestrator 接手后的实施期偏差

### Requirement: 选图细节沉到 reference，正文不膨胀

#### Scenario: 选图速查与骨架的家
- **WHEN** 需要「难点→画哪张图」的映射或某类图的本项目 mermaid 骨架
- **THEN** 它们在 `references/diagrams.md`，SKILL.md 正文只留选图决策机制并指向该文件

## 范围与非目标

- 在范围：`change-design-author` 的 SKILL.md（开篇双目的+分层、§3.1 难点选图、§3.2 决策结论上浮/取证
  下沉、§2 Changelog 留空、删 §7 反 anti-pattern 压缩）、`assets/design.md` 模板对应注释、新增
  `references/diagrams.md`。
- 非目标：
  - 不动其他 change-* skill（spec-author / orchestrator / worker / reviewer / verifier）。
  - 不回溯重写已产出的 design.md（如 refactor-406）——只规范未来产出。
  - 不引入机械校验（不卡 design.md 格式 / 图数量），靠 agent 遵守 + 人审。
  - 不照搬 superpowers 的浏览器可视化 server（重型、跨 harness），只取「按难点判断该不该图」的判据。
