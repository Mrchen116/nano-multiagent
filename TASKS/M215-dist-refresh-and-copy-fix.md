# M215 current-main dist 重建与旧文案清理计划

## Roadpoints

### R1 锁定 current-main completed 文案残留并建立 dist 证据
- Acceptance:
  - 证明旧字符串在当前源码的可见路径还是仅存在于旧 dist。
  - 新增/更新测试能明确锁定 completed 状态不再显示旧完成态文案。
  - 明确 `@agent:` 仅允许存在于发送协议 token，不允许作为用户可见残留。
  - 记录旧 dist 命中证据，作为重建前基线。
- Tests Plan:
  - unit: 选。直接覆盖 `MessagePane` completed 状态的可见文案断言，成本最低且能准确锁定回归点。
  - contract: 不选。本 Roadpoint 不改接口结构，仅验证文案与可见性。
  - integration: 选。沿用 chat workspace 既有入口，确认 `NO_REPLY` 流程不会再带出旧完成态文案。
  - e2e: 不选。本 milestone 目标是 current-main build 产物与仓内前端入口一致，Vitest + dist 字符串扫描足以提供证据。
- Expected Tests:
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M215/src/IM/frontend/src/features/chat/components/message-pane.test.tsx`
  - `/Users/czj/Repos/nano-multiagent/.worktrees/M215/src/IM/frontend/src/features/chat/chat-workspace-page.test.ts`
- DoD:
  - `cd /Users/czj/Repos/nano-multiagent/.worktrees/M215/src/IM/frontend && npm test -- --runInBand src/features/chat/**/*.test.ts* && npm run build` 全绿。
  - 能给出源码/测试/dist 三处证据，说明旧文案来源与修复范围。
  - 完成 C1/C2/C3。
  - `PROGRESS/M215-dist-refresh-and-copy-fix.md` 记录决策/证据/哈希。
- 状态: TODO

### R2 重建 current-main dist 并验证旧字符串消失
- Acceptance:
  - 使用 current-main 源码重建 `src/IM/frontend/dist`。
  - 重建后的 dist 不再包含 `Agent replied`、`The latest agent response finished successfully.`、`Target: Multiple participants`、`Using your main agent assistant` 等旧可见文案。
  - 重建后的 dist 不暴露用户可见 `@agent:` 残留；若仍出现，只能是协议/测试层而非产物可见文本。
  - 输出 fresh build 证据，证明 M170 后续验收会读到新产物。
- Tests Plan:
  - unit: 不新增。沿用 R1 已建立的 completed 文案保护。
  - contract: 不选。本 Roadpoint 仅重建产物并做字符串门禁。
  - integration: 选。运行 milestone gate 并结合 dist 扫描，验证入口产物已刷新。
  - e2e: 不选。本 milestone 不做产品验收，仅验证仓内 fresh runtime 所依赖的静态产物。
- Expected Tests:
  - `npm test -- --runInBand src/features/chat/**/*.test.ts*`
  - `npm run build`
  - Python/grep 字符串验证 `dist/assets/*`
- DoD:
  - milestone gate 全绿。
  - dist 字符串扫描结果满足 exit criteria。
  - 完成 C1/C2/C3。
  - `PROGRESS/M215-dist-refresh-and-copy-fix.md` 记录 build hash/验证结果。
- 状态: TODO
