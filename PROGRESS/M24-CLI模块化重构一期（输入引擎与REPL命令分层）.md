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

### R24.1 抽离可编辑输入与历史回填引擎到 `cli/repl_input.py`
- Context:
  - `commands.py` 同时承载 REPL 主循环与终端输入细节（raw mode、按键解析、历史导航），导致文件过长且职责耦合。
  - 现有测试直接调用 `cli_commands._read_interactive_line`，迁移时需保持兼容并防止行为漂移。
- Decision:
  - 新增 `src/nano_multiagent/cli/repl_input.py`，收敛输入引擎协议与实现：`build_repl_input_reader`、`read_interactive_line` 等。
  - `commands.py` 通过导入别名委派输入逻辑，继续暴露 `_read_interactive_line` 兼容既有测试入口。
  - 新增 `tests/unit/test_cli_refactor_boundaries.py`，为“输入引擎职责在独立模块”建立结构门禁。
- Rationale:
  - 把“输入编辑”从“REPL 编排”中剥离后，后续可独立演进输入能力，且不影响主流程可读性。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_cli_refactor_boundaries.py`（ImportError: `repl_input` 不存在）
    - Gate: `pytest -q`（`326 passed, 4 skipped`）
  - Entry:
    - 行内编辑/历史回填相关测试保持通过；
    - `commands.py` 输入细节函数体已迁出到 `repl_input.py`。
- Rollback:
  - `e1af44f`（R24.1 C1）
- Commits: C1=`e1af44f`, C2=`747dac1`, C3=`6e73823`
- Next:
  - R24.2 Red：新增 REPL 命令路由模块边界测试。

### R24.2 抽离 REPL 命令路由与参数校验到 `cli/repl_commands.py`
- Context:
  - `_run_repl` 内联了全部命令路由、参数校验、错误兜底与历史展示，主流程编排被命令细节淹没。
  - 需要在保持输出文案/异常分层完全一致的前提下拆出稳定命令边界。
- Decision:
  - 新增 `src/nano_multiagent/cli/repl_commands.py`，承载命令路由核心：`handle_repl_command`、参数校验、`/history` 解析与命令错误输出。
  - `commands.py` 的 `_run_repl` 改为“读输入 -> 委派命令 -> 处理普通消息”薄编排，并通过 `_handle_repl_command` 维护会话切换/退出信号。
  - `supported_repl_commands()` 改为读取新模块常量，防止命令清单漂移。
- Rationale:
  - 命令分层后，主循环与路由逻辑各自单一职责，后续扩命令时无需再修改大块 REPL 主流程。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_cli_refactor_boundaries.py`（ImportError: `repl_commands` 不存在）
    - Gate: `pytest -q`（`327 passed, 4 skipped`）
  - Entry:
    - 新增结构门禁通过：`commands._handle_repl_command` 委派到 `repl_commands.handle_repl_command`；
    - 命令链路相关 unit/integration 断言保持稳定。
- Rollback:
  - `1cafc84`（R24.2 C1）
- Commits: C1=`1cafc84`, C2=`f2fa5f8`, C3=`<pending>`
- Next:
  - Milestone 收口：rebase `origin/main`、全量回归、合并 `main` 并回写 `dev-tasks.json`。
