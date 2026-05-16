# bugfix-355-M2 — Progress

### R1 — 新建 dangerous_paths.py + 单测

- Context: M2 核心是提供危险路径检查能力,供 WriteTool/EditTool 的 check_permissions 调用。先建模块再接工具。
- Decision: 新建 `src/agent/platform/tools/dangerous_paths.py` 含 DANGEROUS_FILES(8项)/DANGEROUS_DIRECTORIES(6项)常量 + `check_dangerous_path` 函数;实现 Anchor G 的 `.claude/worktrees/` 例外逻辑。
- Rationale: 按 D5.2 清单逐字实现,相对 CC baseline 裁掉 `.ripgreprc`/`.claude.json`,加入 `.nanocode`/`.nano-assistant` 两项本仓自家目录。
- Evidence:
  - Tests: `pytest tests/unit/agent/platform/tools/test_dangerous_paths.py` 44 passed
  - Entry: `pytest tests/unit/agent/` 150 passed(含原有 106 + 新增 44)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — 纯后端常量+函数模块,无用户入口侧效应
  - Visual/Interaction: N/A
- Rollback: revert to commit 76721105 (C1)
- Commits: C1=76721105, C2=ac2903f4, C3=<this>
- Next: R2 — WriteTool/EditTool check_permissions 实现
