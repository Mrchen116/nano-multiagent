# feat-457: 引入通用架构巡检与深模块设计能力

## Relations

- Related: feat-432

## 原始需求

> 我定期会用.claude/skills/improve-codebase-architecture/SKILL.md 这个skill扫描这个代码仓，但是现在是不是还没有目录承载这些报告

> 以很好，我同意，这个skill是我从别的地方拷过来的，还有啥不适配的地方没

> 这个skill是从这个/Users/czj/Repos/opensource-hub/mattpocock-skills来的，我是觉得我需要这么一个定期审视架构的环节，所以不一定和我现在的适配。也可能还需要引入他的一些skill。帮我审视我的skill体系，和他的skill体系，给我一个引入他的这个能力的方案，给我审视下

> 我觉得不用大规模重写improve-codebase-architecture，和当前skill体系不兼容的地方改掉就行了。特别是不用适配本仓库，我要的是通用的一组skill。“只扫描 git ls-files，排除 .worktrees、node_modules、.venv、运行时状态和生成物。”，这种也是搞笑的，原本人家skill能跑，我的仓在这方面没有特殊性，根本不必改。引入codebase-design我认同，整个大流程设计我也认同，就是design-author阶段按场景需求调用codebase-design。“candidates.md：稳定候选 ID 与状态。”搞这么复杂干嘛，每次独立审视就行了。审视完存一份，后续也知道这份分析是哪个commit id就ok了。
>
> 理解我说啥，重新给一份方案。

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 这本身也是个需求，现在对齐完成了。我同意现在的。你开始写spec吧

## 澄清记录

- Q1: 定期架构审视报告是否需要落入仓库，形成可追溯的历史产物？
  A(原话): 以很好，我同意，这个skill是我从别的地方拷过来的，还有啥不适配的地方没
  Agent 解读: 用户确认需要为定期架构审视提供仓库内的报告落点，同时要求继续检查外来 skill 的能力依赖与流程兼容性。

- Q2: 应该把 Matt Pocock 的整套工程 skill 流程引入，还是只引入定期架构审视所需的能力？
  A(原话): 这个skill是从这个/Users/czj/Repos/opensource-hub/mattpocock-skills来的，我是觉得我需要这么一个定期审视架构的环节，所以不一定和我现在的适配。也可能还需要引入他的一些skill。帮我审视我的skill体系，和他的skill体系，给我一个引入他的这个能力的方案，给我审视下
  Agent 解读: 目标是补上“定期审视架构”这一能力缺口；是否引入相邻 skill 应按能力依赖判断，而不是默认整体搬运 Matt 的流程。

- Q3: `improve-codebase-architecture` 应做仓库专项重写，还是维持通用能力并只修兼容点？
  A(原话): 我觉得不用大规模重写improve-codebase-architecture，和当前skill体系不兼容的地方改掉就行了。特别是不用适配本仓库，我要的是通用的一组skill。“只扫描 git ls-files，排除 .worktrees、node_modules、.venv、运行时状态和生成物。”，这种也是搞笑的，原本人家skill能跑，我的仓在这方面没有特殊性，根本不必改。引入codebase-design我认同，整个大流程设计我也认同，就是design-author阶段按场景需求调用codebase-design。“candidates.md：稳定候选 ID 与状态。”搞这么复杂干嘛，每次独立审视就行了。审视完存一份，后续也知道这份分析是哪个commit id就ok了。
  Agent 解读: 保留原 skill 的探索方式、候选卡片和 HTML 表达，只做通用兼容修改；引入 `codebase-design`；架构报告每次独立保存并标明所审视的 commit；不增加扫描过滤策略、候选台账或历史状态管理；`change-design-author` 仅在相关设计场景按需调用 `codebase-design`。

