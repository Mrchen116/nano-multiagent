# 调研附档：Agent 开发中代码仓 spec/design 文档怎么组织

> feat-392 的支撑材料。两轮调研：(1) 联网 + 读本地 `~/Repos/opensource-hub/OpenSpec` 源码；(2) 联网核对"是否业界普遍做法"。
> 本档是 reference，不是验收对象。结论已提炼进 `spec.md` 的【澄清记录】与【目标状态】。

## 1. 五类文档分层（综合 spec-kit / Kiro / OpenSpec / ADR / arc42 / C4）

不是"一份大文档"，是五类各司其职、防 rot 机制各不同：

| 层 | 业界名 | 装什么 | 本仓对应 | 防 rot 机制 |
|---|---|---|---|---|
| 约定/steering | AGENTS.md、Kiro steering、spec-kit constitution | 规范、命令、how-to、"永远用 X" | AGENTS.md + COMMENTING/TESTING_GUIDE + runbook | 约定变了才改 |
| 顶层架构 | C4 Context/Container | 跨包：包、依赖方向、部署拓扑 | `SPEC.md` | 极少变 |
| 组件行为契约 | C4 Component / OpenSpec specs | 单包对外可观察行为（Requirement/Scenario） | （待建）`docs/specs/<包>/` | **单元收尾归并保持 current** |
| 决策 | ADR | 一条决策一记，带 status + supersede | （待建）`docs/decisions/` | append-only，废弃靠 status 不靠覆盖 |
| 变更稿 | OpenSpec changes/、Kiro/spec-kit spec | per-change 的 what/how/tasks，易逝 | `docs/changes/<unit>/{spec,design,tasks}.md` | ship 后归档 |

## 2. OpenSpec 的核心机制：delta-spec + 机械归并（读源码所得）

源在 `~/Repos/opensource-hub/OpenSpec/docs/concepts.md`。要点：

- **长青层 = 行为契约 spec**，按 domain/能力组织（它明说三种切法都行：by feature area / by component / by bounded context）。格式 = `## Purpose` + `### Requirement:`（SHALL/MUST）+ `#### Scenario:`（Given/When/Then）。
- **每个 change 的 `specs/` 不写全量，只写 delta**：`## ADDED / MODIFIED / REMOVED Requirements`。
- **archive 时 CLI 机械合并**进 canonical：ADDED 追加、MODIFIED 替换、REMOVED 删除。是 `openspec archive` 干的，不是 agent 重写 → 这是它防 rot 的根。
- **design.md 保持 per-change**（technical approach + architecture decisions + data flow + file changes），archive 留痕，**不**并进任何 living design。

它对"spec 该放什么"的 quick test（原文）：
> *If implementation can change without changing externally visible behavior, it likely does not belong in the spec.*

> 本仓采纳其"行为契约长青层 + 收尾归并"思想，但**否决 delta-spec 工件**（用户决定：orchestrator 收尾直接编辑 canonical）。

## 3. 四工具对比：实现后留什么（Martin Fowler 三工具对比 + 各家文档）

| 工具 | merge 后什么留下 | design 寿命 | 耐久项目层 | merge 后 source of truth |
|---|---|---|---|---|
| **Kiro** | 只剩代码，spec 三件套丢弃 | 易逝 | steering（product/tech/structure.md） | **代码** |
| **spec-kit** | per-feature spec 留档（branch-bound），倾向冻结 | 易逝 | constitution（不可变原则） | **代码** |
| **Tessl** | living merged spec（`GENERATED FROM SPEC`） | 揉进 spec 持续演进 | knowledge.md + agents.md | **spec** |
| **OpenSpec** | living canonical spec（delta 归并） | 易逝（归档） | specs/ + AGENTS | **spec** |

两个结论：

