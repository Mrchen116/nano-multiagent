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

### R2 — WriteTool/EditTool check_permissions + bypass-immune 单测

- Context: M1 在 auto_mode_gate 建立了 safety_locked bypass-immune 路径;M2 需要 WriteTool/EditTool 实现 check_permissions 才能实际触发该路径。检查 D5 要求两个写工具都必须 override。
- Decision: 在 write.py 和 edit.py 各加 `check_permissions` 方法,调用 `check_dangerous_path(raw_path, cwd=ctx.cwd)` — 命中则返回 `PermissionDecision(behavior='ask', decision_reason={'type': 'safety_check', 'matched_path': raw_path})`,否则 passthrough。
- Rationale: 对称实现 — 两工具都能写,攻击面相同,只区分工具名和 reason 文案。锚点 G 中 cwd 透传让相对路径也能正确解析。
- Evidence:
  - Tests: `pytest tests/unit/agent/platform/tools/test_tool_check_permissions.py` 23 passed (含原有 6 + 新增 17)
  - Entry: `pytest tests/unit/agent/` 167 passed(含全部平台测试)
  - Frontend State Matrix: N/A
  - Browser QA: N/A
  - E2E/Regression: N/A — 纯后端 check_permissions;reviewer 旅程将在 dangerously 模式下手动验证弹卡片
  - Visual/Interaction: N/A
- Rollback: revert to commit 65ee904c (C1 R2)
- Commits: C1=65ee904c, C2=492409f3, C3=<this>
- Next: milestone 完成，进入集成阶段
