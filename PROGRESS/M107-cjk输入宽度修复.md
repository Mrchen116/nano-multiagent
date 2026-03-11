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
- Commits: C1=`b9ed0e0`, C2=`9b5835c`, C3=<pending>
- Next:
  - 写入 Roadpoint 完成证据并提交文档。

### R1 输入状态与渲染宽度按可见列对齐
- Context:
  - 逻辑输入状态原本已按 Python 字符索引移动，所以左右键对中文字符本身并不会拆半；实际问题在于渲染层把“剩余字符数”误当成“终端剩余列数”。
  - inline hint 也会参与尾部回退列数，若文本含 CJK，提示区前的光标位置同样会错位。
- Decision:
  - 保持 `_InputState.cursor` 的字符级语义不变，只在 `_render_interactive_line_locked` 改为按 `line[cursor:]` 和 `inline_hint` 的显示宽度计算 `tail_size`。
  - 新增 `_display_width()`，对 East Asian Width 为 `W/F` 的字符按 2 列计算，对 combining 字符按 0 列处理，其余按 1 列处理。
- Rationale:
  - 这样可以最小化改动：编辑语义继续是一键一字符，终端定位则与用户看到的列宽一致，不需要重写输入状态机。
- Evidence:
  - Tests: `pytest -q /Users/czj/Repos/nano-multiagent/.worktrees/M107/tests/unit/test_cli_main.py -k "repl_input or cjk"`
  - Entry: 16 passed, 67 deselected；新增用例覆盖中文插入、mixed-width 光标回退、带 inline hint 的 CJK 光标定位。
- Rollback:
  - 若需重做，可回退到 C1 `b9ed0e0`，保留红测后重新实现宽度策略。
- Commits: C1=`b9ed0e0`, C2=`9b5835c`, C3=<pending>
- Next:
  - 提交 TASKS/PROGRESS 文档收口本 Roadpoint。
