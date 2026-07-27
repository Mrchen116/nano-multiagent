# Change Workflow

> **Canonical scope**：本文记录本仓已有的开发变更生命周期，负责“是否建 unit”、Full/Bugfix lite
> 路径、阶段流转、角色组合、门禁选择和完成定义。`change-*` skills 负责各角色内部怎么执行；
> [`../changes/readme.md`](../changes/readme.md) 负责 unit 文件放在哪里。

## 什么时候不建 unit

不是所有改动都需要 change unit。符合下列情形的小修可以直接修改、验证和提交：

- 单文件、无行为变化、无设计决策的小修，例如 typo、注释、常量值、配置目录路径、日志级别；
- 纯重命名、局部 inline 或删除死代码；
- 已合并 unit 的内部清洁，使用 `chore` commit 并在 message 中关联最近的相关 unit。

判据：如果写不出有意义的 `spec.md` / `incident.md`，即没有用户视角的事情要说明，就不建 unit。
如果用户能感知到错误行为，则建立 bugfix unit。

## Unit 路径选择

| 路径 | 判据 | 入口 | 跳过的阶段 |
|---|---|---|---|
| Bugfix lite | 仅 bugfix；单 milestone；影响面小；无独立设计决策；不需要独立回归矩阵 | `change-spec-author` 产 `fix.md` | design、verifier、产品 reviewer |
| Full | feat/refactor/perf；或跨多个 milestone、需要独立回归矩阵、根因横跨多个模块的 bugfix | `change-spec-author` | 不跳过下述 Full 门禁 |

Bugfix 默认走 lite；发现影响面扩大后再升级为 Full。

## 总流程

```text
Full
  change-spec-author
    ├─→ change-spec-reviewer（可选：用户要求，或 author 希望独立复核）
    └─→ change-design-author
          → fresh change-design-reviewer loop
          → change-orchestrator
             → change-impl-worker(s)
             → selected validation gates
             → canonical spec merge
             → archive
             → PR + CI

Bugfix lite
  change-spec-author（fix.md 前两段）
    → change-orchestrator
       → 单个 change-impl-worker
       → change-code-review
       → archive
       → PR + CI
```

`change-retro` 是完成后的可选取证流程，不是交付门禁。

## 阶段 1：探索与首文档

`change-spec-author` 与用户收口“做什么”，产出 `spec.md`、`incident.md`、`motivation.md` 或 lite
路径的 `fix.md`：

- 用户场景、范围/非目标、Requirement/Scenario 或 RCA 已完整；
- Scenario 只写用户/消费者可观察结果，不写内部实现；
- 相关现状和用户点名的参考已经 grounding；
- 文档没有模板注释、TBD 或待澄清项。

### 门禁 1：首文档定稿

作者完成 skill 内的检查并将首文档定稿，即可进入 Full 的 design 阶段；Bugfix lite 直接交给
`change-orchestrator`。

`change-spec-reviewer` 是可选的独立复核，不是默认强制门禁：

- 用户明确要求 review，或 `change-spec-author` 收尾时希望独立复核，才调用它；
- `Issues Found` 时把报告写入 `spec-review.md`，供作者逐条修改；
- `Approved` 可以只在对话中给出台账，不要求落盘；
- `change-design-author` 的启动条件不依赖 `spec-review.md`。

## 阶段 2：设计

`change-design-author` 基于首文档、current specs 和真实代码产出：

- `design.md`：现状、架构、关键决策、接口/数据流、风险与回退；
- 前端相关 unit 的 `prototype.html`；
- 面向 canonical specs 的 delta-spec；
- milestone 表，以及每个 milestone 仅含 `.gitkeep` 的空目录骨架。

`tasks.md` 和 `progress.md` 不在设计阶段预填，由 worker 进入自己的 worktree、完成 explore 后创建。

### 门禁 2：独立设计审查闭环

设计作者必须启动全新、独立的 `change-design-reviewer` 做完整审查。每次修订后都换一个 fresh reviewer
从头复审，不只复查旧 finding。门禁 2 通过必须同时满足：

- 最新 `design-review.md` 为 `Approved`；
- `0 CRITICAL / 0 WARNING`；
- 作者核实所有 findings/recommendations 后认为无实质问题；
- 审查完成后，design、delta-spec、prototype 和 milestone 骨架未再变化。

