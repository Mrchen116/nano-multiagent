# M215 current-main dist 重建与旧文案清理进展

## Milestone context
- Goal: 查明并修复 current main 验收仍读到旧前端产物的问题，确保 M213 文案与 NO_REPLY 可见态修复真正进入 current-main dist 并被 fresh runtime 提供。
- Scope: 仅限 `/Users/czj/Repos/nano-multiagent/.worktrees/M215/src/IM/frontend/**` 与本 milestone 的 `TASKS/PROGRESS`。
- Guardrails:
  - 先证明问题是否来自 dist 未更新，而不是误判代码逻辑。
  - 必须用 current-main build 产物验证旧字符串是否还在 dist 中。
  - 若只需重建 dist，不扩展改动；若源码与 dist 不一致，仅做最小修复。

### R1 锁定 current-main completed 文案残留并建立 dist 证据
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:

### R2 重建 current-main dist 并验证旧字符串消失
- Context:
- Decision:
- Rationale:
- Evidence:
  - Tests:
  - Entry:
- Rollback:
- Commits: C1=, C2=, C3=
- Next:
