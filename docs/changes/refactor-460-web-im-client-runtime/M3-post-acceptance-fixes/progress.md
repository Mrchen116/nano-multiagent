# refactor-460-M3 — Progress

## 启动记录

- 2026-07-13：完整读取 motivation/design、Round 1 verification/acceptance、项目 AGENTS/SPEC/注释与测试规范、worker/systematic-debugging skill；M3 目录起始仅有 `.gitkeep`，无 LOGBOOK。
- worktree：`milestone/refactor-460-M3` 基于 `origin/unit/refactor-460` 的 `e2410713`；初始缺 `node_modules`，执行 `npm ci` 后未改源码。
- 基线：全量 Vitest 62 files / 574 tests passed；`npm run build` passed；ownership contract 3 passed。
- 根因摘要：Chat recovery 仅刷新 conversations；HTTP 401 调 freshness-aware entry 会复用仍 fresh 的旧 token；production cursor 直接调用 sessionStorage，异常可中断 open/dispatch；TanStack 默认吞 refetch error；bind confirm ref 未按 token 分区；toast 仍识别 legacy `message_created` 且未聚合 canonical completion；direct Web IM visibility policy 把 NO_REPLY 当 literal；Agent detail 对同一 summary endpoint 建第二 key；Chat 保留未调用 mention API 和私有 JSON parser；ownership guard 禁止所有非 runtime WebSocket。
- 范围扩展：orchestrator 确认 direct Web IM NO_REPLY 必须在 Gateway canonical responsibility 修复，授权最窄 runtime-delivery policy/tests；不改变外部 channel/其他 delivery context，不由 worker 修改 design。

## R1 — auth/runtime 与 Chat recovery 连续性

- Status: DONE
- Context: Round 1 verification C1/W2/S1，加上 storage throw 会击穿共享 stream。
- Decision: auth session 暴露复用原 module-level promise 的 force-refresh entry，HTTP 401 必经该入口；runtime 在持久 cursor port 外维护 per-user 单调内存 cursor，storage 异常只上报不阻断 resume/event/ping；Chat recovery settled 刷新 active messages、conversations、agents、nodes；ownership guard 只匹配 `/im/ws/user` endpoint。
- Rationale: expiry freshness 只能回答 token 是否过期，不能推翻服务端 401；cursor 的 transport 连续性不能依赖可能被浏览器策略禁用的 storage；resync 会前移 cursor，故领域 callback 必须在同一 recovery 中重读所有可能漏失的权威快照。
- Evidence:
  - C1 红测：fresh future-exp token 只产生 2 次 fetch 并把旧 token replay 到 refresh mock；storage `SecurityError` 在 socket open 直接抛出；recovery 后只有 conversation title 变化，消息/Agent/Node 仍旧。
  - C2 定向：auth session/fetch、user-stream、Chat workspace 4 files / 60 tests passed；frontend build passed；ownership contract 3 passed。
  - Recovery integration 实际调用 captured callback，把四个 REST response 切到新 snapshot，断言旧消息消失、新消息出现、标题/Agent initials/Node 名与 offline chip 一起收敛。
- Rollback: 回退 C2 `ec4f3a3a`；C1 `b09c9609` 保留可观察缺口。
- Commits: C1=`b09c9609`, C2=`ec4f3a3a`, C3=本提交。
- Next: R2 用真实 QueryClient 锁定 bind refetch failure 与 token A/B 隔离。

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
