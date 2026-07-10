# refactor-457: 长青 spec 按 area 拆分

## 原始诉求

> 当前长青层spec，每个spec文件多少行

> 我觉得现在太长了，而且项目还在继续演进，这样不方便维护和读取消费了。你觉得应该怎么处理

> 很好，新开一个分支worktree，按这个顺序开始做。

> 主仓中做了大量需求，spec做了很多更新，你可能要重新做。或者在你做的基础上补充。你来决定怎么做。

> change-*系列skill中关于spec的部分有一并修改吗

> [$change-spec-author](/Users/czj/Repos/nano-multiagent/.claude/skills/change-spec-author/SKILL.md) 这个本身也是一个特殊的需求，你应该补一个首文档

## 澄清记录

- Q1: 这次重构的核心目标，是一次性拆小现有文件，还是建立持续防止长青 spec 再次膨胀的规则？
  A(原话): 不用跟我澄清，直接补。我review
  Agent 解读: 用户授权按已完成的现状调研直接补全首文档，由用户在 PR 中统一审阅。目标按“建立可持续规则”收口，不再逐项提问。

## 现状痛点

长青 spec 是维护者、change-* agent 和后续变更单元理解系统 current 行为的共同入口。随着项目持续演进，
kernel、gateway、IM 的单包 `spec.md` 已分别增长到 1065、928、1053 行；CLI 为 180 行。前三份文档同时承担
包入口、领域导航和全部 Requirement/Scenario 细节，产生以下问题：

- 维护者为定位一个局部行为也需要读取整份近千行文档，检索、理解和审阅成本随需求持续累积。
- 不同语义领域的契约集中修改在同一文件，多个 unit 更容易发生无关 diff 交叠和合并冲突。
- 包级职责、边界与具体行为混在同一层级，新读者难以先建立地图再按需下钻。
- change-* 流程仍把 canonical spec 默认视为单个 `spec.md`，即使手工拆分，后续 delta-spec 归并也会继续把内容写回大文件。

问题不在契约内容过多，而在所有内容被压进同一个消费单元。通过删减或摘要化缩短文档会丢失 current 行为
细节，不能解决长期维护问题。

## 目标状态

`docs/specs/` 继续作为长青行为契约的单一权威，已有契约语义不因重构而改变。文档改为两级消费结构：

- 每个包的 `spec.md` 是稳定、短小的入口，说明包级职责、边界并索引 canonical areas。
- 具体 Requirement/Scenario 按语义内聚放入同目录 area 文档；读者只需打开与当前问题相关的页面。
- area 按“语义是否内聚、能否一次读完”持续演进；单个 area 再次膨胀时继续按语义拆分，不设机械行数门禁。
- delta-spec 镜像 canonical 目录并指向具体 target，change-* 在 grounding、设计、归并和验收阶段均识别 area 文档。
- 当前仍易于维护的 CLI spec 保持单文件；拆分是按需能力，不是所有包必须采用的形式。

## 用户侧验收标准（不变性）

重构前，维护者可以从包级 spec 查到该包全部 current 行为，change-* 流程可以读取对应契约并把 unit 的行为
增量归并回长青层。重构后这些能力保持不变，同时维护者可以先从包入口建立领域地图，再只读取或修改相关
area；文档位置变化不改变产品运行时行为，也不改变任何已有 Requirement/Scenario 的含义。

### Requirement: 维护者可从稳定入口定位完整长青契约

#### Scenario: 从包入口查找局部行为
- **WHEN** 维护者打开 kernel、gateway 或 IM 的 `spec.md` 查找某一类 current 行为
- **THEN** 入口展示包级职责、边界和 area 索引，维护者可通过链接进入承载该行为的 canonical 文档

#### Scenario: 查找未拆分包的行为
- **WHEN** 维护者打开当前规模仍适合单文件维护的 CLI spec
- **THEN** 可直接读取完整契约，不需要为了形式一致而跨多个空泛 area 跳转

### Requirement: 文档重组不得改变既有行为契约

