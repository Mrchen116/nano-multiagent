# M107 CJK 输入宽度修复

## Milestone Context
- Milestone: M107 — coding_cli 中文 / 混合宽度输入光标移动与渲染修复
- execution_mode: serial
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M107`
- branch: `milestone/M107`
- test_command: `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M107/tests/unit/test_cli_main.py -k "repl_input or cjk"`
- allowed_scope: `src/coding_cli/input/repl_input.py`, `tests/unit/test_cli_main.py`, `TASKS/M107-*.md`, `PROGRESS/M107-*.md`
- forbidden_scope: `data/dev-tasks.json`、与本 bug 无关的 CLI/agent/IM 代码
- prevention_rules:
  - 范围只收敛在 REPL 输入状态与终端渲染宽度，不扩散到无关 UI 重构。
  - 先用红测固定 CJK / mixed-width 光标与渲染问题，再做最小实现。
  - 终端列宽计算必须以“用户可见字符宽度”为准，而不是 `len()`。

## Roadpoints

### R1 输入状态与渲染宽度按可见列对齐
- Status: DONE
- Acceptance:
  - 左右方向键在中文文本中每次只移动一个用户可见字符。
  - 中英混排文本中，逻辑光标仍按字符移动，但终端回退列数按显示宽度计算。
  - `render_interactive_line` 对 CJK / mixed-width 光标定位不再使用 `len()` 作为尾部回退列数。
  - 现有 ASCII 输入编辑行为无回归。
- Tests Plan:
  - unit: 需要。直接覆盖输入状态机与渲染 ANSI 输出，最快固定 bug。
  - contract: 不需要。本次无新的外部契约面。
  - integration: 不需要。本 bug 聚焦纯输入引擎，无需 HTTP/运行时链路。
  - e2e: 不需要。终端原始按键与宽度问题先由 unit 精准覆盖，避免引入脆弱终端依赖。
- Expected Tests:
  - `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M107/tests/unit/test_cli_main.py -k "cjk or mixed_width or repl_input"`
- DoD:
  - 上述 test_command 全绿。
  - 完成 C1/C2/C3 三提交。
  - `PROGRESS/M107-cjk输入宽度修复.md` 写清决策、证据、回滚点、提交哈希。
