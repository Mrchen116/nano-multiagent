# feat-485: Design review 轮次生命周期

> 状态：Completed。实现经 [PR #214](https://github.com/Mrchen116/nano-multiagent/pull/214) 合入
> `main`；本 unit 随后冻结为历史。

## Relations

- Related: feat-475

## 原始需求

> 最近有个unit引入了design reviewer到design到默认流程中，但是按照他跑，每次design reviewer返工完，都重新再新的subagent review这个成本太高了，太可接受了。你可以看看codex最近做梳理消息交互改进项的session，他跑了好几次review。你看看怎么能优化skill，让他更高效一些。给我你的分析

> 永远复用reviewer，然后reviewer来判断review-mode 路由是不是更合理？

> 以及design-review.md，是不是应该改为每轮都记录保留？这样也适合复盘

> 不，我觉得这样比较乱，还是得按轮次来，第一轮的问题放一起，第二轮的放一起，并且把每轮的时间写入时间也记录一下，复盘方便。而且agent读它改问题也方便

> ok，新建worktree开始改。主仓不要动，主仓在做其他修改

> .claude/skills/change-orchestrator/SKILL.md不需要检查design-review，撤掉对orchestrator的修改。
>
> 不用记录“sha256 与 byte length”，搞复杂了，agent足够聪明。
> 这个tests/contract/test_design_review_round_contract.py测试是干嘛的？

> 根本就是垃圾测试，难道所有文档都需要加这种测试？整个删掉

## 澄清记录

- Q1: 返工后的 design review 是换一个 reviewer，还是复用最初的 reviewer？
  A(原话): 永远复用reviewer，然后reviewer来判断review-mode 路由是不是更合理？
- Q2: `design-review.md` 的历史按问题生命周期还是按 review 轮次组织？
  A(原话): 不，我觉得这样比较乱，还是得按轮次来，第一轮的问题放一起，第二轮的放一起，并且把每轮的时间写入时间也记录一下，复盘方便。而且agent读它改问题也方便
- Q3: 本次修改是否可以直接在主仓工作区进行？
  A(原话): ok，新建worktree开始改。主仓不要动，主仓在做其他修改
- Q4: 是否由 orchestrator 再检查 design review，以及是否用 hash/字节数证明历史和产物一致？
  A(原话): .claude/skills/change-orchestrator/SKILL.md不需要检查design-review，撤掉对orchestrator的修改。不用记录“sha256 与 byte length”，搞复杂了，agent足够聪明。
- Q5: 是否保留精简版文档契约测试？
  A(原话): 根本就是垃圾测试，难道所有文档都需要加这种测试？整个删掉

## 用户场景

走 Full 变更流程的人在 design reviewer 报出问题后，会让 design-author 修订方案并再次送审。现有流程每轮都冷启动一个全新 reviewer，新的 reviewer 需要重新读取首文档、design、delta-spec、代码和上一轮已经核过的大量事实；在连续返工时，这部分重复取证成为主要时间和 token 成本。

目标状态是：一个 unit 的整个 Gate 2 审查闭环只创建一个独立 reviewer。它在第一轮建立完整上下文，后续由 design-author 唤醒复用。author 只交代本轮修订事实，不替 reviewer 选择检查深度；reviewer 根据真实影响选择 `closure`、`delta` 或 `full`，必要时自行升级。

同一个 `design-review.md` 按时间顺序保留全部轮次。每轮的问题、实际核实证据、结论和耗时放在自己的轮次块内，author 的逐条处理结果也紧邻该轮问题。这样下一轮 reviewer 能快速定位未闭合项，后续复盘也能看出每轮为什么发生、花了多久、解决了什么。

## 验收标准

### Requirement: 一个 Gate 2 闭环固定复用同一 reviewer

#### Scenario: 首轮建立独立 reviewer
- **GIVEN** design-author 已完成自身设计自检
- **WHEN** Gate 2 开始第一轮 design review
- **THEN** 用户看到 author 创建一个与 author 上下文隔离的 reviewer 实例
- **AND** 该实例成为这个 unit 后续 review 轮次的固定 reviewer

#### Scenario: 修订后再次送审
- **GIVEN** 固定 reviewer 已完成上一轮 review
- **AND** author 已处理上一轮问题并修订受审产物
- **WHEN** author 发起下一轮 review
- **THEN** 用户看到 author 唤醒同一个 reviewer 实例，而不是创建新的 reviewer
- **AND** reviewer 可以复用已经建立的 unit、代码和问题上下文

#### Scenario: 已有轮次后重新进入 design-author
- **GIVEN** `design-review.md` 已存在一个或多个 Round
- **WHEN** 用户在同一或新的任务中重新进入 design-author
- **THEN** author 先读取最后轮次和 reviewer 标识，从下一轮编号继续
- **AND** 不重新创建 reviewer、不再次写 Round 1

#### Scenario: 固定 reviewer 客观不可恢复
- **GIVEN** 原 reviewer 实例已不可用或上下文无法恢复
- **WHEN** Gate 2 仍需继续
- **THEN** 用户在下一轮记录中看到 reviewer 被替换的原因和新 reviewer 标识
- **AND** 替代 reviewer 的首轮检查使用 `full`，不假装继承原实例未保存的判断

### Requirement: Review mode 由 reviewer 按影响自主路由

#### Scenario: Author 提交返工结果
- **GIVEN** author 已处理完上一轮问题
- **WHEN** author 唤醒固定 reviewer
- **THEN** reviewer 收到本轮编号、受审产物、变更位置和 author 的问题处理记录
- **AND** author 不指定 `review_mode`、期望结论或要求只看某些问题

#### Scenario: Reviewer 选择检查深度
- **GIVEN** reviewer 已检查本轮修订的语义影响和可界定的波及范围
- **WHEN** reviewer 开始正式核实
- **THEN** reviewer 自主选择 `closure`、`delta` 或 `full`
- **AND** 本轮记录包含所选 mode 及其事实依据

#### Scenario: 轻量轮保留未失效的审查证据
- **GIVEN** reviewer 选择 `closure` 或 `delta`
- **WHEN** 本轮没有重新执行上一轮的某些核实项或架构进攻角度
- **THEN** 本轮简要说明其余检查继承自哪个 Round，以及为什么本轮变化未使其失效
- **AND** 不重复抄写上一轮完整台账或架构进攻

#### Scenario: 轻量检查发现影响扩大
- **GIVEN** reviewer 原计划执行 `closure` 或 `delta`
- **WHEN** 核实中发现新副作用、跨边界影响、无法界定的 delta 或新的阻断问题
- **THEN** reviewer 在同一轮自行升级检查范围，必要时升级到 `full`
- **AND** author 不能阻止该升级

### Requirement: Design review 报告按轮次保留完整历史

#### Scenario: 完成一轮 review
- **WHEN** reviewer 完成任意一轮检查
- **THEN** reviewer 在 `design-review.md` 末尾追加一个独立轮次块
- **AND** 不覆盖、重排或改写先前轮次的 reviewer 结论和问题

#### Scenario: 每轮问题独立成组
- **GIVEN** 某轮产生 CRITICAL、WARNING 或 Recommendation
- **WHEN** 人或 agent 阅读 `design-review.md`
- **THEN** 该轮实际执行的核实证据、问题和建议都位于同一个轮次块
- **AND** 每个问题有包含来源轮次的稳定 ID，后续轮次能逐条引用其关闭状态

#### Scenario: Author 处理一轮问题
- **GIVEN** reviewer 已落盘本轮问题
- **WHEN** author 判断并处理这些问题
- **THEN** author 在该轮下追加逐条 Resolution，记录采纳、驳回或升级给用户的结论、证据和改动位置
- **AND** author 不改写 reviewer 原始问题文本

#### Scenario: 记录 review 时间
- **WHEN** reviewer 开始并完成一轮检查
- **THEN** 该轮记录包含带时区的开始时间、完成时间和耗时
- **AND** 复盘者能区分等待、取证和返工发生在哪一轮

### Requirement: Gate 2 以最新轮次为准

#### Scenario: 最新轮次通过
- **GIVEN** 最新完成轮次为 `Approved` 且 `0 CRITICAL / 0 WARNING`
- **AND** author 确认没有仍值得修改的实质问题
- **AND** 该轮完成后没有再次修改受审产物
- **WHEN** design-author 结束审查闭环
- **THEN** Gate 2 可以通过
- **AND** 完整历史继续保留在同一个 `design-review.md`

#### Scenario: 最新轮次后受审产物再次变化
- **GIVEN** 最新轮次已经通过
- **WHEN** author 随后再次修改任一受审产物
- **THEN** 最新结论立即过期并新增下一轮 review
- **AND** 旧轮次仍保留为历史证据

### Requirement: 本次修改与主仓工作区隔离

#### Scenario: 在独立 worktree 实施
- **WHEN** 本 unit 的 skill 和流程文档被修改
- **THEN** 修改只出现在 `codex/design-review-round-history` worktree 分支
- **AND** 主仓工作区原有的已修改和未跟踪文件不被改写或纳入本 unit

## 范围与非目标

- 在范围:
  - `change-design-author` 的 reviewer 生命周期、返工派发和 Gate 2 判据。
  - `change-design-reviewer` 的 mode 路由、轮次格式、时间记录和追加写入契约。
  - `docs/changes/readme.md` 中 Gate 2 流程与 `design-review.md` 产物说明。
- 非目标:
  - 让 `change-orchestrator` 读取或校验 `design-review.md`。
  - 用 sha256、byte length 或完整产物 manifest 证明报告历史和受审产物一致。
  - 用字符串断言为 skill 或流程文档建立代码契约测试。
  - 改变 design reviewer 的核实维度、严重度定义或架构进攻标准。
  - 给 reviewer 写入 `design.md`、代码或其他受审产物的权限。
  - 定期轮换 reviewer；只有原实例客观不可恢复时才允许留痕替换。
  - 引入独立数据库或拆分成每轮一个报告文件。
  - 把主仓中其他任务尚未提交的 `docs/README.md`、`docs/development/` 等文件复制进本分支。
  - 修改产品运行时代码。
