# feat-341: Change Workflow Skills — 技术方案

> 对齐: spec.md v1.0
>
> Unit branch: `unit/feat-341` (will be created by orchestrator,本 unit 是回溯式 spec/design,实际产物已直接落 main)

## Changelog

- 2026-04-30: 回溯式 spec/design 创建。skill 实施先行,spec/design 后补,作为流程自身的第一次 dogfooding。
- 2026-04-30 (M1): 实施期发现 5 处不自洽:目录命名三处打架 / lite 路径在 orchestrator 断裂 / reviewer 派发包字段不一致 / acceptance worktree 多余 / tasks.md 状态词汇不一致。已统一修复(详见各 skill 提交)。
- 2026-04-30 (M1): 加入 design-author §5 "整体自检"节(逐段对齐看不到的全局矛盾,完工前必跑一次)。

---

## 1. 架构总览

```
┌──────────────────────────────────────────────────────────────────────┐
│                       人(User)在三个关键点介入                       │
│                                                                      │
│   立项触发              门禁 1                门禁 2          PR 关口 │
│      │                    │                    │                    │ │
│      ▼                    ▼                    ▼                    ▼ │
│  ┌────────┐  spec.md  ┌────────┐  design.md  ┌──────┐  PR  人 review │
│  │ spec-  │  +        │design- │  +          │orch- │  ─→ + merge   │
│  │ author │  Q&A 收口 │ author │  Milestone  │estra-│       │       │
│  │        │           │        │  表 + 自检   │ tor  │       ▼       │
│  └────────┘           └────────┘             │      │   GitHub      │
│      ↑                    ↑                  │      │   auto-close  │
│      └──── deferred ──────┘                  │      │   关联 issue  │
│           实现层问题口头交接                   │      │               │
│                                              │  ┌───┴───────────┐  │
│                                              │  │  内部派发循环  │  │
│                                              │  │               │  │
│                                              │  │  ┌─────────┐  │  │
│                                              ├──┼→ │ worker  │  │  │
│                                              │  │  │ (并行)  │  │  │
│                                              │  │  └─────────┘  │  │
│                                              │  │       │       │  │
│                                              │  │  ┌────▼────┐  │  │
│                                              ├──┼→ │reviewer │  │  │
│                                              │  │  │ (独立)  │  │  │
│                                              │  │  └─────────┘  │  │
│                                              │  │       │       │  │
│                                              │  │  失败循环路由  │  │
│                                              │  │  fix/issue/   │  │
│                                              │  │  escalate     │  │
│                                              │  └───────────────┘  │
│                                              └──── 提 PR 退出 ─────┘
└──────────────────────────────────────────────────────────────────────┘
```

5 个 skill 各司其职,人在三处插入(立项 / 门禁 1 / 门禁 2),其余阶段全自动;失败循环里只有 escalate 才回人。

### Git 拓扑

```
main
 ├── unit/feat-341 (orchestrator 启动时建,审完 PR merge 后删)
 │    ├── milestone/feat-341-M1   (worker1 worktree, 从 unit/feat-341 拉)
 │    ├── milestone/feat-341-M2   (worker2)
 │    └── ...
 │   reviewer 在 unit/feat-341 上验收
 │   全部通过 → orchestrator 提 PR → 人 review → merge → main
 │
 └── unit/bugfix-200 (orchestrator B 占,与 A 完全隔离)
```

---

## 2. 关键决策

### 决策 1: spec/design 阶段拆 2 个 skill,不合并

- **选择**: 两个独立 skill (`change-spec-author` + `change-design-author`)
- **理由**: spec 和 design 是不同 stance(用户视角 vs 架构视角),一个 skill 同时教 agent 两种态会越界(就是用户原始痛点);skill 边界天然成为 stance 切换点 + 门禁 1。
- **拒绝**: 合并成一个(节省切换但 stance 边界模糊)/ 三件套加 proposal(单人协作冗余)。
- **风险**: 切换时 agent 重读 spec.md 有少量上下文成本——可接受,spec 通常很短。

### 决策 2: 一套 skill 参数化覆盖所有变更类型

- **选择**: spec-author 内部按 type 路由模板(spec/incident/motivation/fix);design-author 通用。
- **理由**: stance 跨类型一致;按类型造 skill 会爆炸(4 类 × 2 阶段 = 8)。
- **拒绝**: 每种类型独立 skill。

### 决策 3: milestone 拆分由 design-author 产出,不另起 skill

- **选择**: design.md Milestone 表 + 空目录骨架,在 design 阶段定型。
- **理由**: 拆分依据(模块/接口/数据流边界)正好是 design 产物;另起 skill 无收益。
- **拒绝**: 由 orchestrator 拆(它接到时已晚)/ 单独的 milestone-planner skill(切换成本)。

### 决策 4: 颗粒度反向门槛,默认单 M1

