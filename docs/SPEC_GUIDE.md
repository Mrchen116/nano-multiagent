# SPEC_GUIDE — 长青 spec 文档怎么写、什么进、什么不进

> 本指南规定本仓**长青行为契约层** `docs/specs/<包>/spec.md` 的写法,以及单元如何把行为增量经
> **delta-spec** 归并回去。它服务三类作者:写契约的人/agent(判断"这条该不该进 spec、怎么落");
> `change-design-author`(design 阶段产出本单元的 delta-spec —— 对 canonical 的 ADDED/MODIFIED/REMOVED);
> `change-orchestrator`(收尾据实际代码 diff 校正 delta 后,合并进 canonical)。
>
> 顶点架构(包、依赖方向、部署拓扑)在 [`SPEC.md`](SPEC.md);本指南只管单包行为契约层。

## 这套体系长什么样

```
顶点架构      SPEC.md                          跨包:包 / 依赖方向 / 部署拓扑(手维护,极少变)
长青行为契约  docs/specs/{kernel,im,gateway,cli}/spec.md
                                               单包对外可观察行为(Purpose + Requirement/Scenario)
                                               —— 经 delta-spec 归并保持 current,本指南管这一层
契约层增量    docs/changes/<unit>/specs/<包>/spec.md   (delta-spec,镜像 canonical 目录)
                                               per-unit 对 canonical 的 ADDED/MODIFIED/REMOVED Requirements;
                                               design 阶段产,收尾据实际 diff 校正后合并进长青层,随变更稿归档
变更稿        docs/changes/<unit>/{spec,design,tasks}.md
                                               per-unit,易逝,ship 后归档;架构决策记在 design.md §关键决策
```

长青层是 **current 状态的单一权威**:打开它就知道"系统现在怎么表现",不必脑内合并 N 个历史单元。
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
| 函数 / 类名、实现走查、内部数据结构、库选型 | 代码 + 注释(COMMENTING_GUIDE) |
| "当初为什么这么选"(决策) | 该单元 `docs/changes/<unit>/design.md` 的 `## 关键决策` |
| 启停命令、调试 how-to、加 channel 教程 | `AGENTS.md` / `docs/operator-runbook.md` |
| 跨包架构总图、依赖方向、部署拓扑 | `SPEC.md`(顶点) |
| 进行中的 bug / TODO / 迁移笔记 | `docs/changes/<unit>/` / GitHub issue |

**单一 canonical 落点**:同一事实只在一处写全,其余靠链接。契约层与 SPEC.md 不重复同一句话。

## 契约层文件骨架

每份 `docs/specs/<包>/spec.md` 按此结构:

```markdown
# <包> Specification

> 对齐: <最新改动该包行为的 unit-id>

## Purpose

<这个包对外承担什么职责、显式**不**负责什么。一两段,不下钻实现。>

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
  drift 不靠机械绑定,靠收尾软对账(见下「收尾归并 checklist」)。
- `> 对齐: <unit-id>` 行是该文件被哪个单元最后更新的标记,收尾归并时 bump。
- `Requirement` 是一份契约(一条规则),不是模块清单。一个 `Requirement` 配一个或多个 `Scenario`。

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

## 契约层增量(delta-spec):何时产、放哪、怎么写

长青层**不靠**"每个单元收尾全量重扫 canonical"维护(每单元全量既不现实也无必要),而是用
**delta 归并**:每个单元只声明它对 canonical 的**增量**,收尾把增量并回去。

**何时产 / 谁产**:`change-design-author` 在 design 阶段产出——那时已握有首文档【验收标准】+ 关键决策 +
契约层 grounding 三份输入,能投影出"本单元对 canonical 改什么"。它是 design 的**派生产物**,不是首文档,
不回头改用户场景(发现验收标准有疏漏仍按规矩停下回 `change-spec-author`)。

**放哪**:`docs/changes/<unit>/specs/<包>/spec.md` —— **镜像** canonical `docs/specs/<包>/spec.md` 的
目录结构(包 ∈ {kernel,im,gateway,cli}),与变更稿 `spec.md`/`design.md` 同处 unit 目录、随其归档。本单元
没碰的包不建对应文件。

**怎么写**:一份"迷你 canonical",同骨架(可选 `## Purpose`)+ 三个 delta 段,只写**变更的** Requirement:

```markdown
# <包> Specification (delta for <unit-id>)

## ADDED Requirements
### Requirement: <新增的契约>
#### Scenario: ...

## MODIFIED Requirements
### Requirement: <被改的契约,写改后的完整条目>
#### Scenario: ...

## REMOVED Requirements
### Requirement: <被删的契约名>
```