- **普世共识**：四家**无一**维护"living 全量 design"。design 一律 per-feature 易逝或揉进 spec。耐久项目层永远是**约定/原则**（steering / constitution / knowledge）。
- **真分歧**：实现后 spec 留不留 → 两派。"代码即真相"（Kiro / spec-kit 默认）vs "spec 即活真相"（Tessl / OpenSpec）。

## 4. 关键观察：撞上 fragmentation 的人都在向"活 spec"收敛

spec-kit 官方 Discussion #1804：维护者主张"spec 冻结、改动开新编号 spec"；规模用户顶回去——*"答案散在三个 spec 里，得按顺序读、脑内合并出还 current 的部分"*。社区自发解法是 **reconciliation + 归档进中心 living `.specify/memory/spec.md`**——等于把 OpenSpec 的 delta-归并重新发明一遍。

→ 默认是"代码即真相"，但**撞上规模的都在往 living-merged-spec 去**。本仓用户最初痛点（"只有个简单的全量 SPEC.md"）正是 fragmentation，故应选 living-merge 派。

## 5. 普世警告：living spec 也会 drift，必须配强制闸

业界共识：*static specs fail，stale spec 会理直气壮误导 agent*。解药不是靠自觉，而是**自动强制**（spec 与代码背离时测试就挂）+ **在固定 transition point 复核**。本仓对应：收尾归并 + spec-vs-code 校验闸。

## 6. 放什么 / 不放什么（arc42 + C4 印证）

- arc42："只记录架构相关决策""避免冗余文本""别记录代码本身能更好表达的东西""小块文档才好维护"。
- C4：选定一个高度就停（Context→Container→Component→**Code 不维护，由代码承担**）。契约层下钻到"模块一句话职责"即止，不到函数级。
- 判据（两问，都 yes 才进长青层）：① 再过 5 个 unit 还成立吗（稳定）？② 生手读几分钟代码能否自己还原（不可廉价重建）？任一 no → 不进，落代码/注释/ADR/runbook/issue。

| 不进长青 spec 的内容 | 落点 |
|---|---|
| 函数/类名、实现走查 | 代码 + 注释 |
| 当初为什么这么选（决策） | `docs/decisions/` ADR |
| 启停命令、调试 how-to、加 channel 教程 | AGENTS.md / operator-runbook |
| 跨包架构总图、依赖方向、部署 | `SPEC.md`（顶点） |
| 进行中 bug/TODO/迁移笔记 | `docs/changes/` / issue |

## 7. 给「库/内核」写行为契约——消费者是开发者,不是终端用户（专题调研）

终端产品（IM/Gateway/CLI）的"可观察行为"= 人在产品上看到什么。**内核是库**,它没有 UI,"消费者"是经 `agent.sdk` 调用它的两个产品。给库写契约有专门的成熟体系,不必硬套 UI 那一套:

### 7.1 Design by Contract（DbC，Bertrand Meyer / Eiffel）——库契约的经典三元组

一个库函数/方法的行为契约 = **precondition + postcondition + invariant**：

| 元素 | 含义 | 映射到 Given/When/Then |
|---|---|---|
| **Precondition** | 调用方在调用**前**必须满足的（合法输入、所需状态、auth token） | `GIVEN`（前置状态）+ 部分 `WHEN` |
| **Postcondition** | 供应方在执行**后**保证的（返回值、状态、错误码） | `THEN` |
| **Invariant** | 该类/模块**所有实例、任何 public 方法前后**都成立的约束 | 写成独立 `Requirement`（SHALL NOT…） |

定理：*invariant ∧ precondition（调用前）⟹ invariant ∧ postcondition（调用后）*。DbC 明确把"契约即该模块行为的文档"——正是我们要的长青 spec。

→ **内核 Scenario 这样落**：`GIVEN` 写调用方/Kernel 的前置态，`WHEN` 写调用方经 sdk 发起调用，`THEN` 写调用方可观察的结果（返回形态/抛的错/不变量被保住）。跨包分层不变量（`core 不依赖 platform`）写成 invariant 型 `Requirement`。

