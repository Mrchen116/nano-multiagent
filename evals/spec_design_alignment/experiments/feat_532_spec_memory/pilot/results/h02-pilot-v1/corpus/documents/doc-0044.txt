# feat-475: Design Author 独立审查闭环

> 状态：Completed。行为由提交 `206609a62` 进入 `main`，随后被 feat-485 的 reviewer 复用与轮次生命周期
> 规则显式修订；本文件随 unit 冻结为历史。

> 回顾性 spec：本 unit 的行为边界先在对话中完成对齐，随后修改
> `change-design-author/SKILL.md`；本文档按用户要求补记这项特殊需求，并与 skill 修改一同提交。

## Relations

- Related: feat-411
- Related: feat-432

## 原始需求

> 当前change-design-author skill没有写用design reviewer skill开个subagent做独立审查，审查完自己判断对应问题是否真实，进行loop改进到没问题为止。我想加上。
>
> 明白吗，先不做，跟我对齐。

> 唯一需要你拍板的边界这个问题，你说的对，按你建议的。
>
> 你理解清楚了开始改吧

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 改完之后，补一个spec文档，因为这本身也是一个特殊的需求。然后spec和你的修改一同commit

> [$skill-creator](/Users/czj/.codex/skills/.system/skill-creator/SKILL.md) description的作用是触发skill，你不用改他啊。

> ## §0 不可越界的硬规则 不用强调这个，这个肯定是遵从性很好的。不用反复强调的

> 你有没有发现，我原本skill中没出现过“作者”这个词，你不停用。

## 澄清记录

- Q1: 如果 reviewer 的真实问题会推翻一个已经由用户确认的关键架构决策，author 应该自主修改，还是重新找用户对齐？
  A(原话): 唯一需要你拍板的边界这个问题，你说的对，按你建议的。
  Agent 解读: 事实纠错、遗漏补齐、自洽性和接口闭合等问题由 author 自主修订并循环复审；若修复会推翻用户已经确认的关键架构决策，则必须重新找用户拍板。

## 用户场景

走 change-* SDD 流程的人用 `change-design-author` 完成架构对齐后，当前流程只有同一上下文里的整体自检，可以直接宣布门禁 2 通过；要获得独立视角，仍依赖用户另行要求调用 `change-design-reviewer`。这会让写设计时的思维惯性继续留在设计里，也会把“拿 review 报告回来、判断问题真假、修改、再复审”的协调工作交给用户。

目标状态是：author 自检通过后自动启动独立的 design reviewer subagent，等待它完成全量核实台账和架构进攻。author 不盲从报告，而是回到首文档、长青契约和真实代码逐条判断问题是否成立；真实问题自主修正，误报不为了迎合报告而修改。修改后由新的独立 reviewer 从头全量复审，循环到最新报告通过且 author 自己也认为没有实质问题。

常规 review findings 不打断用户。只有当真实问题的修法会推翻用户已确认的关键架构决策，或需要改变首文档中的用户场景、验收标准、范围时，design-author 才把决定交回用户。最终用户能看到一份与当前设计一致的最新 `design-review.md`，并确信门禁 2 经历了真正独立的复核。

## 验收标准

> 本 unit 的“产品”是 `change-design-author` skill；“用户可观察”是用户运行该 skill 时看到的
> subagent 调度、交互边界、门禁结论与落盘报告。

### Requirement: 门禁 2 前自动发起独立设计审查

#### Scenario: Author 自检通过后进入独立审查
- **GIVEN** design、Milestone、delta-spec 与其他受审产物已经完成自检
- **WHEN** `change-design-author` 准备宣布门禁 2 通过
- **THEN** 用户看到 author 先启动一个执行 `change-design-reviewer` 的独立 subagent
- **AND** 在完整独立报告返回前不会宣布门禁 2 通过

#### Scenario: 当前环境不能提供独立上下文
- **GIVEN** 当前 harness 不能启动 subagent，或不能隔离当前 design 对齐上下文
- **WHEN** author 准备送审
- **THEN** 用户被明确告知门禁 2 因缺少独立审查上下文而阻断
- **AND** author 不会把自己的再次自检冒充成独立审查

### Requirement: 每轮 review 保持独立且完整

#### Scenario: 修改后的设计重新全量复审
- **GIVEN** author 根据上一轮真实 findings 修改了任一受审产物
- **WHEN** author 重新送审
- **THEN** 用户看到一个新的独立 reviewer 从首文档、设计、契约与真实代码重新完成全量审查
- **AND** reviewer 不只复查上一轮问题，也不继承 design-author 的预设结论

