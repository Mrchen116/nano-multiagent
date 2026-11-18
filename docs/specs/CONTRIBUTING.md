# 长青行为契约编写规范

> 本指南规定本仓**长青行为契约层** `docs/specs/<包>/` 的内容边界、文件结构和写法，以及 **delta-spec** 如何表达并归入 canonical spec。
>
> 全仓文档地图见 [`docs/README.md`](../README.md)；顶点架构(包、依赖方向、部署拓扑)在 [`SPEC.md`](../../SPEC.md)。本指南只管单包行为契约层。

## 这套体系长什么样

```
顶点架构      SPEC.md                          跨包:包 / 依赖方向 / 部署拓扑(手维护,极少变)
长青行为契约  docs/specs/{im,gateway}/
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

长青层是 **current 状态的单一权威**:打开对应包目录就知道"系统现在怎么表现",不必脑内合并 N 个历史单元。`docs/specs/<包>/spec.md` 是短入口,负责说明包职责、边界和 area 索引;具体契约以同目录 area 文档为准。它**不是 design**——HOW / 为什么留在 per-unit `design.md`(归档不维护)。本仓不维护 living 全量 design,也不建独立 ADR 层(`docs/decisions/`);决策的家是 per-unit `design.md` 的 `## 关键决策`。

## 哪些行为进入长期契约

先找出现行条款，再问：**这次改变后，谁在什么条件下，可以依赖什么不同的结果？** 消费者包括用户、客户端、对端节点，以及实际读取工具或上下文的模型。写清足以判定回归的条件、结果和例外。例如，设备离线期间可能仍显示旧聊天；同步得知访问已撤销后，重启也不能让内容重新出现。

判断细节是否必要，可以尝试换一种实现。中继改用另一种持久存储，仍须保证重启后同一帧只处理一次。头像可以重画，已有角色改名后仍要可辨认。公开字段的取值、权限失效时机、统计口径等一旦改变会影响消费者，应精确到足以互操作或判断结果。

仅当消费者的保证新增、改变或撤销时，才写 delta。恢复已约定的行为、保持同一保证的可见改版、内部重构，都可以在现有设计或收尾记录中写 `no spec delta` 并简述依据。本次交付要求的画法、文案或布局仍由设计、原型和验收记录承载。

## 不进 spec 的内容,分流到哪

| 不进长青 spec 的内容 | 落点 |
|---|---|
| 函数 / 类名、实现走查、内部数据结构、库选型 | 代码；跨模块通用写法遵守 [`development/coding-guidelines.md`](../development/coding-guidelines.md) |
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
- **不写** `覆盖: tests/...` 行、**不加** `[可执行]` / `[行为]` 标签、**不建** freshness/锚点测试。测试映射和验证记录属于测试或 change evidence，不写入契约正文。
- `> 对齐: <unit-id>` 只记录最近一次归并到该文件的 change unit；每份 spec 恰好一条、一个 unit，不累积历史 unit。只有实际发生变化的入口或 area 文件更新该标记，`scripts/docs-check` 校验声明唯一性和单个 unit 格式。
- 包入口 `Canonical Areas` 表中的 `Requirements` 是便于浏览的派生数量；`scripts/docs-check` 会按对应 area 文档中的 `### Requirement:` 标题机械校验数量、重复登记和遗漏登记。
- `Requirement` 是一份契约(一条规则),不是模块清单。一个 `Requirement` 配一个或多个 `Scenario`。
- 每个 area 文档优先控制在可一次读完的范围内。若单个 area 持续膨胀,先按语义继续拆 area,不要把入口 `spec.md` 重新变成大文件。

## 接口与跨端行为

接口 Scenario 写实际调用方发起的动作，以及对方能依赖的响应、拒绝或重试结果。协议已有权威 schema 时引用它，另写字段省略、确认、重放等仅靠类型看不出的语义。测试用于核对这些保证。

共享业务规则在负责判定结果的领域写全。客户端引用它，只补该端特有的可观察行为。例如，IM 决定哪些卡片改动随消息一次性消费；iOS 另写发送失败时如何保留正文与本地编辑。

## 契约层增量（delta-spec）

长青层通过 delta-spec 接收单个 change unit 对 canonical spec 的增量，不要求每个 unit 全量重写或重扫 canonical。是否产生 delta 按[长期契约收录判据](#哪些行为进入长期契约)决定。

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

- 先查同一行为已有的 Requirement 及直接引用。新规则收窄旧规则的适用条件时，把受影响的旧条目也列入本次 delta。
- `ADDED` 写新增条目的完整内容。
- `MODIFIED` 写修改后的完整条目。
- `REMOVED` 只写待删除的 Requirement 名称。

用户验收标准描述一次 change 的用户视角结果，delta-spec 描述 canonical spec 将发生的契约变化。两者可能覆盖相同场景，但承担的知识角色不同。实现前形成的 delta 只是目标状态；归并版本必须以最终实现的可观察行为为准。

## delta-spec 归并规则

归并只处理 delta-spec 指向的 canonical 文件和列出的 Requirement，不扩展成 canonical 全量重写。

1. 核对 delta 与实际实现、相关测试是否一致。把它与受影响的现行条款合读，确认同一条件下的结果明确，共享规则有唯一归属。发现未解释的实现偏差时先查清预期。
2. `ADDED` 追加到对应 canonical 文件，`MODIFIED` 替换同名条目，`REMOVED` 删除同名条目。
3. 归入 canonical 的每个条目仍须满足本指南的内容判据和格式纪律。
4. 新增 area 或移动 Requirement 时，同步更新包入口 `spec.md` 的 `Canonical Areas` 表。
5. 只更新实际发生变化的入口或 area 文件，并将其头部 `> 对齐:` 标记更新为当前 unit-id。

## 如何核实现有行为

从实际消费者、当前实现和相关测试核实行为，结合已确认需求判断哪些属于承诺。旧实现、历史验收和示例用作线索。测试与 spec 冲突时，核对适用版本、条件与已确认的意图，再决定修订哪一方。
