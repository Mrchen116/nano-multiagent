# refactor-461-M9 — Progress

## Baseline

- Code review CRON-1: M8 的 `active_since` 只说明 Gateway 何时可运行，不能说明具体 job 何时创建或
  重新启用；past-due job 可被错误补投。
- Code review E2E-1: e2e-up 捕获 `GW_PROCESS_START` 用于 rollback，却未在成功 identity gate 中比对它，
  foreign/reused generation 可被当作本轮成功栈。
- R8 verifier: `docs/changes/.../specs/gateway/service-lifecycle.md` 已声明 lifecycle 行为增量，
  canonical `docs/specs/gateway/service-lifecycle.md` 尚未归并，违反 `docs/SPEC_GUIDE.md` 收尾 checklist。

## R1 — Success-path Gateway generation identity

- C1 `2f5a21138`: fake Gateway 可发布非本轮 birth、但保持 PID/config/argv 一致，旧 success path
  返回 0；identity 后 fake `ps` birth 漂移而 IM node 已 online 时，旧 readiness path 同样返回 0。
- C2 `b030d0f3d` + `8e5dc88d6`: public identity 现在必须与本轮 `GW_PROCESS_START` 规范化相等；
  readiness 在每次 nodes 查询前和 online 结果后均检查同一 birth。drift 时 rollback 保留完整证据且不
  signal 外来 generation。高频检查改为脚本内双读 `ps` birth，而非重复 import `main.py`，保持启动预算。
- Target evidence: 两条新 generation regression、既有 rollback-reuse regression，以及原 node-offline
  rollback regression 均通过。
- Status: IMPLEMENTED; e2e-up script suite `10 passed in 90.00s`.

## R2 — Cron activation boundary

- C1 `c8859a742`: Gateway active-before-due、job 的 persisted `eligible_at` 却在 due 之后时，旧
  `CronScheduler.tick()` 仍 submit 并写 `last_due_at`，证明 service fence 被误当作 job fence。
- C2 `d9f19341d`: cron tool 在 add、变更 schedule、disabled→enabled 时写入私有 `eligible_at`；
  scheduler 对 one-shot 先检查该 job 边界，再保留 legacy job 的 Gateway-lifetime/restart fence。
- Target evidence: active-lifetime + cron-tool closure tests `13 passed`；新 C1 以真实 `tick()` 验证不 submit
  且不写 state。
- Status: IMPLEMENTED; full regression pending.

## R3 — Canonical Gateway lifecycle spec merge

- `docs/specs/gateway/service-lifecycle.md` 已机械归并 delta 的 startup confirmation 与 Gateway-owned
  timing migration requirement；`docs/specs/gateway/spec.md` 更新 area 计数，heartbeat/cron 契约补充
  due 后创建、改期和重新启用的 one-shot 不自动回放。
- Status: EDITED; pending documentation commit and verifier review.

## R4 — Final gates

- Narrow static checks、Cron target tests 与 generation regression 已通过；完整 e2e-up script suite
  `10 passed in 90.00s`，Cron scheduler/tool regression bundle `72 passed`。
- Status: IN PROGRESS — full non-e2e、真实 stack up/down 和独立 verifier/reviewer/final code review 待执行。
