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
- Commits: C1=`f75ad20`, C2=`5308b13`, C3=`<pending>`
- Next:
  - R27.2 Red：补 REPL 接线与集成回归测试，确保真实入口输入 `/` 可触发并执行下拉命令。
