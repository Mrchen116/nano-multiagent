# 长青行为契约编写规范

> 本指南规定本仓**长青行为契约层** `docs/specs/<包>/` 的内容边界、文件结构和写法，以及 **delta-spec** 如何表达并归入 canonical spec。
>
> 全仓文档地图见 [`docs/README.md`](../README.md)；顶点架构(包、依赖方向、部署拓扑)在
> [`SPEC.md`](../../SPEC.md)。本指南只管单包行为契约层。

## 这套体系长什么样

```
顶点架构      SPEC.md                          跨包:包 / 依赖方向 / 部署拓扑(手维护,极少变)
长青行为契约  docs/specs/{kernel,im,gateway,cli}/
                                               单包对外可观察行为;spec.md 是入口索引,
                                               area 文档承载具体 Requirement/Scenario
                                               —— 经 delta-spec 归并保持 current,本指南管这一层
契约层增量    docs/changes/<unit>/specs/<包>/*.md   (delta-spec,镜像 canonical 目录)
                                               per-unit 对 canonical 的 ADDED/MODIFIED/REMOVED Requirements;
                                               实现完成后以最终行为为准归入长青层;
                                               unit 结束后随其移到 docs/changes/archive/<unit>/
变更稿        docs/changes/<unit>/{spec,design,tasks}.md
                                               per-unit,易逝,unit 结束后归档到 docs/changes/archive/<unit>/;
                                               架构决策记在 design.md §关键决策
```

长青层是 **current 状态的单一权威**:打开对应包目录就知道"系统现在怎么表现",不必脑内合并 N 个历史单元。
`docs/specs/<包>/spec.md` 是短入口,负责说明包职责、边界和 area 索引;具体契约以同目录 area 文档为准。
它**不是 design**——HOW / 为什么留在 per-unit `design.md`(归档不维护)。本仓不维护 living 全量
design,也不建独立 ADR 层(`docs/decisions/`);决策的家是 per-unit `design.md` 的 `## 关键决策`。

## 判据:这条该不该进契约层(两问,都 yes 才进)

要给长青层加/改一句话,先过两问:

1. **再过 5 个 unit 还成立吗?**(稳定性)实现能换而对外行为不变的东西,不进 spec。
2. **生手读几分钟代码能否自己还原?**(不可廉价重建)代码/注释里一看就懂的,不进 spec。

任一为 no → 不进契约层,按下面的分流表各归其位。

## 不进 spec 的内容,分流到哪

| 不进长青 spec 的内容 | 落点 |
|---|---|
| 函数 / 类名、实现走查、内部数据结构、库选型 | 代码 + [`development/commenting.md`](../development/commenting.md) |
| "当初为什么这么选"(决策) | 该单元 `docs/changes/<unit>/design.md` 的 `## 关键决策` |
| 本地环境、测试命令、提交格式和测试身份 | `docs/development/local-development.md` |
| worktree 服务隔离与进程清理 | [`development/worktree-runtime.md`](../development/worktree-runtime.md) |
| 启停命令、调试 how-to、加 channel 教程 | [`operations/`](../operations/README.md) |
| 跨包架构总图、依赖方向、部署拓扑 | `SPEC.md`(顶点) |
| 进行中的 bug / TODO / 迁移笔记 | `docs/changes/<unit>/` / GitHub issue |

**单一 canonical 落点**:同一事实只在一处写全,其余靠链接。契约层与 SPEC.md 不重复同一句话。

## 契约层目录骨架

每个包目录至少有一个入口 `docs/specs/<包>/spec.md`。入口保持短小,只放包级职责、边界和 area 索引:

```markdown
# <包> Specification

> 对齐: <最新改动该包行为的 unit-id>

## Purpose

<这个包对外承担什么职责、显式**不**负责什么。一两段,不下钻实现。>

## Canonical Areas

| Area | Covers | Requirements |
|---|---|---|
| [<Area>](<area>.md) | <覆盖的语义范围> | <Requirement 数> |
```

具体契约写在 `docs/specs/<包>/<area>.md`,按此结构:

```markdown
# <包> - <Area> Specification

> 对齐: <最新改动该 area 行为的 unit-id>
> 上级: [<包> Specification](spec.md)

## Purpose

<这个 area 约束哪一组对外行为。>

## Requirements

### Requirement: <一句话契约,SHALL/MUST 口吻>

<可选:一句话说明这条契约约束的是什么。>

#### Scenario: <这条契约的一个可观察情形>
- **GIVEN** <前置状态>
- **WHEN** <消费者发起的动作>
- **THEN** <消费者可观察的结果>
- **AND** <附加保证,可选>
```

格式纪律(本仓决策,务必遵守):

- 契约层保持**纯** `Purpose + Requirement/Scenario`。
- **不写** `覆盖: tests/...` 行、**不加** `[可执行]` / `[行为]` 标签、**不建** freshness/锚点测试。
  测试映射和验证记录属于测试或 change evidence，不写入契约正文。
