# PROGRESS (Milestone: M25)

- Title: CLI模块化重构二期（事件渲染/预算/错误处理分层）
- Goal: 继续拆分 `cli/commands.py`，抽离异步事件消费、预算展示、错误分层映射为可复用模块，保持行为一致。
- Exit Criteria:
  - 抽离 async 事件消费与预览输出模块。
  - 抽离预算快照与阈值提示模块。
  - 抽离错误分层/建议映射模块并保持单命令 JSON 错误契约稳定。
  - `commands.py` 保持薄编排，`pytest -q` 全绿。
- Test command: `pytest -q`
- Branch: `milestone/M25`

### Baseline
- Context:
  - Milestone：`M25`；execution_mode=`serial`；use_worktree=`true`；worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M25`；branch=`milestone/M25`。
  - 允许范围：`src/nano_multiagent/cli/**`、`tests/**`、`TASKS/**`、`PROGRESS/**`、`LOGBOOK.md`、`README.md`、`data/dev-tasks.json`（脚本更新）。
  - 禁止范围：`agent/runtime/tool/session/llm` 核心逻辑；HTTP API 契约行为变更。
  - prevention_rules：行为保持一致；CLI 继续 HTTP-only；单命令 JSON 错误兼容；不引入仅转发层；Roadpoint 必须 C1/C2/C3。
  - LOGBOOK 继承规则：异步事件必须 `event_id` 去重 + `run_id` 过滤；错误分层需 `input/network/runtime`；单命令 JSON 保留 `error/suggestion`。
- Decision:
  - Roadpoints 拆为三段：R25.1 事件模块、R25.2 预算模块、R25.3 错误呈现模块。
  - 采用 Red -> C1 -> Green/Refactor -> C2 -> Docs -> C3 的串行节奏执行。
  - 先用边界测试固定职责归属，再迁移实现，避免重构过程回流。
- Rationale:
  - 模块化拆分降低 `commands.py` 认知负担，同时用现有 CLI 测试网保证无行为漂移。
- Evidence:
  - Tests: `pytest -q`（baseline：`327 passed, 4 skipped`）。
  - Entry: 基线全绿，可进入 R25.1 Red。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R25.1 Red：先加 `repl_events` 模块边界测试并验证红灯。

### R25.1 抽离异步事件消费与预览输出到 `cli/repl_events.py`
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R25.2 抽离预算快照与阈值提示到 `cli/context_budget.py`
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R25.3 抽离错误分层与建议映射到 `cli/error_presenter.py`
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
