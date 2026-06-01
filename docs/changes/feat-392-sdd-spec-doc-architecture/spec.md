# feat-392: SDD 长青 spec 文档体系（行为契约层 + ADR + 顶点架构，收尾归并保持 current）

> 本 unit 是回顾性立项：把一段较长的交互式讨论（含两轮联网调研 + 读 OpenSpec 源码）沉淀成首文档。
> 调研结论单列附档 [`research-sdd-doc-landscape.md`](./research-sdd-doc-landscape.md)，本文件只写"做什么 / 目标状态"。

## Relations

- Depends on: 无
- Blocks: 无
- Related: 触及整个 `change-*` skill 套件（change-spec-author / change-design-author / change-orchestrator / change-reviewer）的读写侧行为，但不依赖任何具体 unit 先完成。

## 原始需求

> 现在change-*系列skill顺利的做SDD，但是现在只有个简单的全量SPEC.md，没有全量Design。我觉得需要有全量spec和design，然后后续在做sdd开发的时候，spec阶段先读全量spec，design阶段先读design，然后最终做完需求后，更新全量design和spec。你觉得呢

（后续在对话中逐步收敛，原话见【澄清记录】。）

## 澄清记录

> 本 unit 的"用户"= 用本仓做 SDD 的开发者 + `change-*` 系列 agent。澄清在一段连续讨论中完成，A 段粘用户原话。

- Q1: 全量 spec / design 该不该建？现状缺口在哪？
  A(原话): 现在change-*系列skill顺利的做SDD，但是现在只有个简单的全量SPEC.md，没有全量Design。我觉得需要有全量spec和design……spec阶段先读全量spec，design阶段先读design，然后最终做完需求后，更新全量design和spec。
  Agent 解读: 方向认可。但核实发现仓里其实已有分布式 design 层（`docs/{内核设计,CodingCLI,NodeGateway,IM}-SPEC.md`），真正缺的是"单元做完后把变更写回长青文档"这条闭环——不是缺一份文档。

- Q2: 那些既有的子系统 design 文档能直接用吗？
  A(原话): 这些文档虽然有，但是没有进行维护，很旧了。
  Agent 解读: 陈旧不均匀（NodeGateway-SPEC 停在 3-28、仍描述 refactor-387 已废弃的架构；内核/CLI 为 3 月 v1.0）。根因是闭环缺"写回"步，没有任何 skill 在单元收尾更新它们 → 必然 rot。

- Q3: 直接照现结构回填就行吗？
  A(原话): 而且结构也不一定好。我理解这些文档需要有一定规范的吧，比如应该放什么不应该放什么
  Agent 解读: 对。回填进烂结构=重新 rot。需要先定文档规范（放什么/不放什么 + 骨架），再回填。

- Q4: 规范怎么定才不是拍脑袋？
  A(原话): 你这是一个模版。我希望你上网详细研究下这个topic。用agent开发中，代码仓的spec/design文档应该如何组织，放那些东西。
  A(原话，补充): ../opensource-hub/OpenSpec 有openspec的git仓 / 你有其他仓库要研究也可以拉到opensource-hub中
  Agent 解读: 联网 + 读本地 OpenSpec 源码调研。关键发现：OpenSpec 用 **delta-spec + archive 时机械归并**把"长青层"和"变更稿"连起来；维护的是**行为契约 spec**，**不**维护 living design 文档。详见附档。

- Q5: 要不要每个 change 额外产出 delta-spec 工件？
  A(原话): 我觉得不用额外产出delta spec，在最后收尾orchestrator再改进去就行。
  Agent 解读: 采纳。**不引入独立 delta-spec 工件**；改为 orchestrator 在单元收尾时，依据本单元 design.md + 代码 diff，直接编辑 canonical 契约层。代价：手改非确定性，需配固定 Requirement/Scenario 格式 + 防 drift 校验闸。

- Q6: 那"全量长青层"里到底写什么？这是 spec 还是 design？
  A(原话): 所以你还没跟我说，全量的 新长青层，里面写啥
  A(原话，追问): 这是design还是spec？
  Agent 解读: 长青层写的是 **spec（行为契约：Purpose + Requirement/Scenario，SHALL/MUST）**，不是 design。澄清概念：**"全量 design"不建——它是 rot 重灾区**。design 的耐久残渣只有两处：架构级决策 → ADR；跨包结构/部署 → 顶点 SPEC.md。其余 HOW 留 per-unit design.md + 代码，归档不维护。