## 阶段 3：实施

`change-orchestrator` 完成 sync gate，建立 unit 集成分支/worktree，再按 design 的 milestone 表派发
`change-impl-worker`。Bugfix lite 由 orchestrator 创建单个 `M1-fix`。

每个 milestone：

- worker 自行创建并维护 `tasks.md`、`progress.md` 和 `evidence/`；
- 按 roadpoint 做 TDD，先 Red/Verify，再 Green；
- 先跑最窄验证，再扩大验证范围；
- 只在自己的范围和 worktree 内提交；
- 发现 spec/design 偏差时暂停并升级，不能自行改写已确认的需求或设计。

### 门禁 3：实施完成

所有 milestone 的退出标准、实现记录和 evidence 齐全，并已合入 unit 分支后，进入 selected
validation gates。

## 阶段 4：selected validation gates

| Unit 类型 | `change-verifier` | `change-reviewer` | `change-code-review` |
|---|---:|---:|---:|
| Full，存在用户可观察旅程 | 必须 | 必须 | 必须 |
| Full，零用户面 | 必须 | 跳过 | 必须 |
| Bugfix lite | 跳过 | 跳过 | 必须 |

- verifier 核实现与 spec/design/tasks 的 Completeness、Correctness、Coherence。
- reviewer 走真实产品旅程，只验用户可观察结果。
- code review 审查 unit diff；Full 和 Bugfix lite 都必须经过。
- 三类角色只读。发现问题后由 orchestrator 判真、打包，再派 worker 修复；验收角色不得顺手改代码。
- 修复后按受影响范围重跑对应门禁，直到所有 selected gates 有有效通过结论。

## 收尾

门禁通过后由 `change-orchestrator`：

1. 据实际实现校正 delta-spec，并归并到 `docs/specs/<package>/<area>.md`。
2. 核对架构、测试、操作手册和关键 e2e 清单是否需要同步。
3. 跑本地 CI 等价检查。
4. 将整个 unit 从 `docs/changes/<unit>/` 移入 `docs/changes/archive/<unit>/`。
5. 创建 PR 并等待远端 CI；CI/fix 导致代码变化时重新执行受影响门禁。

归档表示 unit 已达到可交付状态，不是删除历史。开放 PR 的同一交付会话可以继续做自包含小修；
会话退出后恢复必须同时验证 branch、PR head 和 clean worktree。需要修改 design 或新增 milestone 的反馈，
必须重新交由人判断，不能在 archive 中启动第二套生命周期。

## 角色与边界

| 角色 | 负责 | 不负责 |
|---|---|---|
| `change-spec-author` | 用户意图、范围、验收标准、RCA | 技术方案、代码 |
| `change-spec-reviewer` | 按需独立复核首文档质量 | 改首文档、查实现、充当默认门禁 |
| `change-design-author` | 现状 grounding、方案、delta-spec、milestone | 写产品代码 |
| `change-design-reviewer` | 独立审查设计事实与质量 | 修改方案或实现 |
| `change-orchestrator` | 调度、判真、门禁、归并、归档、PR/CI | 自己实现 milestone |
| `change-impl-worker` | 单 milestone 实现、测试和证据 | 擅改 spec/design |
| `change-verifier` | 实现对文档的一致性 | 写代码、产品体验判断 |
| `change-reviewer` | 用户旅程和可用性 | 写代码、用源码替代旅程 |
| `change-code-review` | diff correctness 与维护风险 | 直接实施 finding |

## 权威分工与防漂移

- 本文拥有“是否建 unit”、Full/Bugfix lite 路径、阶段、角色组合、门禁选择和完成定义。
- 每个 `SKILL.md` 拥有该角色的详细动作、模板和输入输出契约。
- [`../changes/readme.md`](../changes/readme.md) 拥有 unit 目录、命名、产物归属和归档位置。
- [`../SPEC_GUIDE.md`](../SPEC_GUIDE.md) 拥有 canonical/delta-spec 的内容规范。
- 若 skill 与本文冲突，流程必须暂停，先核对既有意图并同步修正文档，不能由 agent 临场发明新规则。
- 有意修改流程时，必须在同一变更中同步本文、受影响 skills、`docs/changes/readme.md` 和 agent 路由入口。
