# M175 修复 isolated IM runtime sqlite readonly blocker

- Milestone: M175
- Title: 修复 isolated IM runtime sqlite readonly blocker
- Goal: 修复 fresh isolated IM runtime 中 Gateway websocket register 写入 SQLite 时报 `sqlite3.OperationalError: attempt to write a readonly database` 的阻塞问题，恢复真实浏览器验收链路的可信度。
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M175`
- branch: `milestone/M175`
- test_command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M175 && python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q`
- allowed_scope: ` /Users/czj/Repos/nano-multiagent/.worktrees/M175 ` 内 isolated runtime/worktree runtime、相关单测、TASKS/PROGRESS。
- forbidden_scope: 不改 `data/dev-tasks.json` 内容；不扩散到无关 IM 功能；不新建额外 worktree。
- prevention_rules:
  - isolated runtime 必须保留 worktree-local 可写 `data/` 目录，用于私有 IM SQLite 与 uploads。
  - 仅 `data/dev-tasks.json` 与 `data/locks` 继续共享到主仓，避免调度状态分叉。
  - 用最小修复恢复真实浏览器验收 blocker；优先补聚焦回归测试。

## Baseline
- M171 证据表明 isolated IM 在 19011 成功启动，但 gateway websocket register 进入 `src/IM/ws/gateway_handler.py -> NodeRepository.record_gateway_registration()` 时，SQLite 报 `attempt to write a readonly database`。
- 现有 worktree runtime 卫生逻辑仅保证共享 `data/dev-tasks.json` 与 `data/locks`，但 fresh isolated runtime 未显式重建 worktree-local `data/` 目录，导致 IM 默认 `data/im_service.sqlite3` 容易落到缺失/错误继承权限的路径上。

## Roadpoints

### R1 根因钉死与红测收口
- Status: DONE
- Acceptance:
  - 确认 readonly 根因来自 worktree runtime 卫生后未确保私有 `data/` 目录存在且可写，而 IM 默认数据库路径依赖该目录。
  - 新增回归测试覆盖 fresh worktree 只共享 board/locks 后，仍会重建本地 `data/` 目录供私有 runtime 文件写入。
- Expected Tests:
  - `tests/unit/test_worktree_dev_tasks_symlink.py::test_prepare_shared_runtime_files_recreates_worktree_local_data_dir_for_private_runtime_files`
- DoD:
  - 红转绿并能用测试描述新的目录契约。

### R2 最小实现与回归验证
- Status: DONE
- Acceptance:
  - `prepare_shared_runtime_files()` 在建立共享 symlink 前，会确保 worktree-local `data/` 目录存在。
  - 不修改共享 board 内容，不改变 locks/dev-tasks 的共享语义。
  - 回归测试全绿。
- Expected Tests:
  - `python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q`
- DoD:
  - 目标测试全绿。
  - PROGRESS 记录根因、决策、证据、回滚点。
