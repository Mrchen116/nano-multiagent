# Documentation Map

> 本文是 nano-multiagent **文档体系的唯一顶层索引与冲突裁决入口**。
> 它只声明“哪类事实由哪里负责”，不复制下层文档正文。

## 从哪里开始

| 任务 | 先读 |
|---|---|
| 第一次了解项目 | [`../README.md`](../README.md) → [`../SPEC.md`](../SPEC.md) → 相关包的 [`specs/`](specs/README.md) |
| 配置本地环境、运行测试或前端开发 | [`development/local-development.md`](development/local-development.md) |
| 修改用户可观察行为 | [`development/change-workflow.md`](development/change-workflow.md) → 相关包的 current spec |
| 修改跨包边界或依赖方向 | [`../SPEC.md`](../SPEC.md) → [`development/change-workflow.md`](development/change-workflow.md) |
| 写或归并行为契约 | [`SPEC_GUIDE.md`](SPEC_GUIDE.md) → [`specs/README.md`](specs/README.md) |
| 运行、调试或恢复服务 | [`operator-runbook.md`](operator-runbook.md) |
| 规划 worktree 内真实联调 | [`development/worktree-runtime.md`](development/worktree-runtime.md) → [`e2e-critical-paths.md`](e2e-critical-paths.md) |
| 查一个变更为什么这样设计 | 活动区或历史区的 [`changes/`](changes/readme.md) unit |
| 查本地参考项目或 LLM 日志 | [`../AGENTS.md`](../AGENTS.md#调研与联调入口) |
| 查外部项目比较或阶段性研究 | 研究/蓝图类文档；先确认其基线和状态，不能当作 current 契约 |

## 权威矩阵

同一事实只允许在一个位置写全；其他文档只做摘要并链接到它。

| 事实类型 | Canonical source | 不负责 |
|---|---|---|
| 跨包职责、依赖方向、部署拓扑 | [`../SPEC.md`](../SPEC.md) | 单包具体行为、实现步骤、变更历史 |
| 单包当前对外行为 | [`specs/<package>/`](specs/README.md) | 未来方案、内部实现叙事 |
| 长青 spec 的写法与 delta-spec 归并 | [`SPEC_GUIDE.md`](SPEC_GUIDE.md) | 整个开发生命周期 |
| 是否建立 change unit、Full/Bugfix lite 路径、阶段、角色和门禁选择 | [`development/change-workflow.md`](development/change-workflow.md) | 各角色内部的逐步执行细节 |
| change unit 的目录、命名、产物和归档规则 | [`changes/readme.md`](changes/readme.md) | 开发流程状态机 |
| 各 `change-*` 角色如何执行 | [`.claude/skills/change-*/SKILL.md`](../.claude/skills/) | 擅自改变 workflow 的模式、阶段或门禁 |
| 本地环境、常用命令和提交格式 | [`development/local-development.md`](development/local-development.md) | 服务运行语义、测试分层 |
| LLM 交互日志与本地参考项目路径 | [`../AGENTS.md`](../AGENTS.md#调研与联调入口) | LLM provider 配置、current 行为契约 |
| worktree 服务的端口、config、进程和绑定隔离 | [`development/worktree-runtime.md`](development/worktree-runtime.md) | 主仓正常启动、产品排障 |
| 测试分层与测试文档规范 | [`TESTING_GUIDE.md`](TESTING_GUIDE.md) | 服务操作手册 |
| 必须长期守护的用户旅程 | [`e2e-critical-paths.md`](e2e-critical-paths.md) | 单个 unit 的临时验收证据 |
| 服务启动、重启、健康检查与排障 | [`operator-runbook.md`](operator-runbook.md) | 产品行为契约 |
| LLM provider 与本地代理联调 | [`可用LLM_API与联调说明.md`](可用LLM_API与联调说明.md) | 通用服务运维 |
| 注释与 docstring 约定 | [`../COMMENTING_GUIDE.md`](../COMMENTING_GUIDE.md) | 产品或架构说明 |

### 当前尚未建立的权威

仓库目前没有干净的“产品愿景/产品原则”canonical 层。`需求.md`、`IM前端蓝图.md` 等现有文件在完成
蒸馏前只作为背景材料，不能覆盖 `SPEC.md`、`docs/specs/` 或当前用户对齐结果。后续应把仍然有效的原则
迁入 `docs/product/`，再将原始蓝图转入历史区。

### 现有非 canonical 材料

这些材料仍可用于取证，但必须先回到上面的权威矩阵核对：

| 现有位置 | 当前定位 | 后续整理方向 |
|---|---|---|
| [`需求.md`](需求.md) | 产品背景草稿 | 蒸馏有效原则到 `docs/product/`，原文归档 |
| [`IM前端蓝图.md`](IM前端蓝图.md) | 前端设计快照 | 蒸馏稳定产品原则/行为，原文归档 |
| [`IM-user-stream-migration-plan.md`](IM-user-stream-migration-plan.md) | 已实施迁移计划 | 移入历史区 |
| [`spec-implementation-conflicts.md`](spec-implementation-conflicts.md) | 某次 spec/code drift 审计 | 复核未决项后转 unit 或归档 |
| [`内核设计细化/`](内核设计细化/) | 实现层参考，不是行为契约 | 与代码/spec 对账后决定保留或拆分 |
| [`tools-diff-cc/`](tools-diff-cc/)、[`kernel-diff-cc/`](kernel-diff-cc/) | 外部实现比较快照 | 迁入统一 research 层并补基线 |
| `brainstorms/`、`architecture-reviews/` | 脑暴和阶段性审查 | 迁入统一 research 层并标明状态 |
| [`archive/`](archive/) | 被 current 覆盖的退役独立文档 | 只读保留 |

## 冲突怎么处理

文档不是一条从高到低的总优先级链，而是按事实类型分工：

1. `SPEC.md` 管跨包架构；`docs/specs/` 管单包 current 行为。两者范围不同，冲突代表文档漂移，不能任选一份。
2. `docs/changes/<unit>/` 描述尚未生效的目标状态。它在实现、验证并完成 delta-spec 归并前，不覆盖 current spec。
3. `docs/development/change-workflow.md` 决定 lifecycle、模式与门禁；skill 决定角色内部怎么执行。两者冲突时暂停流程并一起修正，不能由 agent 临场挑选。
4. 归档和研究材料只解释历史或提供证据，永不覆盖 current 文档。
5. current 文档与真实代码/测试不一致时，将其视为 drift：先查清真实行为和预期，再修代码或文档；禁止静默把其中一方当成天然正确。
## 文档生命周期

| 类别 | 路径 | 含义 | 维护方式 |
|---|---|---|---|
| Current | `SPEC.md`, `docs/specs/`, development/operations guides | 当前仍成立的架构、行为与工作方式 | 行为或流程改变时同一变更内更新 |
| Proposed | `docs/changes/<unit>/` | 正在探索、设计或实施的未来状态 | 随 unit 推进，不能冒充 current |
| Completed history | `docs/changes/archive/<unit>/` | 已完成 change 的需求、决策、实施和验收证据 | 只读；开放 PR 的自包含小修除外 |
| Retired | `docs/archive/` | 已被 current 文档取代的独立旧文档 | 保留历史，不继续修订 |
| Research snapshot | comparisons、brainstorms、architecture reviews 等 | 某时间/基线下的分析证据 | 新增或触及时标明状态、日期、代码基线和 canonical 替代项 |
| Local/runtime | 本机配置、日志、截图、PID、临时数据库 | 只对当前机器或一次运行有效 | gitignored；需要长期保留的结论提炼进上述层级 |

### Legacy 根目录

根目录的 `LOGBOOK.md`、`ROADMAP.md`、`TASKS.md`、`PROGRESS.md` 以及 `TASKS/`、`PROGRESS/`、
`ACCEPTANCE/` 属于旧开发控制体系，不再是新工作的权威写入点：

- 新变更状态与证据进入 `docs/changes/<unit>/`。
- 可复用的 current 规则进入架构、spec、development 或 operations 文档。
- 历史材料在后续整理中迁移/归档；在迁移完成前保留原文件，不据目录年龄猜测其状态。

## 各入口的职责

- `README.md`：让用户理解产品并完成最短启动，不承载全仓文档索引。
- `AGENTS.md`：常驻上下文中的硬约束、短路由、LLM 日志和参考项目路径，不承载命令大全、配置样例或操作手册。
- `SPEC.md`：跨包架构地图与不变量，不承载全仓索引。
- 本文：唯一全仓文档地图和 source-of-truth 矩阵。
- 各子目录 `README.md`：只索引该目录，不重新定义顶层权威。

## 维护规则

- 新增一份非 unit 的长期文档时，必须在本文或对应子目录入口中可达。
- 一个事实已有 canonical source 时，其他文档用链接，不复制整段。
- 移动/退役 current 文档时，同一变更内更新所有 live 入口；历史归档中的旧链接可以保留语境。
- 文档中的命令应优先指向仓库脚本；散文步骤不能与脚本形成第二套流程。
- 研究和一次性审查若产生长期规则，必须提炼到 canonical 层，不能只留在报告里等待 agent 猜测。
