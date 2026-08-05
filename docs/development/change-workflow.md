# Change Workflow

本文记录 nano-multiagent 当前的开发变更生命周期，负责说明什么时候建立 change unit、Full、Bugfix lite 与快速开发如何选择、实施方式如何选择、各阶段怎样流转，以及每类 unit 需要经过哪些门禁。

各 `change-*` skill 负责角色内部的具体执行方法；[`../changes/README.md`](../changes/README.md) 负责 unit 的目录、命名、文件归属和归档位置。

## 什么时候不建 unit

以下小修可以直接修改、验证和提交：

- 单文件、无行为变化、无设计决策的 typo、注释、常量值、配置目录路径或日志级别调整；
- 纯重命名、局部 inline 或删除死代码；
- 已合并 unit 的内部清洁，使用 `chore` commit 并关联原 unit。

判据是能否写出有意义的首文档：如果没有用户视角的需求、问题、架构动机或性能目标需要对齐，就不建立 unit。用户能够感知到错误行为时，建立 bugfix unit。

## Full、Bugfix lite 与快速开发

| 路径 | 适用条件 | 首文档 | 省略的阶段 |
|---|---|---|---|
| Bugfix lite | 单 milestone、影响面小、无独立设计决策、不需要独立回归矩阵的 bugfix | `fix.md` | 独立 design、verifier、产品 reviewer |
| Full | feat、refactor、perf；或跨多个 milestone、需要独立回归矩阵、根因横跨多个模块的 bugfix | `spec.md`、`motivation.md` 或 `incident.md` | 不省略下述 Full 门禁 |
| 快速开发 | 用户明确选择边对齐、边实现、边测试，并在实现后补齐正式记录 | 实现后补 `spec.md`、`motivation.md` 或 `incident.md`，以及 as-built `design.md` | 事前 Gate 1/2、orchestrator/worker、verifier、产品 reviewer |

Bugfix 默认选择 lite；实施前发现影响面扩大时升级为 Full。快速开发必须由用户明确选择，Agent 不能因为想减少文档或门禁而自行切换。

## 总流程

```text
Full
  change-spec-author
    ├─ change-spec-reviewer（可选）
    └─ change-design-author
         → R1 创建独立 change-design-reviewer
         → 后续轮次复用同一 reviewer
         → 选择实施方式
            ├─ 原流程：change-orchestrator → change-impl-worker(s)
            └─ 用户点名简化流程：change-orchestrator-simple → 自主组织实现
         → 对应 validation gates
         → canonical spec 归并
         → 本地 CI
         → archive
         → PR + 远端 CI

Bugfix lite
  change-spec-author（fix.md 前两段）
    → 选择实施方式
       ├─ 原流程：change-orchestrator → 单个 change-impl-worker
       └─ 用户点名简化流程：change-orchestrator-simple → 自主实施单个 M1-fix
    → change-code-review
    → 必要的 canonical spec 归并
    → 本地 CI
    → archive
    → PR + 远端 CI

快速开发
  用户与 Agent 持续对齐、实现和测试
    → 用户亲自测试并确认结果
    → change-fast-close
       → 建立 unit，补首文档、as-built design 与必要的 delta-spec
       → change-code-review
       → canonical spec 归并
       → 本地 CI
       → archive
       → 按用户授权提交、push 或创建 PR
```

`change-retro` 是完成后的可选取证流程，不属于交付门禁。

## 快速开发模式

快速开发适合用户希望在同一段交互中持续给反馈、Agent 持续修改、用户直接体验结果的工作。它改变的是 change 文档形成的时间：实现可以先发生，交付前仍要把最终用户意图、实际设计、契约变化和 code review 结果写回仓库。

这条路径遵守以下约束：

- 只有用户可以明确选择快速开发；未选择时仍按 Full 或 Bugfix lite 判断；
- 首文档来自原始对话和用户决定，不能只根据最终代码反推需求；
- `design.md` 是标明事后形成的 as-built design，必须以实际代码、diff、测试和已确认决策为依据；
- 不补造没有发生过的 milestone、`tasks.md`、`progress.md`、design review、verifier 或产品 reviewer 记录；
- 用户亲自测试并确认结果后才能进入 `change-fast-close`；本路径不再重复产品验收；
- `change-code-review` 是唯一独立质量门禁；review 修复改变用户可观察行为时，用户需要重新确认受影响旅程；
- 收尾未完成或用户尚未确认时，unit 保持 active。

`change-fast-close` 负责锁定现有 diff、建立事后 unit、回填文档、执行 code review、归并 canonical spec 并按用户授权交付。

## 阶段 1：首文档

`change-spec-author` 与用户收口“做什么”或“出了什么问题”，产出 `spec.md`、`motivation.md`、`incident.md`，或 lite 路径的 `fix.md`。

门禁 1 通过要求：

- 原始需求和澄清记录保真；
- 用户场景、范围与非目标已经收口；
- Requirement/Scenario 只描述用户或消费者可观察结果；
- bugfix 的 RCA 已到达根因；
- 文档没有模板注释、TBD 或待澄清项。

