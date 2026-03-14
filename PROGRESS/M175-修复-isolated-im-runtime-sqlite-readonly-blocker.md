# M175 修复 isolated IM runtime sqlite readonly blocker

## Plan
- 目标：修复 fresh isolated IM runtime 中 gateway websocket register 写 SQLite 时触发 readonly database 的 blocker，恢复 M171/M170 真实浏览器链路可继续验证。
- 基线：M171 证据显示 isolated IM 已启动在 19011，但 `record_gateway_registration()` 写库失败；IM 默认数据库路径是相对 `data/im_service.sqlite3`，依赖当前 runtime worktree 的本地 `data/` 目录可写。
- 测试门禁：`cd /Users/czj/Repos/nano-multiagent/.worktrees/M175 && python3 -m pytest tests/unit/test_worktree_dev_tasks_symlink.py -q`
- 约束：仅做最小 runtime hygiene 修复；不改 `data/dev-tasks.json` 内容；不扩散到无关 IM 功能。

## Roadpoints

### R1 根因钉死与目录契约回归
- Context: worktree runtime 之前只关心把 `data/dev-tasks.json` 与 `data/locks` 指向主仓共享路径，但 fresh isolated runtime 仍需要 worktree-local `data/` 容器来承载私有 IM SQLite 和 uploads。若该目录未被显式重建，IM 默认相对路径数据库会落到错误/不可写上下文，最终在 gateway register 首次写 nodes 表时报 readonly。
- Decision: 在 `prepare_shared_runtime_files()` 中先确保 worktree-local `data/` 目录存在，再继续只把 `dev-tasks.json` 与 `locks` 替换成共享 symlink；同时补单测覆盖“fresh worktree 也必须拥有本地 data 目录”的契约。
- Rationale: 只修 runtime hygiene，不改 IM repository / websocket / DB schema；既保持共享调度文件语义，又给 isolated runtime 留出私有可写数据库目录，变更面最小。
- Evidence:
  - Code path: `/Users/czj/Repos/nano-multiagent/.worktrees/M175/src/IM/app.py` 默认使用 `Path(os.getenv("IM_DB_PATH", "data/im_service.sqlite3"))`；`/Users/czj/Repos/nano-multiagent/.worktrees/M175/src/IM/infra/db.py` 仅会 `mkdir(db_path.parent)`，因此依赖 worktree-local `data/` 为正常私有目录。
  - Tests: `python3 -m pytest /Users/czj/Repos/nano-multiagent/.worktrees/M175/tests/unit/test_worktree_dev_tasks_symlink.py -q` -> `3 passed in 0.03s`
- Rollback: revert changes in `/Users/czj/Repos/nano-multiagent/.worktrees/M175/src/agent/platform/worktree_runtime.py` and `/Users/czj/Repos/nano-multiagent/.worktrees/M175/tests/unit/test_worktree_dev_tasks_symlink.py`.
- Commits: C1=, C2=, C3=
- Next: 如需完全关闭 M171/M170 blocker，使用 fresh isolated runtime 重新跑 browser acceptance，验证 gateway register 不再因 SQLite readonly 中断。
