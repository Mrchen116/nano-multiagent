# M91 CLI 独立包提取 + core/tools 层级修正

## Milestone Plan
- Context:
  - 当前分支已完成 M90 的大部分重命名，但仍残留 `src/nano_multiagent/`、README legacy 路径与 `platform.tools` canonical 抽象。
  - M91 目标要求同时完成 `coding_cli` 独立包提取与 `core/tools` 抽象下沉，并保持全量测试通过。
- Decision:
  - 将里程碑拆为 R1 红测锁边界、R2 下沉 core.tools、R3 提取顶层 coding_cli 并清理 legacy root 三个 Roadpoint。
- Rationale:
  - 先锁结构边界，再迁移抽象与包路径，能降低批量替换误伤与零残留回归风险。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M91 && PYTHONPATH=src pytest -q`
  - Entry: 基线存在 3 个失败，分别指向 README legacy path 与 `nano_multiagent` root 尚未移除。
- Rollback:
  - `7995160 docs(R90.3): 补齐重命名证据与收尾计划`
- Commits: C1=, C2=, C3=
- Next:
  - 先提交 TASKS/PROGRESS 计划骨架，再进入 R1 红测。
