# M139 worktree dev-tasks symlink 与调度卫生收口

- Milestone: M139
- Title: worktree dev-tasks symlink 与调度卫生收口
- Goal: 修复 milestone worktree 内 `data/dev-tasks.json` 未指向主仓共享文件的问题，并收口 worktree 调度卫生，避免多 worker 面板状态分叉。
- execution_mode: parallel
- use_worktree: true
- worktree_dir: `/Users/czj/Repos/nano-multiagent/.worktrees/M139`
- branch: `milestone/M139`
- test_command: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M139 && python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q`
- allowed_scope: ` /Users/czj/Repos/nano-multiagent/.worktrees/M139 ` 内与 worktree 初始化/调度卫生相关的脚本、测试、TASKS/PROGRESS。
- forbidden_scope: 不改 board 业务内容；不新建 git worktree；不改 `/Users/czj/Repos/nano-multiagent/data/dev-tasks.json` 内容；不扩散到 milestone 调度之外。
- prevention_rules:
  - 所有 worktree 内 `data/dev-tasks.json` 必须指向主仓共享文件，避免状态分叉。
  - 若涉及锁目录，也必须统一落到主仓共享路径，避免不同 worktree 各持一份锁。
  - 先补红测，再做最小实现；文档记录根因、证据、回滚点。

## Baseline
- 已确认 `/Users/czj/Repos/nano-multiagent/.worktrees/M104|M133|M134|M136|M137|M138|M139/data/dev-tasks.json` 当前均为普通文件，不是 symlink。
- 基线失败符合 Milestone 现状：`/Users/czj/Repos/nano-multiagent/.worktrees/M139/data/dev-tasks.json` 解析到 worktree 本地文件，而不是主仓共享文件。

## Roadpoints

### R1 红测与共享路径契约固化
- Status: TODO
- Acceptance:
  - 新增最小测试证明 milestone worktree board 文件必须是指向主仓共享文件的 symlink。
  - 测试覆盖“已有普通文件需迁移为 symlink”的场景。
  - 测试覆盖重复执行幂等，不会破坏已存在的正确 symlink。
  - 测试先红，失败点明确指向当前缺失的卫生收口能力。
- Tests Plan:
  - unit: 选择；对 worktree 卫生函数做临时目录验证，最快定位文件系统契约。
  - contract: 选择；断言 symlink 目标与共享锁目录契约。
  - integration: 暂不选；本 milestone 目标集中在文件系统卫生函数，先以单元级覆盖核心行为。
  - e2e: 暂不选；无需拉起真实运行时。
- Expected Tests:
  - `tests/unit/test_worktree_dev_tasks_symlink.py::test_prepare_shared_runtime_files_converts_dev_tasks_file_to_repo_symlink`
  - `tests/unit/test_worktree_dev_tasks_symlink.py::test_prepare_shared_runtime_files_is_idempotent_for_existing_symlink`
- DoD:
  - `python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q` 全绿。
  - 完成 C1/C2/C3。
  - PROGRESS 记录红测失败点、实现决策、证据与回滚点。

### R2 最小实现与调度卫生收口
- Status: TODO
- Acceptance:
  - worktree 准备逻辑会把 `data/dev-tasks.json` 迁移为指向主仓共享文件的 symlink。
  - 必要时同步收口共享锁目录，避免旧 worktree 读写分叉。
  - 重复执行安全，且不会修改 board 业务内容。
  - 代码改动限制在 worktree 初始化/卫生相关实现。
- Tests Plan:
  - unit: 选择；复用 R1 测试验证实现。
  - contract: 选择；断言 symlink realpath 与共享锁目录 realpath。
  - integration: 可选；若已有脚本入口，补最小入口测试验证旧 worktree 迁移。
  - e2e: 不选；不需要真实运行时。
- Expected Tests:
  - `python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q`
- DoD:
  - `python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q` 全绿。
  - 完成 C1/C2/C3。
  - PROGRESS 记录根因、实现、证据、回滚点与提交哈希。
