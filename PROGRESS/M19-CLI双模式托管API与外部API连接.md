# PROGRESS (Milestone: M19)

- Title: CLI 双模式：托管API与外部API连接
- Goal: 为 CLI 提供 managed（自动拉起并管理本地 API）与 remote（连接已有 API）两种运行模式。
- Exit Criteria:
  - 新增 managed 模式：CLI 启动时自动启动本地 uvicorn API，并在退出时回收子进程。
  - 新增 remote 模式：CLI 仅连接已有 `--base-url`，不管理服务进程。
  - 两模式都支持现有 REPL 命令：`/new /tools /compact /history`。
  - 明确日志/错误提示（端口占用、启动失败、连接失败）并给出可操作建议。
  - unit + integration 覆盖关键流程，`pytest -q` 全绿。
- Test command: `pytest -q`
- Branch: `milestone/M19`

### Baseline
- Context:
  - 已先读取 `LOGBOOK.md`，当前可复用规则主要是“只记录经验，不记录过程实现”；M19 无额外冲突规则。
  - 执行模式：`serial`；`use_worktree=true`；worktree：`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M19`。
  - 已在 worktree 建立共享 `data/dev-tasks.json`、`data/locks` symlink，避免状态分叉。
  - 当前 CLI 仅有 remote 直连模式，尚无本地托管 API 生命周期管理。
- Decision:
  - 一次性拆 3 个 Roadpoints：R19.1 生命周期骨架、R19.2 双模式行为对齐、R19.3 诊断与文档收口。
- Rationale:
  - 先固化“模式 + 生命周期”基础设施，再补齐命令兼容与错误体验，减少返工。
- Evidence:
  - Tests: `pytest -q` -> `249 passed, 3 skipped`
  - Entry: 基线全绿，可进入 Red 阶段。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R19.1 Red（先写失败测试）

### R19.1 CLI 运行模式与托管进程生命周期
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `<pending>`
  - Entry: `<pending>`
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R19.2 remote 模式直连语义与 REPL 命令兼容
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `<pending>`
  - Entry: `<pending>`
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:

### R19.3 连接诊断与可操作错误提示收口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests: `<pending>`
  - Entry: `<pending>`
- Rollback:
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
