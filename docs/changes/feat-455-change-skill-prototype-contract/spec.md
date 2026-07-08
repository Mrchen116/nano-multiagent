# feat-455: change skill prototype contract

## Relations

- Related: feat-343
- Related: feat-344
- Related: feat-446
- Related: refactor-435

## 原始需求

> 你是不是能看过去两周的聊天记录中，哪些是做unit-feat-446的设计和实现的。我用的.agents/skills/change-orchestrator/SKILL.md skill进行开发，为什么他的前端设计完全没有按照原型图来，帮我审视对应的日志和相关skill、unit落盘的文档，分析这到底是哪一步出现的问题

> 不是看claude的历史！是codex的历史

> 所以你看change-* 系列skill中哪些需要改，具体改啥，给我列一下

> 好，你开始修改。但是请克制点，不要做无关修改

> 还有一个问题，现在做design的时候，经常出现原型图不参照现有产品的UX设计，完全不匹配当前的UX，导致实现的时候agent只能参照自己的理解融入进去。比如，现在是在IM消息气泡加一个已读功能，他设计的时候压根没看当前气泡的设计，导致原型设计完全不契合现有的UX。我不希望这样，我希望原型设计，就是最终用户体验的。懂我意思吗？

> 设计这一步给原型图，就是类似人类的PM给开发的原型图。是直接指导开发的。

> 开始改change-design-author

> 已查看证据我感觉不需要

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 改skill本身也是个需求，回顾性增加一个spec。然后一起提pr

## 澄清记录

- Q1: 这个变更的范围是只补 `change-design-author`，还是要覆盖 feat-446 暴露出的整条 change-* 前端原型验收链路？
  A(原话): 好，你开始修改。但是请克制点，不要做无关修改
  Agent 解读: 范围应限制在 feat-446 暴露出的直接失守链路：design-author / orchestrator / impl-worker / reviewer / verifier 以及这些 skill 已有模板，不顺手重构其它 skill。

- Q2: `prototype.html` 在流程中的定位是视觉参考，还是直接指导开发的交互原型？
  A(原话): 设计这一步给原型图，就是类似人类的PM给开发的原型图。是直接指导开发的。
  Agent 解读: 原型不是灵感稿或 moodboard，而是实现契约；worker 和 reviewer 都应把它当作真实产品体验目标。

- Q3: design 阶段是否需要把当前产品 UX 的取证路径写进文档？
  A(原话): 已查看证据我感觉不需要
  Agent 解读: 设计阶段仍必须先看当前 UX，但 design.md 只落结论，不写取证流水；保留当前入口、必须继承的 UX 特征、本次增量如何嵌入。

## 用户场景

用户使用 change-* SDD 流程开发前端相关 unit 时，期望 `prototype.html` 像人类 PM / 设计师交给开发的原型图一样，直接指导最终用户体验。设计阶段应先理解当前产品已有 UX，再在现有页面、组件、信息层级和交互模式上做增量原型。实现阶段不应被迫在“照原型做会破坏现有 UX”和“融入现有 UX 会偏离原型”之间自行猜测。

当 unit 的设计文档引用了原型、设计稿、截图或视觉一致性要求时，后续 worker、reviewer、verifier 和 orchestrator 都应能看到同一份原型契约：哪些结构/交互必须一致，哪些可以按现有 design system 调整，哪些只是占位或非目标。原型对齐证据应落在 unit 文档中，不能只保存在临时目录或口头报告里。

这个变更是对已完成 skill 修改的回顾性补档。它不改变产品运行时行为，但会改变后续使用 change-* skill 时用户能获得的流程结果：前端原型更贴近当前产品，原型要求能被 worker 执行、被 reviewer 验收、被 verifier 和 orchestrator 门禁检查。

## 验收标准

### Requirement: 前端原型必须基于当前产品 UX

#### Scenario: design-author 产出前端原型
- **WHEN** 一个前端相关 unit 进入 design 阶段
- **THEN** design-author 的 skill 说明要求先做现有 UX grounding，再产出 `prototype.html`
- **AND** design 模板要求记录当前产品入口 / 组件、必须继承的 UX 特征、本次增量如何嵌入

#### Scenario: 原型想改变既有 UX
- **WHEN** 前端原型需要改变现有页面、组件或交互模式
- **THEN** design-author 的 skill 说明要求把该变化升级为显式 design 决策和 milestone 验收项
- **AND** 不能把 UX 迁移留给 worker 在实现阶段自行调和

### Requirement: 原型是实现和验收契约

#### Scenario: design 文档引用 prototype.html
- **WHEN** `design.md` 含 `## 前端原型`
- **THEN** design-author 的 skill 和模板要求写出原型对齐契约
- **AND** 每个必须对齐的原型区域能被下游映射到 milestone 退出标准

#### Scenario: worker 完成前端原型相关 milestone
- **WHEN** worker 回报涉及前端原型或 reference 的 milestone 完成
- **THEN** worker 的 skill 和模板要求留下真实浏览器证据和逐项原型对照结论
- **AND** 证据应落在 unit 目录或其它可复查位置，而不是只写临时路径

#### Scenario: reviewer 验收原型相关 unit
- **WHEN** reviewer 验收引用原型、设计稿、reference screenshot 或视觉一致性要求的 unit
- **THEN** reviewer 的 skill 和验收模板要求列出 reference artifact、实际产品证据和对照结论
- **AND** 页面元素存在、功能可用、API 成功不能替代原型对照

### Requirement: 门禁能拦住缺失的原型对照证据

#### Scenario: orchestrator 签收 worker DONE
- **WHEN** worker 回报前端原型相关 milestone 为 DONE
- **THEN** orchestrator 的 skill 说明要求检查 `progress.md` 中是否有原型对照表和 durable evidence
- **AND** 缺少逐项对照或只给临时证据时不能签收该 DONE

#### Scenario: verifier 核对 unit 实现
- **WHEN** verifier 发现 `design.md` 有前端原型或 reference artifact
- **THEN** verifier 的 skill 和模板要求核对原型契约是否投影到 milestone、tasks/progress/acceptance 是否有证据链
- **AND** verifier 只核 explicit contract 与证据链，不把自己变成主观视觉 reviewer

## 范围与非目标

- 在范围：
  - 补充回顾性 `feat-455` 首文档。
  - 更新 change-design-author，让原型必须基于当前产品 UX，并让 design.md 落现有 UX grounding 结论。
  - 更新 change-design-author / change-orchestrator / change-impl-worker / change-reviewer / change-verifier 的原型契约、证据和门禁说明。
  - 更新相关 skill 的已有模板，使后续文档自然产出原型对齐契约、Prototype Comparison、Reference Artifacts Reviewed 和 verifier 证据链。
- 非目标：
  - 不重写 feat-446 的实现或验收报告。
  - 不改变 IM 前端产品代码。
  - 不重构 change-* skill 的整体职责边界。
  - 不要求 design.md 记录现有 UX 的取证路径或截图流水；只记录 UX 结论。
