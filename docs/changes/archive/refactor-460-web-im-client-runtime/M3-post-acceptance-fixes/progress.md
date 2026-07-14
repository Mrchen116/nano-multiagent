# refactor-460-M3 — Progress

## 启动记录

- 2026-07-13：完整读取 motivation/design、Round 1 verification/acceptance、项目 AGENTS/SPEC/注释与测试规范、worker/systematic-debugging skill；M3 目录起始仅有 `.gitkeep`，无 LOGBOOK。
- worktree：`milestone/refactor-460-M3` 基于 `origin/unit/refactor-460` 的 `e2410713`；初始缺 `node_modules`，执行 `npm ci` 后未改源码。
- 基线：全量 Vitest 62 files / 574 tests passed；`npm run build` passed；ownership contract 3 passed。
- 根因摘要：Chat recovery 仅刷新 conversations；HTTP 401 调 freshness-aware entry 会复用仍 fresh 的旧 token；production cursor 直接调用 sessionStorage，异常可中断 open/dispatch；TanStack 默认吞 refetch error；bind confirm ref 未按 token 分区；toast 仍识别 legacy `message_created` 且未聚合 canonical completion；direct Web IM visibility policy 把 NO_REPLY 当 literal；Agent detail 对同一 summary endpoint 建第二 key；Chat 保留未调用 mention API 和私有 JSON parser；ownership guard 禁止所有非 runtime WebSocket。
- 范围扩展：orchestrator 确认 direct Web IM NO_REPLY 必须在 Gateway canonical responsibility 修复，授权最窄 runtime-delivery policy/tests；不改变外部 channel/其他 delivery context，不由 worker 修改 design。
- 第二次范围扩展：修复 Gateway policy 后，真 WS 取证发现 repository 直接插入 tombstone 未触发 live notify，且 replay wire 把 nullable FK 覆盖到 payload 的 provisional id。orchestrator 授权仅修这两处 IM seam，并要求 ordinary/external delivery 回归与真实 UI 撤泡证明。

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

- Status: DONE
- Context: 默认 QueryClient 的 refetch error 不 reject，现有 mock promise rejection 产生虚假覆盖；confirmed result 未按 URL token 分区。
- Decision: 每组 owner-derived invalidation 传入 `throwOnError: true`，仍以 `Promise.allSettled` 等待六组完成后汇总失败；confirmed result 改为 `{token,result}`，仅 same-token reconciliation retry 复用。
- Rationale: TanStack 默认把 queryFn error 收进 query state 并 resolve invalidate promise，必须显式传播；bind token 是一次性资源，但复用边界是该 token，不是组件 lifetime。
- Evidence:
  - C1 红测：真实 QueryClient 第一组 queryFn 抛错时页面仍导航且无 alert；A confirm 后 `/me` 失败，SPA query 改为 B 后只调用过 A。
  - C2：`bind-confirm-page.test.tsx` 4 tests passed；测试用六组真实 query cache 证明失败不导航、same-token retry 不二次 confirm、全成功才导航；A→B 调用序列为 `[bind-a, bind-b]`。frontend build passed。
- Rollback: 回退 C2 `f58ba4f7`；C1 `b5b6d50f` 保留真实失败与 token 隔离回归。
- Commits: C1=`b5b6d50f`, C2=`f58ba4f7`, C3=本提交。
- Next: R3 修 direct Web IM NO_REPLY canonical policy、在线 Agent toast 与 Chat API 残余。

## R3 — 静默回复、在线提醒与 canonical Chat API 收口