- **选择**: 默认 1 个 milestone,拆分必须显式举证(跨独立模块可并行 / 工作量超窗口 / 必须分阶段验证)。横切式(model/api/ui)明确禁止。
- **理由**: 老 orchestrator §3.1 默认是"分解",造成小需求过度拆分。反转默认值治这个根。
- **拒绝**: 不指定默认值(agent 一上来就拆)。

### 决策 5: 废弃 dev-tasks.json,git + docs 作为 SoT

- **选择**: 计划在 design.md / 进度在 tasks.md+progress.md / 运行态派生自 git(分支存在/合并)/ 派发包瘦身到 4-5 字段(指针,不是契约)。
- **理由**: 全局调度板易状态分叉,且这套流程一次只跑一个 unit,git 自然就够。
- **拒绝**: 维护 dev-tasks.json(历史包袱:state 分叉、symlink 失效、claim 冲突)。

### 决策 6: unit 集成分支 + Sync Gate + 两级锁

- **选择**: 每个 unit 一根 `unit/<unit_id>` 集成分支;orchestrator/worker 启动都跑 sync gate;merge 时 unit 锁(unit 内多 worker 互斥)+ main 锁(跨 orchestrator 互斥)。
- **理由**: 多 unit 并行天然隔离;sync gate 堵 stale-base 这个反复出现的坑;两级锁分隔不同抢占。
- **拒绝**: milestone 直接合 main(半成品污染 main + 无人审关口)。

### 决策 7: 失败循环三档路由 + revise-design 三道闸

- **选择**: `fix-implementation`(默认,自动派 fix milestone)/ `out-of-unit`(立 issue,blocking 停 unit、major 不停)/ `revise-design`(三道闸:首轮禁用、≥2 轮 fix 失败、必须引 design 段落,任一不过降级 fix)。
- **理由**: design 永远不完美,但 agent 会甩锅,所以默认归因到实现层,升级到 design 必须举证。
- **拒绝**: 让 reviewer 自由判定(易甩锅)/ 只有 fix 一档(忽略 design 真错了的情况)。

### 决策 8: out-of-unit 走 GitHub issue,Closes/Refs 原生关联

- **选择**: reviewer/worker 发现根因不在本 unit 直接 `gh issue create`;unit ↔ issue 关联用 `Closes #N` / `Refs #N`;blocking 立 issue + 停 unit,major 立但不停,minor 不立只记 Side Findings。
- **理由**: GitHub 原生语义验证过几十万项目;issue 是"待决事项队列"的黄金标准。
- **拒绝**: 自建 backlog 文件(无生态)/ 立刻转 sibling unit(过重,且大部分 out-of-unit 不该立刻做)。

### 决策 9: unit→main 走 PR,orchestrator 提完即退出

- **选择**: reviewer pass → orchestrator rebase + push + `gh pr create` → 输出 URL → 退出。不等 CI、不等 merge。PR comments 回归当作 fix-implementation 处理。
- **理由**: PR 是人审最后关口,治 reviewer 失灵;orchestrator 等 merge 是上下文浪费。
- **拒绝**: orchestrator 直接 merge(无人审)/ orchestrator 等 merge(久占资源)。

### 决策 10: design 完成后整体自检(强制)

- **选择**: design-author §5 必跑自检 checklist(spec↔design 对齐 / 内部自洽 / Milestone↔design 对齐 / 与项目既有架构对齐),发现矛盾不静默修补,回头与用户对齐。
- **理由**: 逐段对齐时局部视野看不到的矛盾,自检阶段才暴露(用户的真实痛点)。
- **拒绝**: 跳过自检(把锅留给 worker)。

---

## 3. 接口与数据流

### Skill 间派发包

**worker 派发**(orchestrator → worker):

```yaml
unit_id: <type>-<id>
unit_dir: <type>-<id>[-<short-desc>]
milestone_id: <unit_id>-M<N>
milestone_dir: M<N>-<title>
worktree_dir: <repo_root>/.worktrees/<milestone_id>
branch: milestone/<milestone_id>
mode: full | lite
```

**reviewer 派发**(orchestrator → reviewer):

```yaml
unit_id: <type>-<id>
unit_dir: <type>-<id>[-<short-desc>]
branch: unit/<unit_id>
review_round: 1 | 2 | ...
prior_acceptance_paths: [...]   # 第 2 轮起
mode: full
```

### 文件契约(产物归属)