#### Scenario: 对账拆分前后的契约
- **WHEN** 维护者比较重构前后的 Requirement/Scenario
- **THEN** 主仓最新的 143 个 Requirement 块均可在新结构中找到，内容不因搬迁而丢失、改名或改写语义

#### Scenario: 用户继续使用既有产品能力
- **WHEN** 用户继续使用 kernel、gateway、IM 或 CLI 的既有能力
- **THEN** 可观察结果与重构前一致，因为本变更不修改运行时代码或产品行为

### Requirement: 后续变更可只消费和更新相关 area

#### Scenario: 新 unit grounding 既有行为
- **WHEN** change-* 作者为一个只涉及局部领域的 unit 读取长青契约
- **THEN** 可从包入口定位并读取相关 area，无需把同包所有无关契约一并载入上下文

#### Scenario: 归并局部契约增量
- **WHEN** unit 的 delta-spec 只新增、修改或删除某个 area 的行为
- **THEN** delta 可指向 `docs/specs/<包>/<target>.md` 的具体 target，并归并到同一 canonical area

#### Scenario: 新增或移动 area
- **WHEN** 后续演进新增 area，或把 Requirement 移到更合适的 area
- **THEN** 包入口同步反映新的导航和 Requirement 数量，维护者通过现有入口仍能找到完整契约

### Requirement: 文档结构可随规模继续演进

#### Scenario: 单个 area 再次变得难以一次读完
- **WHEN** 一个 area 因持续新增契约而失去语义内聚或变得难以一次读完
- **THEN** 维护者可继续按语义拆分 area，同时保持包入口稳定、契约完整且链接可达

#### Scenario: area 仍然紧凑内聚
- **WHEN** 一个包或 area 仍可被清晰维护和消费
- **THEN** 不因机械行数阈值强制拆分，避免产生碎片化文档

## 范围与非目标

本期范围：

- 将 kernel、gateway、IM 的单文件长青契约重组为包入口加 area 文档。
- 增加长青层总入口，并更新 `SPEC.md`、`AGENTS.md`、`docs/SPEC_GUIDE.md` 的导航和规则。
- 更新涉及 spec grounding、delta 产出、审查、归并和 PR 描述的 change-* skill 与模板，使其支持具体 area target。
- 以主仓最新契约为基线完成迁移和完整性校验。

非目标：

- 不新增、删除或重新定义任何运行时产品行为。
- 不借拆分机会润色、合并或重命名已有 Requirement/Scenario。
- 不强制拆分当前 180 行的 CLI spec，也不规定所有包必须拥有相同 area 数量。
- 不引入 spec 代码生成、测试锚点、freshness 检查或机械行数门禁。
- 不批量改写已归档 unit 的历史 delta-spec；新规则用于当前及后续变更。

## 影响范围

直接影响长青文档的作者和消费者：

- `docs/specs/` 的包入口、area 文档和总入口。
- `SPEC.md`、`AGENTS.md` 与 `docs/SPEC_GUIDE.md` 中的长青层导航及维护规则。
- change-spec-author、change-design-author、change-design-reviewer、change-orchestrator、change-reviewer 的 spec 读取、
  delta target、审查和归并约定及相关模板。

不影响 `src/`、运行时配置、持久化数据、外部接口和用户产品旅程。

## 迁移与回滚策略

迁移以主仓最新版本为基线，按完整 Requirement 块移动，避免在结构调整中同时改写语义。迁移完成后对账：

- 拆分前后的 143 个 Requirement 块逐项一致。
- 包入口列出的 Requirement 数与 area 实际数量一致。
- 长青层及相关指南中的本地 Markdown 链接全部可达。
- change-* 对 canonical target 的描述统一支持 `docs/specs/<包>/<target>.md`。

这是纯文档结构迁移，不涉及数据或运行时兼容窗口。若新结构在 review 中被判定不可接受，可整体回退本 unit，
恢复各包单文件 spec；若仅某个 area 边界不合适，可移动完整 Requirement 块并同步入口索引，不需要改变契约内容。
