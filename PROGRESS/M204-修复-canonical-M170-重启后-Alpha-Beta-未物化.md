# M204 Progress — 修复 canonical M170 重启后 Alpha/Beta 未物化

## 启动记录
- worktree：`/Users/czj/Repos/nano-multiagent/.worktrees/M204`
- branch：`milestone/M204`
- 已读取：`LOGBOOK.md`、`COMMENTING_GUIDE.md`、`ACCEPTANCE/M170-acceptance.md`、`scripts/acceptance/m170_runtime.py`、相关 tests。
- 已确认共享派工板：`/Users/czj/Repos/nano-multiagent/.worktrees/M204/data/dev-tasks.json -> /Users/czj/Repos/nano-multiagent/data/dev-tasks.json`

## 初始判断
- 当前 `scripts/acceptance/m170_runtime.py` 的 `_write_runtime_config()` 仍硬编码单一 `assistant` agent，因此 fresh restart 后 gateway register 只能上报 `agent_count=1`。
- `ACCEPTANCE/m170-runtime/node-config.yaml` 与 `workspace/assistant` 现状也印证 canonical runtime 实际只准备了一个 agent。
- M170 rerun 脚本和现有 gateway 集成测试都要求 canonical label `agent-m170-alpha` / `agent-m170-beta`，所以单纯复用仓库根 `node-config.yaml` 的 `Alpha/Beta` 也不满足验收口径。

## 进度