- Q4: 当前方案是否已经对齐，可以进入首文档定稿？
  A(原话): [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 这本身也是个需求，现在对齐完成了。我同意现在的。你开始写spec吧
  Agent 解读: 用户确认上一轮收敛出的最小方案，无需继续澄清，可以据此完成 spec。

## 用户场景

用户维护着一组可复用的工程 skill，并希望定期主动审视代码库架构，而不是只在某个需求已经立项或某次设计已经写完后才发现架构问题。用户调用 `improve-codebase-architecture` 时，仍获得原能力强调的有机代码探索、deepening candidates、before/after 可视化和 top recommendation；这项能力不被改造成某一个仓库专用的检查器。

每次审视结束后，HTML 报告保存在仓库的架构审视报告目录中。用户以后打开历史报告时，可以直接知道该报告审视的是哪个 Git commit，以及生成时所在的分支和工作区状态；每次报告彼此独立，不需要额外维护候选编号、候选状态或跨报告账本。

如果项目没有 Matt 体系约定的 `CONTEXT.md`、`CONTEXT-MAP.md` 或 ADR 目录，用户仍能正常运行架构审视；skill 会利用项目已有的 instructions、架构文档、领域词汇或决策记录，而不会为了运行扫描强迫项目采用另一套文档制度。

当用户从报告中选中一个候选后，架构审视阶段不直接展开 interface 设计，也不启动另一套 grilling/domain-modeling 流程，而是输出足以交给项目现有变更流程继续处理的简洁上下文。项目存在 change-* 流程时，候选可以作为 refactor 需求进入 `change-spec-author`；没有该流程时，用户仍能拿到独立 handoff，交给项目自己的后续流程。

进入技术设计阶段后，`change-design-author` 只在需求确实涉及模块深化、interface/seam 调整、职责重新归属或测试面选择时使用 `codebase-design` 的设计语言与原则；普通设计不会被强制套用该 skill。重要 interface 确实存在多种实质方案时，设计阶段可以进一步比较不同设计，而不是在每个 unit 中机械展开。

## 验收标准

### Requirement: 用户可以运行原有风格的通用架构审视

#### Scenario: 在任意代码仓调用架构审视
- **WHEN** 用户在一个代码仓中调用 `improve-codebase-architecture`
- **THEN** skill 继续通过有机探索发现 deepening opportunities，并给出包含候选、before/after 可视化、推荐强度和 top recommendation 的 HTML 报告
- **AND** 用户不会被要求先采用某一个特定仓库的目录、扫描过滤规则或架构检查清单

#### Scenario: 项目没有 Matt 约定的领域文档
- **GIVEN** 项目不存在 `CONTEXT.md`、`CONTEXT-MAP.md` 或 ADR 目录
- **WHEN** 用户调用架构审视
- **THEN** skill 正常继续，并利用项目实际已有的 instructions、架构文档、领域词汇或决策记录
- **AND** 不会仅为完成本次审视而创建领域词汇表或 ADR 制度

### Requirement: 每次架构审视报告独立持久化并可追溯到代码版本

#### Scenario: 在 Git 仓库生成报告
- **WHEN** 一次架构审视完成
- **THEN** HTML 报告保存在仓库的 `docs/architecture-reviews/` 目录，而不是操作系统临时目录
- **AND** 报告文件名包含生成时间与短 commit SHA，报告正文展示完整 commit SHA、分支和 working tree 的 clean/dirty 状态
- **AND** skill 告知用户报告的绝对路径并打开报告

#### Scenario: 报告目录尚不存在
- **GIVEN** 仓库尚无 `docs/architecture-reviews/` 目录
- **WHEN** 首次架构审视完成
- **THEN** 报告目录被自动建立，报告正常写入

#### Scenario: 当前目录无法取得 Git commit
- **GIVEN** 当前代码目录无法提供 Git commit 信息
- **WHEN** 架构审视完成
- **THEN** 报告仍然生成，并明确标示 commit 信息不可用，而不是伪造或省略版本语境

#### Scenario: 用户连续运行多次审视
- **WHEN** 用户在不同时间或不同 commit 上多次运行架构审视
- **THEN** 每次运行各自产生一份独立报告，旧报告不会被覆盖
- **AND** 用户无需维护候选 ID、候选状态或跨报告台账

### Requirement: 选中的架构候选进入项目已有变更流程

#### Scenario: 项目存在 change-* 流程
- **GIVEN** 用户从报告中选中一个候选，且项目提供 `change-spec-author`
- **WHEN** 用户决定继续推进该候选
- **THEN** 架构审视 skill 输出包含报告路径与版本、候选标题、涉及文件、当前问题、预期改善和待定问题的简洁 handoff
- **AND** 候选作为 refactor 需求进入 `change-spec-author`，而不是在架构审视阶段直接设计 interface 或修改代码

#### Scenario: 项目没有 change-* 流程
- **GIVEN** 用户从报告中选中一个候选，但项目没有 `change-spec-author`
- **WHEN** 用户决定继续推进该候选
- **THEN** skill 提供同样的独立 handoff，并把后续处理交给项目已有流程或用户决定

### Requirement: 技术设计按场景使用 deep-module 设计能力

#### Scenario: 设计涉及模块深化或 interface/seam 决策
- **GIVEN** 一个进入 `change-design-author` 的 unit 涉及模块深化、职责重新归属、interface/seam 调整或测试面选择
- **WHEN** 用户开始技术设计
- **THEN** design-author 使用 `codebase-design` 的 module、interface、depth、seam、adapter、leverage、locality 等设计语言和原则辅助决策
- **AND** 项目已经定义的领域名、产品名和正式架构术语保持原样，不因设计词汇被强行重命名

#### Scenario: 普通设计不涉及 deep-module 决策
- **GIVEN** 一个 unit 不涉及模块深化、重要 interface/seam 或测试面选择
- **WHEN** 用户调用 `change-design-author`
- **THEN** design-author 按原流程完成设计，不机械调用 `codebase-design`

#### Scenario: 重要 interface 存在多种实质方案
- **GIVEN** 设计阶段确认一个重要 interface 存在两种以上实质不同且各有权衡的方案
- **WHEN** 用户需要比较设计取舍
- **THEN** design-author 可以使用 `codebase-design` 的 Design It Twice 方法比较方案并给出推荐
- **AND** 该方法不会成为每个 unit 的固定步骤

## 范围与非目标

- 在范围：
  - 引入通用的 `codebase-design` 能力及其 deepening、Design It Twice 参考
  - 保留 `improve-codebase-architecture` 原有探索逻辑、候选表达和 HTML 可视化风格，仅修正与现有通用 skill 流程不兼容的部分
  - 架构审视报告持久化到 `docs/architecture-reviews/`，记录生成时间、commit、分支和工作区状态
  - 项目领域文档与决策记录按“存在则读取、不存在则继续”处理
  - 选中候选后生成 handoff，并优先接入项目已有的 spec/design 流程
  - `change-design-author` 在 deep-module 相关设计中按需使用 `codebase-design`
- 非目标：
  - 不针对 nano-multiagent 增加专用扫描规则、固定目录排除、固定架构维度或仓库特定检查清单
  - 不限制扫描输入为 `git ls-files`
  - 不增加 `candidates.md`、稳定候选 ID、候选状态机、历史报告比较或跨报告账本
  - 不大规模重写 `improve-codebase-architecture` 的探索方式、候选卡片结构或视觉报告形式
  - 不引入 Matt 的 `grilling`、`grill-with-docs`、`domain-modeling`、`setup-matt-pocock-skills`、spec/tickets/implement/TDD 主流程
  - 不要求项目创建 `CONTEXT.md`、CONTEXT map 或独立 ADR 层
  - 不强制每次 `change-design-author` 都调用 `codebase-design` 或执行 Design It Twice
  - 不修改 `change-orchestrator`、worker、verifier、reviewer 或 code-review 的既有职责
