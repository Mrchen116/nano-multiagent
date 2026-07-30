# 仓库文档地图

本文是 nano-multiagent 全仓文档的顶层索引。它说明重要文档在哪里、分别负责什么、当前变更与长期事实如何区分，以及发生冲突时应核对哪一类来源。

## 从哪里开始

| 任务 | 先读 |
|---|---|
| 第一次了解项目 | [`../README.md`](../README.md) → [`../SPEC.md`](../SPEC.md) → 相关包的 [`specs/`](specs/README.md) |
| 理解产品定位、目标用户或稳定体验原则 | [`product/`](product/README.md) |
| 修改跨包职责、依赖方向或部署拓扑 | [`../SPEC.md`](../SPEC.md) |
| 修改用户或外部消费者可观察行为 | 相关包的 [`specs/`](specs/README.md) → [`development/change-workflow.md`](development/change-workflow.md) |
| 编写或归并行为契约 | [`SPEC_GUIDE.md`](SPEC_GUIDE.md) → [`specs/README.md`](specs/README.md) |
| 判断是否建立 unit、选择 Full/Bugfix lite、查看阶段和门禁 | [`development/change-workflow.md`](development/change-workflow.md) |
| 查 change unit 的目录、命名、文件归属或归档位置 | [`changes/readme.md`](changes/readme.md) |
| 跟踪本次 Agent-Native 仓库知识体系迁移 | [`refactor-486 plan`](changes/refactor-486-agent-native-repository-knowledge-system/plan.md)（Active Work，不覆盖 current） |
| 配置开发环境、运行测试或开发 CLI/前端 | [`development/`](development/README.md) |
| 启动、调试或恢复服务 | [`operations/`](operations/README.md) |
| 在 worktree 内运行真实服务或关键路径 E2E | [`development/worktree-runtime.md`](development/worktree-runtime.md) → [`development/e2e-critical-paths.md`](development/e2e-critical-paths.md) |
| 查某个变更为什么这样设计 | 活动区或历史区的 [`changes/`](changes/readme.md) unit |
| 查 LLM 交互日志或本地参考项目 | [`../AGENTS.md`](../AGENTS.md#project-overview) |
| 查外部项目比较、脑暴或阶段性审查 | 对应研究材料；先核对日期、代码基线和当前权威，不能直接当作 current |

## 当前权威分工

同一类长期事实只在一个位置写全，其他文档保留必要摘要并链接到它。

| 要回答的问题 | 权威位置 | 说明 |
|---|---|---|
| 产品是什么、如何最短启动 | [`../README.md`](../README.md) | 面向使用者的产品入口 |
| 产品定位、目标用户和跨版本体验原则是什么 | [`product/`](product/README.md) | 产品 Truth 入口 |
| 顶层包如何分工、允许怎样依赖、如何部署 | [`../SPEC.md`](../SPEC.md) | 跨包架构与不变量 |
| 单包当前应该表现为什么 | [`specs/<package>/`](specs/README.md) | current 行为契约 |
| 长青 spec 如何编写、delta-spec 如何归并 | [`SPEC_GUIDE.md`](SPEC_GUIDE.md) | 契约层内容规则 |
| change unit 如何选择、推进，经过哪些角色和门禁 | [`development/change-workflow.md`](development/change-workflow.md) | 当前开发变更生命周期 |
| change unit 如何命名，文件放在哪里、由谁维护和归档 | [`changes/readme.md`](changes/readme.md) | unit 存储与文件归属 |
| 开发流程、环境、测试和联调文档如何进入 | [`development/`](development/README.md) | 开发任务地图 |
| 本地环境如何安装、常用命令和提交格式是什么 | [`development/local-development.md`](development/local-development.md) | 开发者本地入口 |
| worktree 内如何隔离启动真实服务并完成清理 | [`development/worktree-runtime.md`](development/worktree-runtime.md) | 临时端口、config、进程、数据和绑定隔离 |
| 测试如何分层、什么值得进入长期测试 | [`development/testing.md`](development/testing.md) | 测试规范 |
| 哪些真实用户旅程必须长期守护 | [`development/e2e-critical-paths.md`](development/e2e-critical-paths.md) | 关键路径与 E2E 对账 |
| 服务如何启动、观察、恢复和排障 | [`operations/`](operations/README.md) | 按任务进入主链路、Gateway 或排障文档 |
| LLM provider、本地代理与交互日志如何联调 | [`development/llm-integration.md`](development/llm-integration.md) | 模型与代理入口 |
| 注释和 docstring 如何编写 | [`development/commenting.md`](development/commenting.md) | 代码注释规范 |
| Agent 开始任务前必须知道什么 | [`../AGENTS.md`](../AGENTS.md) | 仓库级指令、关键入口与运行约束 |

## 文档状态

| 状态 | 位置 | 如何使用 |
|---|---|---|
| Current | `SPEC.md`、`docs/specs/`、现行开发规范与操作手册 | 描述当前仍成立的架构、行为和工作方式 |
| Active / Proposed | `docs/changes/<unit>/` | 描述正在讨论、设计或实施的目标状态；完成前不能覆盖 current |
| Completed history | `docs/changes/archive/<unit>/` | 解释已完成变更的需求、设计、实施与验收过程 |
| Retired | `docs/archive/` | 保存已被 current 文档取代的独立旧文档 |
| Research snapshot | `docs/tools-diff-cc/`、`docs/kernel-diff-cc/`、`docs/brainstorms/` 等 | 提供特定时间和基线下的研究证据 |
| Local / runtime | 本机配置、日志、PID、数据库、截图和临时运行目录 | 只服务当前机器或单次运行，不作为仓库长期规范 |

## 冲突怎么处理

1. 先确认问题属于跨包架构、单包行为、开发流程、运行操作还是历史解释，再读取该问题对应的权威位置。
2. 活动 change unit 描述未来目标。只有实现、验证并完成 delta-spec 归并后，`docs/specs/` 才成为新的 current。
3. 归档和研究材料只用于解释历史或提供证据，不能覆盖 current 文档。
4. current 文档与代码、测试或真实运行结果不一致时，把它视为 drift：查清预期和实现后修正文档或代码，不能默认任选一方为准。

## 现有背景与历史材料

| 位置 | 当前作用 |
|---|---|
| [`product/`](product/README.md) | 产品定位与稳定体验原则；原始需求稿和蓝图从该入口进入 archive |
| [`IM-user-stream-migration-plan.md`](IM-user-stream-migration-plan.md) | 已实施迁移的历史计划 |
| [`spec-implementation-conflicts.md`](spec-implementation-conflicts.md) | 一次 spec/code drift 审计 |
| [`内核设计细化/`](内核设计细化/) | 内核实现层参考 |
| [`tools-diff-cc/`](tools-diff-cc/)、[`kernel-diff-cc/`](kernel-diff-cc/) | 外部实现比较快照 |
| [`brainstorms/`](brainstorms/) | 脑暴与阶段性方案材料 |
| [`archive/`](archive/) | 已退役独立文档 |

根目录的 `LOGBOOK.md`、`ROADMAP.md`、`TASKS.md`、`PROGRESS.md` 以及 `TASKS/`、`PROGRESS/`、`ACCEPTANCE/` 属于旧开发记录体系。新 change 的工作状态和证据写入 `docs/changes/<unit>/`；迁移完成前保留旧记录用于取证，但不要据目录位置或更新时间猜测它是否仍然有效。

## 维护规则

- 新增长期文档时，在本文或对应子目录入口中增加链接和一句用途说明。
- 已有权威位置的事实，其他文档只保留必要摘要和链接，不复制完整正文。
- 移动或退役 current 文档时，同一变更内更新所有 live 入口。
- 变更完成时，把验证后的长期行为归并进 current 文档；change unit 随后冻结为历史。
- 文档中的命令优先指向仓库脚本，避免散文步骤与脚本形成两套流程。
