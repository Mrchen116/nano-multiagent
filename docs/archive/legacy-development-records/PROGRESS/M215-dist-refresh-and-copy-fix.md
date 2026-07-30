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
  - 旧 M170 验收仍读到 `Agent replied`、`The latest agent response finished successfully.` 等旧完成态文案，已知旧 dist 命中这些字符串。
  - prevention_rules 要求先分清是旧 dist 漂移，还是 current-main 源码仍保留可见路径。
- Decision:
  - 先把 `message-pane` 完成态测试改成断言只显示 `Delivered`，并显式禁止旧完成态文案，作为 Red。
  - 以 grep 对源码与 dist 双向取证，确认旧 ownership/target 文案只剩测试，而 completed 文案仍在运行源码。
- Rationale:
  - 只有先把失败点锁到运行源码，才能避免把问题误判成“仅需重新 build dist”。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M215/src/IM/frontend && npm test -- --runInBand src/features/chat/components/message-pane.test.tsx` 先红，失败于找不到 `Delivered`。
  - Entry: `/Users/czj/Repos/nano-multiagent/.worktrees/M215/src/IM/frontend/src/features/chat/components/message-pane.tsx` 仍含 `Agent replied` 与 `The latest agent response finished successfully.`；而 `Target: Multiple participants`、`Using your main agent assistant` 仅剩测试字面量。
- Rollback: `b824627`（R1 C1）
- Commits: C1=b824627, C2=a766b68, C3=
- Next: 补齐 R2 文档，固定 fresh dist 的字符串验证证据。

### R2 重建 current-main dist 并验证旧字符串消失
- Context:
  - 仅修源码不够，M170 fresh runtime 仍依赖仓内 `src/IM/frontend/dist`，必须证明新产物已吸收 current-main 修复。
  - dist 中仍会保留 `@agent:` 协议 token 常量，需要与“用户可见残留”严格区分。
- Decision:
  - 运行完整 chat test gate 与 `npm run build` 重建 dist，并用 Python 直接扫描 build 产物中目标字符串。
  - 将 `@agent:` 归因为 mention payload 编码常量，而非 UI 可见文案。
- Rationale:
  - exit criteria 是 fresh runtime 读取到的新产物，因此必须给出 build 后产物级别证据，而不能只停留在源码 grep。
- Evidence:
  - Tests: `cd /Users/czj/Repos/nano-multiagent/.worktrees/M215/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build` 全绿（67 tests passed；build 产出 `dist/assets/index-Dc1OFUfo.js`）。
  - Entry: Python 扫描 `/Users/czj/Repos/nano-multiagent/.worktrees/M215/src/IM/frontend/dist/assets/index-Dc1OFUfo.js`，`Agent replied` / `The latest agent response finished successfully.` / `Target: Multiple participants` / `Using your main agent assistant` 均返回 `-1`；仅 `@agent:` 命中协议常量 `const IN="@agent:"`。
- Rollback: `a766b68`（R1 C2 / 当前稳定实现）
- Commits: C1=, C2=, C3=
- Next: 提交文档并继续 milestone 集成到 main。
