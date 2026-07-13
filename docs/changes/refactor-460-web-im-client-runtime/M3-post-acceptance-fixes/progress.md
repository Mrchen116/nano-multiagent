# refactor-460-M3 — Progress

## 启动记录

- 2026-07-13：完整读取 motivation/design、Round 1 verification/acceptance、项目 AGENTS/SPEC/注释与测试规范、worker/systematic-debugging skill；M3 目录起始仅有 `.gitkeep`，无 LOGBOOK。
- worktree：`milestone/refactor-460-M3` 基于 `origin/unit/refactor-460` 的 `e2410713`；初始缺 `node_modules`，执行 `npm ci` 后未改源码。
- 基线：全量 Vitest 62 files / 574 tests passed；`npm run build` passed；ownership contract 3 passed。
- 根因摘要：Chat recovery 仅刷新 conversations；HTTP 401 调 freshness-aware entry 会复用仍 fresh 的旧 token；production cursor 直接调用 sessionStorage，异常可中断 open/dispatch；TanStack 默认吞 refetch error；bind confirm ref 未按 token 分区；toast 仍识别 legacy `message_created` 且未聚合 canonical completion；direct Web IM visibility policy 把 NO_REPLY 当 literal；Agent detail 对同一 summary endpoint 建第二 key；Chat 保留未调用 mention API 和私有 JSON parser；ownership guard 禁止所有非 runtime WebSocket。
- 范围扩展：orchestrator 确认 direct Web IM NO_REPLY 必须在 Gateway canonical responsibility 修复，授权最窄 runtime-delivery policy/tests；不改变外部 channel/其他 delivery context，不由 worker 修改 design。

## R1 — auth/runtime 与 Chat recovery 连续性

- Status: TODO
- Context: Round 1 verification C1/W2/S1，加上 storage throw 会击穿共享 stream。
- Decision: pending C1 red tests.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: 写 C1 红测并逐项确认失败来自目标缺口。

## R2 — bind reconciliation 真实失败与 token 隔离

- Status: TODO
- Context: 默认 QueryClient 的 refetch error 不 reject，现有 mock promise rejection 产生虚假覆盖；confirmed result 未按 URL token 分区。
- Decision: pending C1 red tests.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: R1 完成后进入。

## R3 — 静默回复、在线提醒与 canonical Chat API 收口

- Status: TODO
- Context: acceptance 两项 major 均为真实用户旅程失败，另有 dead/duplicate API seam。
- Decision: pending C1 red tests.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: R2 完成后进入。

## R4 — Agent 详情去重与全量验收

- Status: TODO
- Context: 详情页为仅需 display name 的直聊操作重复拉 Agent summary；M3 完成必须重新跑全部门禁和真栈旅程。
- Decision: pending C1 red tests.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: R3 完成后进入。