### 7.2 Consumer-Driven Contracts（CDC / Pact）——契约由"调用方依赖什么"界定

CDC 的核心：**契约是消费者写的**——消费者声明它对供应方"请求/响应结构"的期望,这些期望的集合才是契约。Pact 用 `.given()`（provider state/前置）→ `.uponReceiving()`（调用）→ 期望响应,就是 GWT。

→ **直接回答"内核契约写多全"的问题**：不是把内核整个内部 API 都写进去,而是**只写两个产品经 sdk 真正依赖的那部分**。调用方不依赖的内部能力,不进契约层（它可以变）。这天然防止 kernel spec 滑成"内部实现清单"。

### 7.3 严谨度三档：库该用 spec-anchored（arxiv "From Code to Contract"）

`spec-first` / `spec-anchored` / `spec-as-source` 三档。**SDK/库的甜点是 spec-anchored**：spec 是有文档价值、可验证的契约,但**不要求代码从 spec 全量生成**。正是本仓内核的处境——我们不 regenerate 内核,只维护一份与代码对账的契约 spec。

### 7.4 防 drift（库 spec 专属强化）

业界对 SDK spec 的共识做法:CI 跑 contract test,**实现与 spec 背离则 build 挂**;任何 API 改动**先改 spec**;spec 当核心工件纳入版本控制。→ 落到本仓 = 收尾归并 + spec-vs-code 校验闸（已在 spec.md Requirement）。

### 7.5 提炼给 GUIDE 的硬纪律（内核契约不写歪的关键）

1. **WHEN/THEN 的主语必须是消费者**（产品 / sdk 调用方 / contract 测试）。一旦写成"core 调 platform 的 X"就是实现,踢出去。
2. **每个 Requirement 是一份 pre→post 契约,或一条 invariant**——不是模块清单。
3. **按 CDC 裁剪范围**:只收调用方依赖的对外行为,内部可变部分不进。
4. **spec-anchored**:文档化 + contract-test 验,不追求从 spec 生成代码。

> 这一节的纪律将折进 feat-392 的文档 GUIDE（design 阶段产出）；此处先作为调研依据存档。

## Sources

- Martin Fowler — Understanding SDD: Kiro, spec-kit, Tessl: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
- OpenSpec（本地源码 `~/Repos/opensource-hub/OpenSpec/docs/concepts.md`）: https://github.com/Fission-AI/OpenSpec
- GitHub spec-kit — spec-driven.md: https://github.com/github/spec-kit/blob/main/spec-driven.md
- spec-kit Discussion #1804（keeping spec files canonical / fragmentation）: https://github.com/github/spec-kit/discussions/1804
- spec-kit Discussion #152（Evolving specs）: https://github.com/github/spec-kit/discussions/152
- Kiro Docs — Specs / Steering: https://kiro.dev/docs/specs/ , https://kiro.dev/docs/cli/steering/
- arc42 §9 — Architecture Decisions: https://docs.arc42.org/section-9/
- ADR 范例库: https://github.com/architecture-decision-record/architecture-decision-record
- Augment Code — What SDD gets wrong / Living specs: https://www.augmentcode.com/blog/what-spec-driven-development-gets-wrong
- Design by Contract — Wikipedia / Bertrand Meyer 原始章节: https://en.wikipedia.org/wiki/Design_by_contract , https://se.inf.ethz.ch/~meyer/publications/old/dbc_chapter.pdf
- CMU SEI — API Security through Contract-Driven Programming（pre/post/invariant 映射 API）: https://www.sei.cmu.edu/blog/api-security-through-contract-driven-programming/
- Pact — Consumer-Driven Contracts（consumer 定义契约 / GWT）: https://docs.pact.io/consumer , https://pactflow.io/what-is-consumer-driven-contract-testing/
- arxiv — Spec-Driven Development: From Code to Contract（spec-first / anchored / as-source 三档）: https://arxiv.org/html/2602.00180v1
