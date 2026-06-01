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

## 8. 决策的 supersede 链怎么设计（ADR 传承，专题调研）

feat-392 砍掉了独立 `docs/decisions/`（决策留 per-unit `design.md`）。但调研了"决策随时间演化"在 ADR 圈的成熟设计,作为将来 opt-in 的现成模型存档。

### 8.1 status 生命周期（Nygard / MADR 通用）

四态最小集:`Proposed → Accepted → Deprecated / Superseded`。末两态区分:

- **Deprecated**:不再适用,**无替代**(整块功能废了)。
- **Superseded by ADR-NNNN**:被更新的 ADR **替换**;`NNNN` 让链**可前向追溯**。

### 8.2 不可变 + 唯一允许的改动

铁律:ADR 一旦 `accepted` **不再编辑**。改主意 → **新写一条**去 supersede 旧的。对旧 ADR **只允许动 status 行**(加 `Superseded by ADR-NNNN`),正文一字不改——保住"当初怎么想"的历史。

### 8.3 双向链

```
ADR-0005（新）:  Supersedes ADR-0001       ← 后向:我替换了谁
ADR-0001（旧）:  Superseded by ADR-0005    ← 前向:我被谁替换
```

两向都写 → 既能从旧往前查"被谁取代",也能从新往后查"推翻了啥",不必翻 git 历史。

### 8.4 工具自动化（adr-tools, Nat Pryce）

`adr new -s 9 "标题"`:建新 ADR 标记 supersede #9,**并自动改 #9 的 status 指向新的**。v2.1.0 起一条可 supersede 多条;通用 `adr link` 随时加任意关系。

### 8.5 这套成立的两个前提（= 为什么 per-unit design.md 挂不了链）

① **稳定全局 ID**(ADR-0001);② 在不可变记录上留**一个可变字段(status)**。per-unit `design.md` 两个都不干净:ID 是 unit 内局部(`决策 1/2/3`),且文件冻结归档。**这正是 ADR 圈维护一层薄 decisions 的真正原因——不是为内容,是为给决策稳定 ID + 可变 status。** 真要挂链,最小补法 = 加一张薄索引,**不是重写内容**。

## 9. SDD 各家怎么处理决策 / ADR（专题调研）

回答"前面调研的 SDD 工具是否也做 supersede 链"——**不,这是两条不同传承,被拼成可选挂件**。

### 9.1 两条传承

- **SDD 工具默认流**:决策待在 per-feature/per-change 的 `design.md`,**易逝**(归档即逝)。**无 supersede 链。** —— 跟本仓 per-unit `design.md` 现状一致。
- **supersede 链来自独立的 ADR 传承**(Nygard/adr-tools/MADR),另一个更老的圈子。

### 9.2 各家拼法（都做成可选挂件,且都印证"durable 决策须在变更稿之外")

| 工具 | 决策默认在哪 | durable + 链怎么办 |
|---|---|---|
| **OpenSpec** | per-change `design.md`,归档即逝 | **可选 schema `spec-driven-with-adr`**:ADR 工件**放在 change 之外、`openspec/` 之外**,归档后仍持久 |
| **Kiro** | per-feature `design.md` | 通过 **steering** 配置让 AI 自动生成 Nygard 式 ADR |
| **spec-kit** | per-feature `plan.md` | 耐久层是 **constitution（不可变原则）**,无 ADR 链 |

### 9.3 关键印证 + 摩擦判据

OpenSpec 的 ADR 必须**活在 change 之外、归档后仍持久**——正是"决策要 durable+挂链就得有独立于易逝变更稿的持久层"。生态对"为什么大家不维护 ADR"的诊断很尖锐:*纯粹是摩擦——能被记下的往往是设计期 upfront 的决策,实现中途冒出来的同样重要的决策反而漏了*。→ 依据:要么做得极廉价,要么别做。

### 9.4 回扣 feat-392 的决定

砍 `docs/decisions/` = **选了 OpenSpec 默认 schema(不带 adr),决策留 per-unit design.md**,是 SDD **主流默认**,非另类。supersede 链是**有现成模型的 opt-in 挂件**(OpenSpec `spec-driven-with-adr` / Kiro steering),需要时按 §8.5 最小补法接入即可。**一句话:他们默认也不做链;做的人都当作 change 之外的可选持久层——本仓跟随默认,留好 opt-in 口子。**

## 10. 把 Requirement 绑到测试——业界三种做法（专题调研）

"绑定" = 在 spec 里写一条规矩,旁边注明"这条由哪个测试把守",让规矩有可执行的牙。业界从浅到深三种:

### 10.1 RTM 内联（需求可追溯矩阵,最轻）—— 本仓采纳

经典 QA 做法:一张 **Requirement ID ↔ Test ID** 的映射(前向证明覆盖 + 后向)。落到 spec 里 = 每条 Requirement 注一行指向验它的测试。
- 缺点:手维护的 RTM 自身会 rot / 变形式主义 → 本仓用 freshness 检查补这颗牙(见下)。

