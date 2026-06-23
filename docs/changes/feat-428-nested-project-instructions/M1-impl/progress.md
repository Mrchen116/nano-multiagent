# feat-428-M1 — Progress

<!-- 每个 roadpoint 完成后实时追加。 -->

## R1 — 共享核心 agents_md

- Context: 机制 A/B 都要读 AGENTS.md（含 @import）、机制 B·外要定最外层 git 仓根并逐级收 AGENTS.md。仓内无现成 helper。
- Decision: 新建 `src/agent/core/agent/agents_md.py`，三函数纯 core（仅 pathlib/re）：
  - `load_agents_md(path, *, _seen, _depth)`：读正文 + 行扫描跳 fenced code block（```/~~~）后用 CC 同款正则 `(?:^|\s)@((?:[^\s\\]|\\ )+)` 提 @import，解析 @path/@./@~/@/abs，深度上限 5、Set（绝对路径）防环、不存在静默忽略，展开正文用 `\n\n` 拼接。
  - `find_outermost_git_root(start_dir)`：单次上行到文件系统根，记录最高一层含 `.git`（`.exists()` 覆盖目录与文件两形态）者 = 最外层仓根；无则 None。
  - `iter_agents_md_chain(file_dir, *, top)`：[file_dir … top] 闭区间逐级 yield 存在的 AGENTS.md（nearest-first）。
- Rationale: CC 用 marked Lexer；本仓无等价库，轻量行扫描跳代码块对齐 CC "leaf text only"语义且零新依赖（已报 team-lead）。@import 正则/MAX_DEPTH=5/Set/路径判定逐字核对 CC claudemd.ts 源码。最外层（非最近）仓根 + 单次上行 = design 决策 7。
- Evidence:
  - Tests: `tests/unit/test_agents_md_loader.py` 16 passed（@import 相对/绝对/裸路径/缺失/代码块```与~~~/防环单次/深度上限5；git 无/单仓/.git 文件 worktree 形态/嵌套仓取最外层；chain 范围内存在项/全空）
  - Entry: N/A（纯逻辑 helper，入口验证在 R2/R3 机制层）
  - Frontend State Matrix / Browser QA / Visual: N/A（无 UI）
  - E2E/Regression: N/A（纯单元逻辑，无 e2e 依赖）
- Rollback: 回退到 R1 C1（test commit）即移除实现。
- Commits: C1=test 红测, C2=feat 实现, C3=本段
- Next: R2 机制 A。