`change-spec-reviewer` 是可选的独立复核：用户明确要求 review，或 author 希望独立复核时调用。它不是 Full 流程的默认强制门禁，`change-design-author` 的启动不依赖 `spec-review.md`。

Bugfix lite 在 `fix.md` 的“现象/复现”和“根因”两段完成后直接进入实施；“修复”和“验证”由选定的实施流程回填。

## 阶段 2：设计

Full unit 由 `change-design-author` 基于首文档、current specs 和真实代码产出：

- `design.md`，包括现状、关键决策、接口与数据流、风险和回退；
- 前端相关 unit 的 `prototype.html`；
- 面向 canonical specs 的 delta-spec；
- milestone 表和仅含 `.gitkeep` 的 milestone 目录骨架。

`tasks.md` 和 `progress.md` 不在设计阶段预填，由 worker 进入自己的 worktree、完成探索后创建。

### 门禁 2：独立设计审查闭环

一个 unit 的 Gate 2 使用同一个独立 `change-design-reviewer`：

1. 没有历史 Round 时创建独立 reviewer，R1 必须做 `full` review。
2. author 核实 findings、记录 Author Resolutions 并修订受审内容。
3. 后续轮次唤醒同一 reviewer，由 reviewer 根据实际改动选择 `closure`、`delta` 或 `full`。
4. 所有轮次按时间追加到同一个 `design-review.md`，不得覆盖旧 Round。

门禁 2 通过必须同时满足：

- 最后一个完整 Round 为 `Approved`；
- `0 CRITICAL / 0 WARNING`；
- author 核实所有 findings 和 recommendations 后确认没有实质问题；
- 最后一轮结束后，首文档、design、delta-spec、prototype 和 milestone 骨架没有再变化。

历史 reviewer 只有在客观无法恢复时才允许 failover；替代 reviewer 的首轮必须重新做 `full` review，并记录原因和 reviewer 标识。

## 阶段 3：实施

Full unit 在 Gate 2 通过后、Bugfix lite 在首文档收口后，均有两种实施方式：

| 实施方式 | 触发条件 | 实施组织 | 固定交付要求 |
|---|---|---|---|
| 原流程 | 默认 | `change-orchestrator` 建立 unit worktree；Full 按 milestone 派发 worker，Bugfix lite 派发单个 worker | 完成全部 milestone、适用门禁、契约归并、归档和 PR/CI |
| 简化流程 | 用户点名 `$change-orchestrator-simple` | 在一个 unit worktree 内端到端负责，自主决定直接实现或使用 subagent，不强制 worker、milestone worktree、roadpoint 或过程台账 | 完成全部 milestone、适用门禁、契约归并、归档和 PR/CI |

两种方式共享各自已经确认的首文档、milestone 目标和工程质量底线；Full 额外共享已通过 Gate 2 的 design。选择简化流程只改变实施组织，不改变需求、设计和交付标准。Bugfix lite 在两种方式下都保持唯一的 `M1-fix`。

原流程的每个 milestone：

- worker 删除 `.gitkeep`，创建并维护 `tasks.md`、`progress.md` 和需要的 `evidence/`；
- 按 roadpoint 执行 Red/Verify → Green，并先跑最窄验证；
- 只修改 milestone 范围内的文件；
- 在自己的 worktree 提交，完成后由 orchestrator 合入 unit 分支。

实施中发现 design 错误、遗漏或无法执行时，worker 必须暂停编码，在 `progress.md` 记录修订原因和影响，同步 design 后通知 orchestrator。orchestrator 决定继续、复审或返回 design/spec 阶段，不能让 worker 静默绕过已经确认的方案。

原流程的 milestone 退出标准、tasks、progress 和 evidence 齐全，简化流程的 milestone 退出标准和实际证据可逐条复核，并已统一落在 unit 分支后，进入验收阶段。

## 阶段 4：selected validation gates

| Unit 类型 | `change-verifier` | `change-reviewer` | `change-code-review` |
|---|---:|---:|---:|
| Full，存在用户可观察旅程 | 必须 | 必须 | 必须 |
| Full，零用户面 | 必须 | 跳过 | 必须 |
| Bugfix lite | 跳过 | 跳过 | 必须 |
| 快速开发 | 跳过 | 跳过；使用已记录的用户验收 | 必须 |

Full 和 Bugfix lite 的门禁组合同时适用于原流程和简化流程。

- verifier 核对实现是否完整、正确且与 spec、design、milestone 一致；原流程同时核对 tasks/progress，简化流程核对实际存在的实施记录；
- reviewer 走真实产品旅程，只验用户可观察结果；
- code review 审查 unit diff；
- 原流程的门禁发现问题后由 `change-orchestrator` 判真并派 worker 修复；
- 简化流程的门禁发现问题后由 `change-orchestrator-simple` 判真并自主组织修复；
- 快速开发的 code review 发现问题后，由执行 `change-fast-close` 的主会话判真和修复；
- 修复后按变更范围重跑、局部复验或保留仍然有效的门禁结论；快速开发的修复改变用户可观察行为时交回用户确认。