#### Scenario: Reviewer 尚未完成
- **GIVEN** 独立 reviewer 正在构建核实台账或执行架构进攻
- **WHEN** author 等待审查结果
- **THEN** 受审设计保持冻结
- **AND** 用户不会收到用快速印象替代完整报告的门禁结论

### Requirement: Author 对 findings 独立判真并自主闭环

#### Scenario: Finding 真实且不改变已确认的关键决策
- **GIVEN** reviewer 报告中的问题经 author 对首文档、契约和真实代码核实后成立
- **AND** 修复不需要推翻用户已确认的关键架构决策
- **WHEN** author 处理该 finding
- **THEN** author 自主修正所有受影响的设计产物并重新自检
- **AND** author 启动新的独立 reviewer 全量复审，而不是把常规修订交回用户

#### Scenario: Finding 是误报或口味偏好
- **GIVEN** author 取证后确认某条 finding 不成立、证据不足或没有下游后果
- **WHEN** author 处理该 finding
- **THEN** 设计不会为了迎合报告而被修改
- **AND** author 仍以新的独立全量审查取得最新门禁结论

#### Scenario: Recommendation 揭示实质改进
- **GIVEN** reviewer 的 Recommendation 经 author 判断会实质改善方案
- **WHEN** author 审阅报告
- **THEN** 该 Recommendation 按真实问题进入修订和复审闭环

### Requirement: 推翻用户关键决策时重新对齐

#### Scenario: 修复需要改变已确认的关键架构决策
- **GIVEN** reviewer 的真实问题只能通过推翻用户已确认的关键架构决策来解决
- **WHEN** author 确认该影响
- **THEN** 用户收到事实、具体后果和推荐方案，并重新拍板
- **AND** author 在用户确认前不静默改写该关键决策

#### Scenario: Review 暴露需求边界需要变化
- **GIVEN** reviewer 的真实问题需要改变首文档中的用户场景、验收标准或范围
- **WHEN** author 确认问题属于需求层
- **THEN** 用户被明确引导回 `change-spec-author`
- **AND** 需求变化不会被静默塞进 design

### Requirement: 最新无问题报告才允许门禁 2 通过

#### Scenario: 独立审查闭环完成
- **GIVEN** 最新 `design-review.md` 结论为 `Approved` 且没有 CRITICAL 或 WARNING
- **AND** author 已逐条核实台账、架构进攻和 Recommendations，确认没有仍值得修改的实质问题
- **WHEN** author 准备结束 design 阶段
- **THEN** 用户收到“已通过独立 design review 闭环，门禁 2 通过”的明确结论
- **AND** 最终报告与之后未再变化的受审产物一同成为下游输入

#### Scenario: 最终 review 后设计再次变化
- **GIVEN** 最新 review 已经通过
- **WHEN** design、delta-spec、prototype 或 Milestone 骨架随后又发生变化
- **THEN** 原报告被视为过期
- **AND** author 必须重新启动独立全量审查，不能沿用旧结论

### Requirement: 需求记录与行为修改同一提交

#### Scenario: 本次特殊需求提交
- **WHEN** 本 unit 的修改准备提交
- **THEN** 用户在同一个 commit 中看到本 spec 与 `change-design-author/SKILL.md` 的闭环修改
- **AND** 工作区里与本 unit 无关的既有改动不进入该 commit

## 范围与非目标

- 在范围:
  - `change-design-author` 在自身自检与门禁 2 之间强制调度独立 `change-design-reviewer` subagent。
  - design-author 逐条判真、修订、自检、换新 reviewer 全量复审，直到最新报告和自身判断都无实质问题。
  - 推翻用户已确认的关键架构决策时重新对齐；其他常规 findings 自主闭环。
  - 最新完整 `design-review.md` 成为门禁 2 的正式产物。
  - 本 spec 与 skill 修改一同提交。
- 非目标:
  - 修改 `change-design-reviewer` 的检查维度、严重度或报告格式。
  - 修改 `change-orchestrator`、`change-reviewer` 或 `change-spec-reviewer` 的既有路由。
  - 给没有独立 design 阶段的 bugfix lite 增加 design review。
  - 保存每轮 review 的额外台账或历史报告；固定路径只保留最新完整报告。
  - 改变 design 初稿阶段“一次一个问题”的用户对齐方式。
