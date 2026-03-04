# M55 Codex CLI深度研究与可迁移规则落盘（支撑M48-M52）

日期：2026-03-04  
分支：`milestone/M55`  
工作区：`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55`

## Milestone 启动记录
- Context:
  - 本里程碑定位为“研究线”，只允许文档与规划落盘，不做内核实现改动。
  - 目标是补齐 Codex CLI 在输入状态机、事件折叠、渲染调度上的实现锚点，并转成 nano CLI 可执行迁移规则。
  - 范围限制：仅 `TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`。
- Decision:
  - 采用三路 Roadpoint：`R1 锚点补齐` -> `R2 M48-M52迁移清单` -> `R3 规则沉淀与交付`。
  - `test_command` 记为 `N/A`（文档研究里程碑，无代码与测试门禁变更）。
  - `dev_tasks_path` 使用主仓共享文件：`/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`。
- Rationale:
  - 保持与 tdd-execution-worker 文档化流程一致，同时避免把“研究线”伪装为代码变更里程碑。
  - 先固定锚点证据，再做迁移分配，可减少后续 M48-M52 执行分歧。
- Evidence:
  - 已读：`LOGBOOK.md`、`内核设计蓝图.md`。
  - 已落盘计划：`TASKS/M55-Codex CLI深度研究与可迁移规则落盘（支撑M48-M52）.md`。
- Rollback:
  - 回退到本里程碑计划提交前的最新稳定点。
- Commits:
  - Plan: `TBD`
- Next:
  - 执行 R1：补齐输入状态机、popup 同步、frame coalesce、orphan、fallback 去重窗口的代码锚点矩阵。

## Roadpoint 记录模板

### R1 输入状态机/渲染调度锚点补齐
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `N/A（research-only）`
  - Entry: 文档锚点矩阵可检索复核
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R2 可执行迁移清单（M48-M52 分配）
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `N/A（research-only）`
  - Entry: 迁移矩阵可直接拆分为实现任务
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:

### R3 研究结论沉淀与复用规则更新
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `N/A（research-only）`
  - Entry: PROGRESS + LOGBOOK + 回传摘要齐备
- Rollback:
- Commits: C1=`TBD`, C2=`TBD`, C3=`TBD`
- Next:
