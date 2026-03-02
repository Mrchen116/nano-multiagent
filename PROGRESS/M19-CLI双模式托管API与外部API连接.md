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
  - 现有 CLI 仅有“直接连 HTTP API”路径，缺少“CLI 拉起并托管本地 API”能力。
  - 需保证 managed 生命周期清晰（启动成功判定、退出回收、异常清理）且 remote 不受影响。
- Decision:
  - 新增 `ManagedServerProcess`（`src/nano_multiagent/cli/managed_server.py`）负责：
    - 校验 managed 仅允许本地 `http://` base_url；
    - 启动 uvicorn 子进程并轮询 `/v1/health` 判定就绪；
    - 启动失败/端口占用/超时时抛出带 `suggestion` 的错误；
    - CLI 退出或异常时统一 `stop()` 回收子进程。
  - `run_cli` 新增 `--mode managed|remote`（默认 `remote` 以保持历史兼容）；
    - `managed` 进入托管生命周期；
    - `remote` 走 `nullcontext`，明确不拉起本地服务。
- Rationale:
  - 将进程管理与命令交互解耦，便于 unit/integration 注入 fake manager 做稳定测试。
  - 通过异常携带建议文案，避免上层到处拼接错误提示逻辑。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_cli_main.py tests/unit/test_cli_managed_server.py` -> `ModuleNotFoundError`（符合“先红”）
    - Green: 同命令 -> `17 passed`
    - Gate: `pytest -q` -> `255 passed, 3 skipped`
  - Entry:
    - managed 模式可注入 manager 并触发 `start/stop`；
    - remote 模式不会触发 managed factory；
    - 端口占用等场景返回可操作 suggestion。
- Rollback:
  - `cb71da7`（R19.1 C1）
- Commits: C1=`cb71da7`, C2=`c58db82`, C3=`<pending>`
- Next:
  - R19.2 Red（双模式与现有 REPL 命令链路对齐）

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