### 真实验收的测试动作授权

用户启动 change unit 或要求真实验收，即已授权为验证该 unit 所必需的普通外部写入，但范围仅限已经配置好的专用测试 Bot、测试会话/群聊和隔离 runtime。这项预授权已经满足消息发送类 tool/skill 的确认前置；执行者不得再为单条测试消息、临时测试群创建或仅测试用途的成员变更暂停并重复询问用户，而应在验收证据中记录实际目标和结果。

生产或身份不明的接收方、非测试数据、面向广泛受众的通知、付款、重要数据删除或其他不可恢复的外部动作不在预授权范围内，仍须重新获得用户授权。

所有适用门禁通过后才能收尾。

## 收尾

原流程由 `change-orchestrator` 收尾，简化流程由 `change-orchestrator-simple` 收尾，均按以下顺序完成交付：

1. 同步最新 `origin/main`，比较 main 增量对 reviewer、verifier 和 code review 验证范围的影响；每道闸必须重跑、局部复验或记录 retained 依据，不能用“rebase 无冲突”或 CI 代替失效判断。
2. 在门禁对最终集成树仍然有效后，根据实际实现校正 delta-spec。Full unit 由 `change-verifier` 对校正结果逐条核对实现与测试，通过后归并到 `docs/specs/<package>/<area>.md`；Bugfix lite 触及对外行为但没有 delta 时由当前实施流程补齐并直接归并。
3. 按当前 CI 配置运行本地等价检查；归档前再次判断门禁后新增提交和 main 推进是否使结论失效。
4. 将整个 unit 从 `docs/changes/<unit>/` 移入 `docs/changes/archive/<unit>/`。
5. 创建 PR 并等待远端 CI；CI 或 review 小修改变代码后，重新执行受影响门禁。

CI 全绿后收尾 owner 交棒，由人审查和 merge。归档表示 unit 已达到可交付状态，不表示 PR 已合并。

每次实际执行门禁都记录 `validated_at`（实际核对的 unit tree）和 `executed_base`（执行时的 main）；最终 sync 后再记录 `effective_base` 和 `effective_through`。PR 必须同时展示这些值，区分“在哪里真正执行过”和“经过失效判断后结论有效到哪里”。开放 PR 后若再次同步 main，重新执行同一套门禁失效判断。

快速开发由 `change-fast-close` 收尾，继续使用已经记录的用户验收，不补 verifier 或产品 reviewer。若交付时需要在 code review 或用户确认后同步 main，同样必须判断 main 增量是否使 code review 或用户验收失效；内部变化重跑 code review，用户可观察行为可能变化时交回用户确认。

开放 PR 的同一交付会话可以继续处理自包含小修。会话退出后，恢复前必须核对 unit branch、PR head 和 clean worktree；需要修改 design 或新增 milestone 的反馈交由人判断，不能在 archive 中启动第二套生命周期。

## 角色边界

| 角色 | 负责 | 不负责 |
|---|---|---|
| `change-spec-author` | 用户意图、范围、验收标准、RCA | 技术方案、代码 |
| `change-spec-reviewer` | 按需独立复核首文档质量 | 修改首文档、审实现、充当默认门禁 |
| `change-design-author` | 现状 grounding、方案、delta-spec、milestone | 产品代码 |
| `change-design-reviewer` | 独立审查设计，并在同一上下文中完成后续轮次 | 修改方案或实现 |
| `change-orchestrator` | sync、调度、判真、门禁、契约归并、归档和 PR/CI | 实现 milestone |
| `change-orchestrator-simple` | 在 unit worktree 内自主组织实现，并负责适用门禁、契约归并、归档和 PR/CI | 改写已经确认的需求、设计或交付标准 |
| `change-impl-worker` | 单 milestone 实现、测试、任务记录和证据 | 擅自改写需求或绕过设计 |
| `change-fast-close` | 为已完成的快速开发 diff 补 unit、as-built design、用户验收记录、code review、契约归并和归档 | 伪造事前流程、代替用户验收 |
| `change-verifier` | 实现与 spec/design/milestone 的一致性 | 写代码、产品体验判断 |
| `change-reviewer` | 用户旅程和产品可用性 | 写代码、用源码检查替代真实旅程 |
| `change-code-review` | diff correctness 和维护风险 | 直接实施 finding |

## 权威边界

- 本文负责是否建立 unit、Full/Bugfix lite/快速开发路径、实施方式、生命周期、角色组合和门禁选择。
- 每个 `.claude/skills/change-*/SKILL.md` 负责该角色内部的动作、输入输出和恢复细节。
- [`../changes/README.md`](../changes/README.md) 负责 unit 的目录、命名、文件归属和归档位置。
- [`../specs/CONTRIBUTING.md`](../specs/CONTRIBUTING.md) 负责 canonical spec 与 delta-spec 的内容规范。

这些位置发生冲突时暂停流程，先核对已经生效的规则并同步修正文档；不能由 agent 临场选择一份顺手的版本。
