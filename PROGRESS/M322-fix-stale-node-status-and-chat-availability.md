# M322 Fix stale node status and chat availability mismatch

## Startup
- 已阅读并遵守：`SPEC.md`、`LOGBOOK.md`、`COMMENTING_GUIDE.md`。
- 已完成 worktree 初始化：`/Users/czj/Repos/nano-multiagent/.worktrees/M322`。
- 已将 `data/dev-tasks.json`、`data/locks` 链接到主仓运行态目录。
- 派发 baseline 命令首段失败：`tests/im_service/integration/test_nodes_api.py` 在当前仓库不存在（已被 `test_nodes_metrics_api.py` 替代）；后续执行将按现有测试文件覆盖同一节点状态能力。