- Status: DONE
- Context: acceptance 两项 major 均为真实用户旅程失败，另有 dead/duplicate API seam。
- Decision: `RunDeliveryContextStore` 仅为 `web_relay`（含 direct Web IM）启用 protocol-token suppression，保留任意非 Web shadow transport 的 literal policy；全局 toast 按 message id 暂存 canonical `message.created` 的 Agent 身份，在 `message.completed` 取最终正文后提醒并 invalidation 权威 conversations；Chat JSON 调用统一进入 `authFetchJson` 的 operation-label error seam，删除 dead mention API/initials。
- Rationale: direct Web 的 provisional bubble 与 tombstone 都由 Gateway runtime delivery 所有，UI 隐藏文本不能修复已落库历史；canonical completion 缺 sender、created 缺正文，必须跨事件聚合；未读/preview/排序由服务端维护，completion 后 refetch 才不会重复推算；operation label 下沉共享 auth seam 可复用 refresh/401/A→B 语义同时保持旧错误文本。
- Evidence:
  - C1 红测：direct Web lifecycle context 仍为 `literal_text`；canonical Agent completion toast 保持 `null` 且未 refetch；architecture guard 报出 `listMentionCandidates` / `initialsFrom` / `jsonOrThrow` 三个残余。`listConversations failed: 503 temporarily unavailable` 文案锁定并保持通过。
  - C2 Gateway：relay lifecycle + heartbeat delivery 两文件 42 tests passed；新增 FK-enforced real Gateway handler 路径证明 `turn_start → message_discarded` 后刷新历史消息表为零；非 Web shadow 保持 literal。相关 Python ruff passed。
  - C2 frontend：auth/chat API/architecture/toast/reducer/workspace 6 files / 92 tests passed；真实 QueryClient 第二次请求返回 `unread_count=1`、最终 preview 和置顶排序，非当前会话弹 Planner toast，当前会话不弹；frontend build passed。
- Rollback: 回退 C2 `42083438`；C1 `9c7dff4f` 保留根因回归。
- Commits: C1=`9c7dff4f`, C2=`42083438`, C3=本提交。
- Next: R4 删除 Agent detail 重复 summary query，并完成全量门禁和真栈验收。

## R4 — Agent 详情去重与全量验收

- Status: DONE
- Context: 详情页为仅需 display name 的直聊操作重复拉 Agent summary；Gateway policy 修复后的真实 WS 又暴露 tombstone live publish/replay identity 两个 IM 缺口。
- Decision: Agent detail 只保留编辑 draft，以 `draft.display_name || agentId` 创建 direct chat；`MessageRepository.discard_running_agent_message()` 在事务提交后调用已有 `_notify` 一次；wire data 仅在 event FK 非空时以 FK 覆盖 payload，nullable tombstone FK 保留 payload provisional id。
- Rationale: Open chat 不应维护第二份 summary cache；app 为普通事件由 `EventRepository` notify，而 discard 路径绕过该 repository 直接插入 event，故必须在消息事务完成后显式发布且不能事务内重复；tombstone 删除消息行后 FK 必然为空，provisional id 的唯一权威来源是 payload，普通事件仍以 FK 防御 stale payload。
- Evidence:
  - C1 Agent detail 红测：首次详情加载仍发生第二次 summary fetch；修复后 27/27 tests passed，production build passed。
  - C1 IM 红测：EventBridge 未配置 notify 的真实装配下，discard 后 repository callback 为 0 次；wire replay 把 payload provisional id 覆盖成 `None`。修复后 event bridge/user stream/Gateway focused selection 15 passed，ordinary/external/heartbeat 集中回归 66 passed。
  - 全量：frontend 62 files / 581 tests passed，production build passed；`ruff check src tests` passed；`pytest -m "not e2e"` 3505 passed / 1 skipped / 23 deselected。
  - 真栈：`e2e-critical.sh -m "not slow"` 15 passed / 2 deselected；真实 Gateway/IM/LLM/WS 与 Playwright 验证 NO_REPLY provisional bubble 在线撤销且 reload 后无 Agent row，非当前 Agent reply 同步 toast + unread + preview + 置顶，Agent 详情 Open chat 进入新 direct conversation。完整记录与截图见 `evidence/acceptance.md`。
  - 全量 e2e 首次运行已先通过 7 条路径，随后既有 slow heartbeat wait 命中 pytest 全局 timeout；按脚本支持的 `not slow` profile 重跑后所有 15 条非 time-driven 路径通过。
- Rollback: 回退 Agent detail C2 `85f58218` 与 IM tombstone C2 `f662b8f2`；C1 `9bfac678` / `e854260b` 保留缺口回归。
- Commits: Agent detail C1=`9bfac678`, C2=`85f58218`; tombstone feedback C1=`e854260b`, C2=`f662b8f2`; C3=本提交。
- Next: milestone 合入 `unit/refactor-460`，由 orchestrator 进入 unit-level verification/review。
