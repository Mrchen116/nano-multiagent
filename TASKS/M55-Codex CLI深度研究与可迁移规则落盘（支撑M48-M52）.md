# M55 - Codex CLI深度研究与可迁移规则落盘（支撑M48-M52）

## Milestone Contract
- milestone_id: `M55`
- title: `Codex CLI深度研究与可迁移规则落盘（支撑M48-M52）`
- goal: 继续系统研究 codex CLI 在输入状态机、事件折叠、渲染调度方面的实现细节，沉淀可直接迁移到 nano CLI 的规则与风险清单。
- execution_mode: `parallel`
- use_worktree: `true`
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M55`
- branch: `milestone/M55`
- test_command: `N/A（研究里程碑，仅文档落盘，不改代码）`
- dev_tasks_path: `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`
- allowed_scope:
  - `PROGRESS/**`
  - `TASKS/**`
  - `LOGBOOK.md`
- forbidden_scope:
  - `src/nano_multiagent/core/**`
  - `src/nano_multiagent/server/**`
  - `src/nano_multiagent/agent/**`
  - `src/nano_multiagent/runs/**`
  - `src/nano_multiagent/tools/**`
- prevention_rules:
  - 仅做研究文档，不做实现代码改动。
  - 不改内核设计蓝图，仅作为边界参考。
  - 忽略并行里程碑改动，不触碰无关文件。
  - 锚点必须可定位到具体文件与行号。

## Startup Checklist
- [x] 已阅读 `LOGBOOK.md`
- [x] 已阅读 `内核设计蓝图.md`（仅边界参考）
- [x] 已确认分支/工作区：`milestone/M55` @ `.../worktrees/M55`
- [x] 已确认范围约束：仅 `TASKS/PROGRESS/LOGBOOK`

## Roadpoints

### R1 输入状态机/渲染调度锚点补齐
- Acceptance:
  - 补充输入状态机与 popup 同步代码锚点。
  - 补充 frame coalesce/渲染提交调度锚点。
  - 补充 orphan 事件处理锚点。
  - 补充 fallback 去重窗口策略锚点。
  - 每类锚点都给出“对应 nano 迁移影响点”。
- Tests Plan:
  - unit: 不选（无代码变更）。
  - contract: 不选（无契约变更）。
  - integration: 不选（无链路改动）。
  - e2e: 不选（研究线不做运行验收）。
- Expected Artifacts:
  - `PROGRESS/M55-Codex CLI深度研究与可迁移规则落盘（支撑M48-M52）.md` 的锚点矩阵与证据段落。
- DoD:
  - 锚点覆盖四类主题且可检索复核。
  - 对每个主题形成至少 1 条可迁移规则。
- Status: `TODO`

### R2 可执行迁移清单（M48-M52 分配）
- Acceptance:
  - 给出 `M48-M52` 分项迁移清单（目标、落点、优先级、风险）。
  - 明确依赖顺序与并行边界。
  - 每个里程碑至少列出 2 条可执行规则。
  - 标注“可直接做”和“需前置支撑”。
- Tests Plan:
  - unit/contract/integration/e2e: 不选（文档规划输出）。
- Expected Artifacts:
  - `PROGRESS/M55-Codex CLI深度研究与可迁移规则落盘（支撑M48-M52）.md` 的迁移矩阵章节。
- DoD:
  - M48-M52 执行者可直接按清单拆实现 Roadpoint。
- Status: `TODO`

### R3 研究结论沉淀与复用规则更新
- Acceptance:
  - 在 `PROGRESS` 固化结论、风险、回滚边界。
  - 在 `LOGBOOK.md` 追加可复用防回归规则。
  - 输出交付摘要（文件路径、关键锚点、迁移规则摘要）。
- Tests Plan:
  - unit/contract/integration/e2e: 不选（文档变更）。
- Expected Artifacts:
  - `LOGBOOK.md` 新增 M55 规则条目。
  - `PROGRESS/M55-...md` 完整记录。
- DoD:
  - 满足 Exit Criteria 1-4。
- Status: `TODO`
