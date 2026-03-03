# PROGRESS (Milestone: M27)

- Title: CLI命令下拉选择（/触发）
- Goal: 在交互式 REPL 可编辑输入中，输入 `/` 弹出命令下拉，支持 `↑/↓` 选择、`Enter` 填充，同时保持现有命令流与单命令 JSON 契约稳定。
- Exit Criteria:
  - `/` 触发下拉命令列表（覆盖 `/help /new /use /session /tools /compact /history /exit`）。
  - `↑/↓` 切换选中项，`Enter` 选择后填充输入框。
  - 与行内编辑/历史回填兼容，不破坏命令执行流。
  - 单命令模式 JSON 契约不变。
  - `pytest -q` 全绿。
- Test command: `pytest -q`
- Branch: `milestone/M27`

### Baseline
- Context:
  - execution_mode=`serial`；`use_worktree=true`；worktree=`/Users/czj/Repos/nano-multiagent/.nano_multiagent/worktrees/M27`；branch=`milestone/M27`。
  - 已读取 `LOGBOOK.md`，沿用：CLI 必须保持 HTTP-only、单命令 JSON 契约隔离、REPL 异步事件消费防串线。
  - prevention_rules：仅增强 REPL editable 输入路径；不改 runtime/tool/session/llm 核心逻辑；每个 Roadpoint 必须 C1/C2/C3。
  - 工作区初始无 `data/`，后续集成阶段需确保 `data/dev-tasks.json` 与 `data/locks/` 指向主仓共享运行态文件。
- Decision:
  - 先做两条 Roadpoint：R27.1 输入引擎下拉选择能力；R27.2 REPL 接线与回归门禁收口。
  - 采用“先红测试锁能力缺口，再最小实现，再文档固化”的串行节奏。
- Rationale:
  - 先锁定键盘交互边界可避免实现期间破坏已有编辑/历史行为，并能精确定位回归。
- Evidence:
  - Tests: `pytest -q`（baseline：`327 passed, 4 skipped`）
  - Entry: 基线全绿，可进入 R27.1 Red。
- Rollback:
  - plan commit
- Commits: C1=`<pending>`, C2=`<pending>`, C3=`<pending>`
- Next:
  - R27.1 Red：新增“/ 下拉选择”输入引擎测试并确认失败。

### R27.1 在输入引擎实现“/ 触发命令下拉 + ↑/↓选择 + Enter填充”
- Context:
  - 现有可编辑输入仅支持行内编辑与历史回填，缺少命令候选选择能力。
  - 需求要求下拉打开时 `↑/↓` 用于候选切换，避免误触历史回填。
- Decision:
  - 在 `repl_input.read_interactive_line` 增加 `command_suggestions` 参数与命令下拉状态机。
  - 下拉触发条件限定为输入框当前内容为单个 `/` 且光标位于其后；`Enter` 首次用于填充选中命令，二次 `Enter` 才提交。
  - 通过 ANSI 渲染在输入行下方展示候选列表，并用选中标记高亮当前项。
- Rationale:
  - 触发条件最小化可避免干扰已有输入路径，同时保持行为易于预测与测试。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_cli_main.py -k slash_menu`（新增测试先红：缺少 `command_suggestions` 参数）
    - Gate: `pytest -q`（`329 passed, 4 skipped`）
  - Entry:
    - `/_read_interactive_line` 已支持候选注入与下拉按键流；
    - 既有行内编辑/历史回填回归测试保持通过。
- Rollback:
  - `f75ad20`（R27.1 C1）
- Commits: C1=`f75ad20`, C2=`5308b13`, C3=`f072de3`
- Next:
  - R27.2 Red：补 REPL 接线与集成回归测试，确保真实入口输入 `/` 可触发并执行下拉命令。

### R27.2 在 REPL 编排层接线并补充边界门禁
- Context:
  - R27.1 已具备输入引擎能力，但 `_run_repl` 尚未显式注入候选命令列表，真实入口接线不完整。
  - 需要验证“斜杠选择 -> 命令执行”链路，并确保不破坏历史回填与单命令 JSON 契约。
- Decision:
  - 在 `commands._run_repl` 调用 `_build_repl_input_reader` 时传入 `_REPL_COMMANDS`。
  - 为 scripted REPL 测试读入器注入 `supported_repl_commands()`，让集成测试可稳定复现 `↑/↓ + Enter` 选择流。
  - 新增边界测试校验 `_run_repl` 的候选命令接线，新增集成测试校验“/ 下拉选择 /new 并执行”主链路。
- Rationale:
  - 在编排层接线后，真实 REPL 与测试脚本入口保持一致，能防止后续重构遗漏候选注入导致能力失效。
- Evidence:
  - Tests:
    - Red: `pytest -q tests/unit/test_cli_refactor_boundaries.py tests/integration/test_cli_http_flow_integration.py -k "supported_commands_to_input_reader or slash_menu_selects_command"`（新增断言先红）
    - Gate: `pytest -q`（`331 passed, 4 skipped`）
  - Entry:
    - `/` 下拉命令在 REPL 主流程可用，`↑/↓` 选择后 `Enter` 可填充并执行命令；
    - 既有编辑/历史/命令测试链路保持通过。
- Rollback:
  - `1a932c6`（R27.2 C1）
- Commits: C1=`1a932c6`, C2=`ec75ebe`, C3=`<pending>`
- Next:
  - Milestone 收口：rebase `origin/main`、全量回归、合并 `main`、更新 `dev-tasks.json`。