- 每条仍过本指南「两问判据」+「库契约四纪律」(尤其 kernel:主语=消费者,把用户视角的验收标准
  **翻译**成 sdk 消费者视角,不照抄)。
- 终端产品(im/gateway/cli)的 delta 多是验收标准 Scenario 的契约层镜像;kernel 需视角翻译。
- 本单元无对外行为变化(纯内部重构)→ **不产 delta 文件**,在 design.md 显式注明 "no spec delta"。

**它和首文档【验收标准】的关系**:验收标准是**用户视角**的本单元验收清单(给 reviewer 走旅程);delta-spec
是**契约视角**的 canonical 增量(给收尾合并)。两者对终端产品内容重合,是**视角投影**不是冗余——delta 由
design-author 从【验收标准】+ 决策投影而来。

**为什么是草案、收尾要校正**:design 期产的 delta 是"预计要改什么"。worker 实现时会偏(加了没预见的对外
行为、或某条没落地),所以收尾(orchestrator §7.0)**先拿实际代码 diff 校正 delta,再合并**。

## 收尾归并 checklist(orchestrator 在提 PR 前执行)

单元的行为增量经 design 阶段产的 **delta-spec**(`docs/changes/<unit>/specs/<包>/spec.md`)合并回
canonical——**不全量重扫**,只动 delta 列的条目。对每个有 delta 文件的包:

- [ ] **校正 delta(design 草案 → 实际代码)**:delta 是 design 期预测,worker 实现可能偏。拿实际代码
      diff 核对 delta 每条 ADDED/MODIFIED/REMOVED——实现期新增的对外行为补进 delta、design 写了但没
      落地的删掉。无 delta 文件(design 注 "no spec delta")且 diff 也无对外行为变化 → 跳过本包。
- [ ] **软对账(advisory,不出红测)**:复用 reviewer 旅程 + verifier——对**校正后 delta 的每条**
      Requirement/Scenario 搜代码 + 测试,确认契约与实现一致,背离则在报告里**显式报出**(改实现或改
      delta),不静默累积。**软对账,不出红测、不机械硬卡**;靠 reviewer/verifier 尽责兜。范围 = 本单元
      delta,**不是 canonical 全量**(canonical 其余条目由各自所属单元收尾时已对过账)。
- [ ] **把 delta 合并进 `docs/specs/<包>/spec.md`**:ADDED 追加、MODIFIED 替换对应条目、REMOVED 删
      对应条目(机械对应,因 delta 与 canonical 同骨架)。每条进 canonical 前再过「两问判据」+「库契约四纪律」。
- [ ] **bump 头部 `> 对齐:` 行**到本 unit-id。

> 为什么 delta + 软对账够用:`tests/contract/` 的硬不变量测试本就每次 pytest 跑,与 spec 是否声明链
> 无关——放弃显式 `覆盖:` 绑定损失很小,换来契约层格式干净。delta 把"该验 / 该合并什么"限定到本单元
> 增量,收尾不必全量重扫;手改的非确定性由 delta 固定骨架 + 收尾校正 / 软对账兜。

## 读侧 grounding checklist(change-* 作者在各自阶段执行)

长青层只有被读才有价值。`change-*` 作者按阶段读契约层:

- [ ] **spec 阶段**(`change-spec-author`):立项调研对应包时,读 `docs/specs/<包>`(current 契约层)
      取词汇 / 对齐既有行为,而非读会误导的过期子系统设计叙事。
- [ ] **design 阶段**(`change-design-author`):读 `docs/specs/<包>` **并对当前代码做 grounding**——
      拿契约层声明的行为与 `src/<包>/` 实际代码核对;发现契约层与代码**不一致**即在「现状摘要」里
      报出(契约层可能已 drift,本单元不一定负责修,但要让人看见)。**并据【验收标准】+ 关键决策产出
      本单元 delta-spec**(`docs/changes/<unit>/specs/<包>/spec.md`,见上「契约层增量」节)。
- [ ] **收尾阶段**(orchestrator):见上「收尾归并 checklist」——校正 delta、软对账、合并进 canonical。

## 迁移料源优先级(逆向已有包的当前契约时)

为已存在的包逆向出契约基线时,料源优先级:

1. `tests/contract/` + 各包测试套(**可执行契约,不 drift**)——锚点。
2. `src/<包>/` 实际代码逆向。
3. 旧子系统 SPEC(`docs/archive/*-SPEC.md` 等)**仅作 checklist**:每条进新层前拿代码重核,核不上即弃。

**不从旧文档蒸馏**——旧文档 rot 太久,直接蒸馏=把旧 drift 种进新层(例:旧内核 SPEC 仍描述
refactor-387 已删的 HTTP API)。