- `> 对齐: <unit-id>` 记录最后修改该文件的 change unit。只有实际发生变化的入口或 area 文件更新该标记。
- `Requirement` 是一份契约(一条规则),不是模块清单。一个 `Requirement` 配一个或多个 `Scenario`。
- 每个 area 文档优先控制在可一次读完的范围内。若单个 area 持续膨胀,先按语义继续拆 area,不要把入口
  `spec.md` 重新变成大文件。

## 给「库 / 内核」写契约的额外纪律

终端产品(IM / Gateway / CLI)的"可观察行为"= 人在产品上看到/敲到什么。**内核 `agent` 是库**,
没有 UI,它的"消费者"是经 `agent.sdk` 调用它的两个产品 + `tests/contract/` 里的契约测试。给库写契约
照 Design by Contract(pre/post/invariant)+ Consumer-Driven Contracts 裁剪,四条硬纪律:

1. **WHEN/THEN 的主语必须是消费者**(产品 / `agent.sdk` 调用方 / contract 测试)。一旦写成
   "core 调 platform 的 X"就是实现走查,踢出契约层。
2. **每个 Requirement 是一份 pre→post 契约,或一条 invariant**——不是模块清单。
   - `GIVEN` 写调用方/Kernel 的前置态(precondition);`WHEN` 写调用方经 sdk 发起调用;
     `THEN` 写调用方可观察的结果(postcondition:返回形态 / 抛的错 / 不变量被保住)。
   - 跨层不变量(如"`core` 不依赖 `platform`""产品只能 import `agent.sdk`")写成 invariant 型
     `Requirement`(SHALL NOT…),它由 `tests/contract/` 的硬不变量测试照常把守(与是否在 spec 声明无关)。
3. **按 CDC 裁剪范围**:只收**调用方依赖的对外行为**,内部可变能力不进。这天然防止 kernel spec
   滑成"内部实现清单"。
4. **spec-anchored**:契约 spec 有文档价值、可对账,但**不要求**代码从 spec 全量生成。维护方式 =
   文档化 + 与代码对账,不是 regenerate。

## 契约层增量（delta-spec）

长青层通过 delta-spec 接收单个 change unit 对 canonical spec 的增量，不要求每个 unit 全量重写或重扫 canonical。只有对外可观察行为发生变化时才需要 delta-spec；纯内部重构不产生 delta 文件。

### 放在哪里

delta-spec 位于 `docs/changes/<unit>/specs/<包>/<target>.md`，其相对路径镜像 canonical `docs/specs/<包>/<target>.md`。`<target>` 可以是入口 `spec.md`，也可以是具体 area（如 `external-channels.md`）。没有变化的包或 area 不创建对应文件。

### 如何编写

delta-spec 是一份只包含变更条目的“迷你 canonical”，沿用 Requirement/Scenario 骨架，并用三个区段表达增量：

```markdown
# <包> <target> Specification (delta for <unit-id>)

## ADDED Requirements
### Requirement: <新增的契约>
#### Scenario: ...

## MODIFIED Requirements
### Requirement: <被改的契约，写改后的完整条目>
#### Scenario: ...

## REMOVED Requirements
### Requirement: <被删的契约名>
```

- 每条仍须通过本指南的“两问判据”和“库契约四纪律”。
- `ADDED` 写新增条目的完整内容。
- `MODIFIED` 写修改后的完整条目。
- `REMOVED` 只写待删除的 Requirement 名称。
- 终端产品（IM、Gateway、CLI）的 delta 通常是用户验收场景在契约层的投影；kernel 必须转换为 `agent.sdk` 消费者视角。

用户验收标准描述一次 change 的用户视角结果，delta-spec 描述 canonical spec 将发生的契约变化。两者可能覆盖相同场景，但承担的知识角色不同。实现前形成的 delta 只是目标状态；归并版本必须以最终实现的可观察行为为准。

## delta-spec 归并规则

归并只处理 delta-spec 指向的 canonical 文件和列出的 Requirement，不扩展成 canonical 全量重写。

1. 归并前的 delta 必须与最终实现的可观察行为一致。
2. `ADDED` 追加到对应 canonical 文件，`MODIFIED` 替换同名条目，`REMOVED` 删除同名条目。
3. 归入 canonical 的每个条目仍须满足本指南的内容判据和格式纪律。
4. 新增 area 或移动 Requirement 时，同步更新包入口 `spec.md` 的 `Canonical Areas` 表。
5. 只更新实际发生变化的入口或 area 文件，并将其头部 `> 对齐:` 标记更新为当前 unit-id。

## 迁移料源优先级(逆向已有包的当前契约时)

为已存在的包逆向出契约基线时,料源优先级:

1. `tests/contract/` + 各包测试套(**可执行契约,不 drift**)——锚点。
2. `src/<包>/` 实际代码逆向。
3. 旧子系统 SPEC(`docs/archive/*-SPEC.md` 等)仅作参考线索:每条进新层前拿代码重核,核不上即弃。

**不从旧文档蒸馏**——旧文档 rot 太久,直接蒸馏=把旧 drift 种进新层(例:旧内核 SPEC 仍描述
refactor-387 已删的 HTTP API)。
