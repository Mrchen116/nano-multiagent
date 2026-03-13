# M139 worktree dev-tasks symlink 与调度卫生收口

## Plan
- 目标：修复 milestone worktree 内 `data/dev-tasks.json` 未共享主仓文件的问题，并补齐调度卫生自检，避免多 worker 面板状态分叉。
- 基线：`M104/M133/M134/M136/M137/M138/M139` 的 `data/dev-tasks.json` 均为普通文件；当前尚无针对该卫生契约的自动化测试。
- 测试门禁：`cd /Users/czj/Repos/nano-multiagent/.worktrees/M139 && python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q`
- 约束：只在 `/Users/czj/Repos/nano-multiagent/.worktrees/M139` 内工作；不新建 worktree；不改 board 内容。

## Roadpoints

### R1 红测与共享路径契约固化
- Context: 已知多个 milestone worktree 把 `data/dev-tasks.json` 留成普通文件，导致旧 worktree 和主仓 board 读写分叉；仓内此前没有任何自动化测试约束这条卫生规则。
- Decision: 新增 `tests/unit/test_worktree_dev_tasks_symlink.py`，用临时 repo/worktree 夹具先固化两条契约：普通文件/目录会被迁移成指向主仓 `data/dev-tasks.json` 与 `data/locks` 的 symlink；已正确链接时重复执行保持幂等。
- Rationale: 先把“失败点 = 缺少共享运行态文件收口能力”钉死，再做最小实现，避免只手工修复当前 worktree 而没有防回归门禁。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M139 && python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q` 首次运行在收集阶段失败：`ModuleNotFoundError: No module named 'agent.platform.worktree_runtime'`。
  - Entry: 红测证明仓内尚不存在负责收口共享 board/locks 的实现入口。
- Rollback: `836f56ebbc25b51efab6fdc67d4e093e9a373c2b`
- Commits: C1=`87087f1525d6b448a0f9cfb1789cf1309440c7ff`, C2=, C3=
- Next: 补 `agent.platform.worktree_runtime.prepare_shared_runtime_files`，用最小实现让红测转绿，并据此修复现有 milestone worktree。

### R2 最小实现与调度卫生收口
- Context: 目标不是修改 board 内容，而是把 worktree 内的运行态文件统一指向主仓共享路径；除 `dev-tasks.json` 外，锁目录若仍各自持有副本，也会继续制造调度分叉。
- Decision: 新增 `src/agent/platform/worktree_runtime.py`，提供幂等 helper `prepare_shared_runtime_files(repo_root, worktree_dir)`；它只处理 `data/dev-tasks.json` 与 `data/locks`，将 worktree 本地文件/目录替换为指向主仓共享路径的 symlink。随后用该 helper 一次性修复 `M104/M133/M134/M136/M137/M138/M139` 这批已知旧 worktree。
- Rationale: 用独立小模块收口共享运行态卫生，变更面最小、职责明确，后续无论是创建新 worktree 还是修复旧 worktree，都可以复用同一入口且保证幂等。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M139 && python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q` → `2 passed in 0.02s`
  - Entry: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M139 && PYTHONPATH=src python3 - <<'PY' ... PY` 实际修复并验证 `M104/M133/M134/M136/M137/M138/M139`，均输出 `board_symlink=True` 且目标为 `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json`，同时 `locks_symlink=True` 且目标为 `/Users/czj/Repos/nano-multiagent/data/locks`。
- Rollback: `87087f1525d6b448a0f9cfb1789cf1309440c7ff`
- Commits: C1=`87087f1525d6b448a0f9cfb1789cf1309440c7ff`, C2=`2bfa5ebc62c53569dc4a7693c9e76fa209f39f42`, C3=
- Next: 更新 TASKS/PROGRESS 最终状态并提交文档，作为本 milestone 的 C3。