### 10.2 Kiro（现代 SDD,自动生成 + 可导航）

EARS 需求(`WHEN…THE SYSTEM SHALL…`)→ 工具抽取可测的 "property" → **自动生成** property-based 测试 → 并让你**从需求文本直接跳到验它的测试**。
- 缺点:依赖 Kiro 那套自动抽取/生成器,本仓没有也不造。"可导航"理念可借。

### 10.3 BDD / Gherkin / Cucumber（最深,散文即测试）

**Scenario 文本本身就是测试**:Given/When/Then 每步绑一个 step definition(代码),执行时把散文翻成对系统的操作。spec=living doc=test 同一工件,无"覆盖:"行。`@req-id` 标签做关联。
- 缺点:要上 `pytest-bdd` + 给每条 Scenario 写胶水,所有 Scenario(含没法单测的行为/UI 类)被拽进 BDD 框架,过重。

### 10.4 本仓选型 + 具体例子

取最轻的 **RTM 内联**(复用现有 `tests/contract/`,零新基建),再补 Gherkin/RTM 各自缺的牙:`[可执行]` Req 挂 `覆盖:` 指向已存在的断言;freshness 检查保证引用非悬空。

真实例子(本仓现成规矩 + 现成测试):

```markdown
### Requirement: 产品只能走 agent.sdk,不能碰内核内部   [可执行]
覆盖: tests/contract/test_core_no_platform_imports.py
#### Scenario: 产品越界 import 被拦
- 当 coding_cli 里写了 import agent.core.runtime
- 那么上面那个测试会失败
```

**两个红灯**:
1. 代码违规(coding_cli 真去 import 内核内部)→ 跑 pytest,该测试红 → 挡住。规矩有牙。
2. 测试消失(被删/改名)→ freshness 检查发现 `覆盖:` 指向空气 → 红 → 逼修。链不会静默 rot。

| 做法 | 绑定深度 | 要不要新基建 | 适配 |
|---|---|---|---|
| RTM 内联 `覆盖:` | 浅(指针) | 零,复用 pytest | ✅ |
| Kiro property+导航 | 中 | 要自动生成器 | ✗ |
| Gherkin 全绑 | 深(散文即测试) | 要 pytest-bdd + 全量 step | ✗ 过重 |

> 反向可选:测试 docstring 里写 `# Req: kernel/产品只能走 agent.sdk`,支持从测试回查需求。

### 10.5 OpenSpec 怎么做（本地源码核实）

源:`~/Repos/opensource-hub/OpenSpec/openspec/specs/opsx-verify-skill/spec.md`。

**OpenSpec 不在 spec 里写任何声明式的 scenario↔test 链。** 它靠一个 `/opsx:verify` 命令,实现完跑它,**agent 现场对账**:

- 对每条 Requirement → 搜代码里的实现,指认文件/行,判断是否满足。
- 对每条 Scenario → "检查是否存在覆盖该 scenario 的测试",报告覆盖状态(真实输出:`⚠ Scenario "..." has no test coverage`)。
- 实现与 spec 不符 → 报 **WARNING**,建议改实现或改 spec。

即 OpenSpec 是**软对账**:agent 每次现场搜 + 出报告(advisory),**没有机械硬绑定、不出红测**。这等于本仓的 reviewer 旅程 + design grounding 那一层(靠 agent 判断)。

**对比本仓选型**:

| | OpenSpec | 本仓 RTM 内联 |
|---|---|---|
| spec 里声明链 | 无 | 有 `覆盖: test_xxx` |
| 谁判覆盖 | agent 现场搜 | 机器(freshness 查引用) |
| 结果 | 报告(WARNING) | 红测(硬卡) |

→ 印证两轨:`[可执行]` Req 用 `覆盖:`+freshness 硬卡(比 OpenSpec 硬);`[行为]` Req 靠 agent 对账(= OpenSpec 对所有 scenario 的做法)。本仓 = OpenSpec 软对账 + 给能上硬测的部分再加一道机械链。

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
- npryce/adr-tools（supersede 命令 + 自动改旧记录 status）: https://github.com/npryce/adr-tools
- MADR — Markdown ADR（status 生命周期 proposed/accepted/deprecated/superseded）: https://adr.github.io/madr/
- joelparkerhenderson/architecture-decision-record（ADR 模板库）: https://github.com/joelparkerhenderson/architecture-decision-record
- EventCatalog — ADRs 双向链: https://www.eventcatalog.dev/blog/introducing-adrs
- Martin Fowler — Architecture Decision Record: https://martinfowler.com/bliki/ArchitectureDecisionRecord.html
- intent-driven.dev — ADR with OpenSpec（`spec-driven-with-adr` schema,ADR 在 change 之外持久）: https://intent-driven.dev/blog/2026/04/29/spec-driven-development-with-adr/
- doit.com — SDD with Kiro: who owns the decisions（steering 配置 ADR、摩擦判据）: https://www.doit.com/blog/your-ai-writes-the-code-who-owns-the-decisions
