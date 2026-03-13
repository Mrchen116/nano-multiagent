# M139 worktree dev-tasks symlink 与调度卫生收口

## Plan
- 目标：修复 milestone worktree 内 `data/dev-tasks.json` 未共享主仓文件的问题，并补齐调度卫生自检，避免多 worker 面板状态分叉。
- 基线：`M104/M133/M134/M136/M137/M138/M139` 的 `data/dev-tasks.json` 均为普通文件；当前尚无针对该卫生契约的自动化测试。
- 测试门禁：`cd /Users/czj/Repos/nano-multiagent/.worktrees/M139 && python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q`
- 约束：只在 `/Users/czj/Repos/nano-multiagent/.worktrees/M139` 内工作；不新建 worktree；不改 board 内容。

## Roadpoints

### R1 红测与共享路径契约固化
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R2 最小实现与调度卫生收口
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