- Q7: 这套是 OpenSpec 一家之言，还是业界普遍做法？
  A(原话): 网上其他的做sdd也是这样的吗
  Agent 解读: 二次调研（Martin Fowler 三工具对比 + spec-kit 社区辩论）。结论：**"不维护 living 全量 design"是四家普世共识**；**"spec 是否做成 living 长青层"是真分歧**——Kiro/spec-kit 默认"代码即真相、spec 用完即弃"，Tessl/OpenSpec 维护 living merged spec；但撞上 fragmentation 的规模用户（含 spec-kit 社区）都在向 living-merge 收敛。用户最初的痛点（"只有个简单的全量 SPEC.md"）正是 fragmentation，故为本仓诉求应选 living-merge 派。共识警告：living spec 也会 drift，必须配自动强制闸。

## 用户场景

**现状（痛点基线）**

用本仓做 SDD 的开发者和 `change-*` agent，今天面对的文档世界是：

- 顶层只有一份 `SPEC.md`（架构总图）+ 四份子系统 `*-SPEC.md`（内部设计叙事）。
- 子系统文档**只在大重构时被人手动 bump**，没有任何环节在单元收尾更新它们 → 普遍陈旧（NodeGateway-SPEC 仍描述已废弃的"spawn 内核 uvicorn"架构）。
- `change-design-author` 调研时会**读** `SPEC.md` + `docs/`，但读到的是过期内容，比不读更误导。
- 单元做完后，新行为只落进代码 + 该单元的 `design.md`，**不回流**到任何长青文档。当前系统"现在到底怎么表现"的完整画面，散落在 64 个历史单元的文档里，要靠人脑顺序合并。

**目标（变更后）**

建立并接入一套**有规范、能自维护、不 rot** 的长青文档体系：

1. **长青行为契约层** `docs/specs/<包>/spec.md`：按包（kernel / im / gateway / cli）组织，内容是 `Purpose` + `Requirement`/`Scenario`（对外可观察的行为契约），描述"系统现在怎么表现"。它是 current 状态的单一权威，开发者/agent 读它即可掌握全貌，不必再脑内合并散单元。
2. **收尾归并**：单元在 orchestrator 收尾时，依据本单元 `design.md` + 代码 diff，把行为增量**直接编辑**进对应契约层文件，并 bump"对齐 `<最新 unit>`"行。**不产出独立 delta-spec 工件**。
3. **决策走 ADR**：架构级决策落 `docs/decisions/`（带 status / supersede 链接，append-only），不埋进会过期的设计文档。
4. **顶点 SPEC.md 重定位**：只保留跨包架构（包、依赖方向、部署拓扑），与契约层不重复；手维护，极少变。
5. **design 不做 living 大全**：`design.md` 保持 per-unit、归档留痕；"内部今天怎么搭"由代码 + 归档 design + ADR 承载，不单独维护一份会追不上代码的设计大全。
6. **读侧接入 + 防 drift**：`change-spec-author` / `change-design-author` 在各自阶段读契约层（current），design 阶段对代码做 grounding 校验；并有一个 spec-vs-code 的强制闸，使 drift 可见而非静默累积。
7. **迁移**：把四份既有子系统 `*-SPEC.md` 中稳定的契约部分蒸馏进新契约层，过时的实现叙事退役；`SPEC.md` 收口到顶点定位。

最终让"读侧喂的是新 spec、写侧每单元增量维护、design 不做大全"三头闭合。

## 验收标准

> "用户"= 开发者 + `change-*` agent；"可观察"= 在仓库文档结构 / skill 运行行为上看得到。

### Requirement: 长青行为契约层存在且按包组织

#### Scenario: 打开契约层看到当前行为契约
- **WHEN** 开发者或 agent 打开 `docs/specs/<包>/spec.md`（包 ∈ {kernel, im, gateway, cli}）
- **THEN** 看到 `## Purpose` + 若干 `### Requirement` / `#### Scenario`（SHALL/MUST、Given/When/Then 结构），描述该包对外可观察的行为契约
- **AND** 内容反映系统当前行为，而非某个历史单元的快照

#### Scenario: 契约层不含实现走查
- **WHEN** 审阅任一 `docs/specs/<包>/spec.md`
- **THEN** 其中没有函数/类名级实现走查、库选型、内部数据结构——这些不在契约层

### Requirement: 单元收尾把行为增量归并进契约层（无独立 delta 工件）

#### Scenario: 单元完成后契约层被更新
- **GIVEN** 一个改变了某包对外行为的单元已实现完成
- **WHEN** orchestrator 走收尾流程
- **THEN** 对应 `docs/specs/<包>/spec.md` 被更新以反映新行为，且文件头"对齐"行 bump 到该单元 id
- **AND** 全程没有产出独立的 delta-spec 文件（增量直接编辑进 canonical）