| 文件 | 谁产出 | 谁消费 |
|---|---|---|
| `<unit_dir>/spec.md` (或 incident/motivation/fix) | spec-author | design-author / worker / reviewer / orchestrator(PR body)|
| `<unit_dir>/design.md` (含 Milestone 表 + Changelog) | design-author + worker(实施期 Changelog) | orchestrator / worker / reviewer |
| `<unit_dir>/M<N>-*/tasks.md` | worker | orchestrator(验收) |
| `<unit_dir>/M<N>-*/progress.md` | worker | orchestrator / reviewer |
| `<unit_dir>/acceptance.md` 或 `regression.md` | reviewer | orchestrator(决定下一步)|
| `<unit_dir>/fix.md` 后两段 | worker(lite 模式) | orchestrator(PR body)|
| `LOGBOOK.md` | worker(沉淀) | 后续 worker(读取) |

### Reviewer 输出契约

- `Highest Required Action`: `pass | fix-implementation | revise-design | out-of-unit`
- 每个 issue: `Severity` + `Recommended Action` + `Action Rationale`(revise-design 必须引段落)
- `gh_issues_filed`: out-of-unit blocking/major 的 issue 号列表
- `verdict`: `pass | fail | pass-with-issues`

### Orchestrator 状态查询(无中间文件)

```bash
git branch --list 'milestone/<unit_id>-M*' --no-merged "unit/<unit_id>"   # RUNNING
git branch --list 'milestone/<unit_id>-M*' --merged "unit/<unit_id>"      # DONE
git worktree list | grep "\.worktrees/<unit_id>-M"                        # 哪些 worker 还在
```

---

## 4. 风险与回退

### 风险

1. **lite 路径绕过 reviewer**:bugfix lite 自报"修好了"无独立验证,小 bug 可能漏。
   - **应对**:lite 默认走;影响面大就升 full;reviewer/PR 关口仍是最终保障。
2. **worker 越界改范围**:`design.md` "范围"列只是软约束,git 不强制。
   - **应对**:worker §0 硬规则要求停手报告越界;orchestrator §3.4 检测到强制 revert。
3. **sync gate 分叉时人没及时介入**:本地与 origin 分叉,orchestrator 停下等人,但人没看到。
   - **应对**:停下时显式输出问题给用户;orchestrator 退出而不是默默卡住。
4. **revise-design 三道闸太严,真 design 错的时候难升级**:可能多走 1-2 轮 fix。
   - **应对**:可接受成本;同 issue 5 轮上限兜底自动升级。
5. **design 自检走过场**:agent 勾选 checklist 但没真查。
   - **应对**:checklist 项措辞具体,并要求"发现矛盾必须停下与用户对齐",没法只勾不报。

### 回退方案

- 任何阶段 user 觉得方向跑偏 → abandon unit(删 `docs/changes/<unit_dir>/` + `git branch -D unit/<unit_id>`)
- orchestrator 一旦升级 escalate → 暂停所有 worker、保留产物、退出,等人接管
- skill 本身有 bug → 各 skill 文件版本受 git 管理,任何一次提交都可 checkout 回滚

---

## 5. Milestones

```mermaid
graph LR
  M1[M1-skill-suite-impl] --> Done[完成]
```

| ID | 标题 | 依赖 | 并行组 | 范围 | 退出标准 |
|---|---|---|---|---|---|
| feat-341-M1 | skill-suite-impl | — | A | `.claude/skills/{change-spec-author,change-design-author,tdd-execution-worker,product-acceptance-reviewer,change-orchestrator}/`、`docs/changes/readme.md`、各 skill `assets/` 模板 | 5 个 skill 文件 + 模板就位、工作流端到端贯通无明显不自洽、用户能至少在一个真实 unit 上启动 spec-author(本 unit 自己就是首个) |

**追溯说明**:本 milestone 在 spec/design 写下来之前已实施完毕(skill 文件、模板、整体自检节都已落 main)。Changelog 段记录了实施期发现并修复的不一致。

后续如果真实试用中发现需要调整(描述触发不准、跨 skill 协作有断点、模板字段冗余等),不在本 unit 内做 fix milestone,而是开新 unit(`feat-342-...` / `bugfix-...`)处理——本 unit 已经超期归档,后续是迭代而非补丁。

---

## 6. 上层文档同步

(本节正常应该由 reviewer 在验收时勾选;追溯式 unit 自查)

- [x] `AGENTS.md` / `CLAUDE.md`:无需更新(skill 套件不改变项目运行时,只改变协作流程;skill 触发由 description 即可,不需要根 CLAUDE.md 介绍)
- [x] `docs/changes/readme.md`:已同步(在前面对话里加了"阶段与门禁"+"Agent 协作分工"+"模板"等节)
- [x] `SPEC.md` / 内核设计 SPEC:无需更新(架构没动)
- [x] 各产品 SPEC:无需更新

---

## 7. Notes

本 unit 的特殊性:它是**流程自己规范自己**的第一次落地。后续每个新 unit 走标准流程时,可以参考本 spec.md / design.md 作为示例。

如果将来要把 skill 升级到 user-level(`~/.claude/skills/`),整 skill 目录搬走即可——assets 自带,无需迁移其他文件。
