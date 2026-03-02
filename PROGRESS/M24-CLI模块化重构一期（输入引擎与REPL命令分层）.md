# PROGRESS (Milestone: M24)

- Title: CLI模块化重构一期（输入引擎与REPL命令分层）
- Goal: 拆分 `cli/commands.py`，抽离输入编辑引擎与 REPL 命令路由，同时保持 CLI 行为与 HTTP 契约完全一致。
- Exit Criteria:
  - 输入编辑/历史回填逻辑抽离到独立模块。
  - REPL 命令路由/参数校验抽离到独立模块。
  - `commands.py` 保持薄编排。
  - `pytest -q` 全绿。
- Test command: `pytest -q`
- Branch: `milestone/M24`

### Baseline
- Context:
  - execution_mode=`serial`；`use_worktree=true`；worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M24`；branch=`milestone/M24`。
  - 已读取 `LOGBOOK.md`，沿用：CLI HTTP-only、错误分层输出稳定、命令入口机读兼容。
  - prevention_rules：行为保持不变；不改 runtime/tool/session/llm 核心逻辑；不引入空转发层；每个 Roadpoint 必须 C1/C2/C3。
  - 本 Milestone 边界：仅改 `src/nano_multiagent/cli/**` 与配套 `tests/**`、`TASKS/PROGRESS`，不改 HTTP API 契约语义。
- Decision:
  - 规划两条 Roadpoint：R24.1 抽离输入编辑引擎；R24.2 抽离 REPL 命令路由/校验。
  - 通过“先补结构门禁测试，再迁移实现，再更新文档记录”的小步串行方式执行。
- Rationale:
  - 先固化边界可避免重构中逻辑回流，且每步都能独立回滚与验收。
- Evidence:
  - Tests: `pytest -q`（baseline：`325 passed, 4 skipped`）
  - Entry: 基线全绿，可进入 R24.1 Red。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R24.1 Red：先加输入引擎模块边界测试。