#### Scenario: 纯内部、无对外行为变化的单元
- **GIVEN** 一个不改变任何对外可观察行为的单元（纯内部重构）
- **WHEN** orchestrator 收尾
- **THEN** 契约层无需改动，收尾记录显式注明"no spec delta"

### Requirement: 架构级决策以 ADR 形式独立留痕

#### Scenario: 记录一条架构决策
- **WHEN** 某单元做出一个架构级决策（顶点 SPEC.md 依赖的那类）
- **THEN** 在 `docs/decisions/` 新增一条 ADR，含 status（proposed/accepted/superseded）
- **AND** 推翻旧决策时，是新增 ADR + 把旧 ADR 标 superseded 并互链，而非静默改写旧文

### Requirement: 不维护 living 全量 design 文档

#### Scenario: 找"内部今天怎么实现"
- **WHEN** 开发者想知道某包内部当前如何实现
- **THEN** 答案来自代码 + 该功能所属单元的归档 `design.md` + 相关 ADR
- **AND** 仓库中不存在一份号称 current 的"全量 design 大全"（即无此 rot 载体）

### Requirement: 顶点 SPEC.md 与契约层分工不重复

#### Scenario: 顶点只讲跨包架构
- **WHEN** 阅读 `SPEC.md`
- **THEN** 看到的是跨包内容（4 个包、依赖方向硬规则、部署拓扑），不下钻任何单包内部行为契约
- **AND** 同一事实不在 SPEC.md 与契约层各写一遍（单一 canonical 落点，其余靠链接）

### Requirement: 文档规范 GUIDE 定义放什么/不放什么 + 骨架

#### Scenario: 作者按规范判断内容归属
- **WHEN** 开发者或 agent 要新增/更新一份长青文档，先查文档规范（如 `docs/DESIGN_DOC_GUIDE.md`）
- **THEN** 规范给出判据（"实现能变而对外行为不变的，不进 spec"）、契约层骨架、以及"不进 spec 的内容各自去哪"的分流表

### Requirement: change-* 读侧接入契约层并对代码做 grounding

#### Scenario: spec / design 阶段读到的是 current
- **WHEN** `change-spec-author` 或 `change-design-author` 启动并调研对应包
- **THEN** 它读 `docs/specs/<包>`（current 契约层）而非过期子系统设计叙事
- **AND** design 阶段会拿契约层与当前代码核对（grounding），发现不一致即报出

### Requirement: spec-vs-code 防 drift 校验闸

#### Scenario: 契约层与代码背离被显式暴露
- **GIVEN** 契约层声明的某行为与代码实际行为已背离
- **WHEN** 运行防 drift 校验
- **THEN** 该背离被显式报出（而非静默累积），提示需在收尾或专门单元修正

### Requirement: 既有陈旧文档迁移到新结构

#### Scenario: 旧子系统 SPEC 完成迁移
- **WHEN** 迁移完成后查看四份原 `docs/*-SPEC.md`
- **THEN** 其中稳定的契约部分已蒸馏进 `docs/specs/<包>/`，过时的实现叙事已退役，不再留存会误导的 living 设计叙事
- **AND** `SPEC.md` 已收口到顶点定位

## 范围与非目标

- **在范围**：
  - 文档规范 GUIDE（判据 + 契约层骨架 + 不进 spec 的分流表 + 收尾归并 checklist + 读侧 grounding checklist）。
  - 长青行为契约层结构 `docs/specs/<包>/`（按包组织）。
  - ADR 层 `docs/decisions/`。
  - 顶点 `SPEC.md` 重定位（跨包架构，去单包内部）。
  - `change-*` skill 读写侧接入：spec-author/design-author 读侧指向契约层 + grounding；orchestrator 收尾归并步；防 drift 校验闸。
  - 迁移既有四份子系统 `*-SPEC.md` + `SPEC.md` 到新结构。

- **非目标**：
  - **不引入独立 delta-spec 工件**（用户明确否决；归并由 orchestrator 收尾手工编辑 canonical 完成）。
  - **不维护 living 全量 design 文档**（业界共识的 rot 陷阱）。
  - **不强绑外部 SDD 工具**（openspec CLI / spec-kit 等）——只借鉴机制，不引入工具依赖。
  - 不在本 unit 决定实现形态（归并是纯手工还是配脚本、防 drift 闸的技术形态 contract-test/CI/其它）——交 design 阶段。
  - 不要求一次性把 64 个历史单元全部回灌进契约层；迁移可迭代，先覆盖四大包当前行为基线即可。
