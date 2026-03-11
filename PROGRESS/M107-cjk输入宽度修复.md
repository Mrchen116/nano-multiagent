# M107 CJK 输入宽度修复

## Baseline
- Context:
  - coding_cli REPL 当前在 `src/coding_cli/input/repl_input.py` 中以字符数 `len()` 计算终端尾部回退列数。
  - 对中文 / 混合宽度文本，这会让显示光标列与逻辑光标索引脱节；用户按一次左右键虽变更一个字符索引，但终端光标列移动错误。
  - 范围只修复输入状态与渲染宽度，不改命令菜单、事件流、HTTP 链路。
- Decision:
  - 先新增 focused unit tests 固定中文与 mixed-width 行为，再在输入渲染层引入显示宽度计算。
- Rationale:
  - bug 位于纯本地输入引擎；unit tests 足以精确锁定回归，成本最低。
- Evidence:
  - Tests: `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M107/tests/unit/test_cli_main.py -k "repl_input"`
  - Entry: 现有 REPL 输入测试 13 条通过，但未覆盖 CJK 宽度场景。
- Rollback:
  - 基线，无需回退。
- Commits: C1=<pending>, C2=<pending>, C3=<pending>
- Next:
  - 为中文 / mixed-width 光标移动与渲染补红测。
