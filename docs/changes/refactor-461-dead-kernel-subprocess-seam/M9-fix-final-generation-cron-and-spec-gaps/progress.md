# refactor-461-M9 — Progress

## Baseline

- Code review CRON-1: M8 的 `active_since` 只说明 Gateway 何时可运行，不能说明具体 job 何时创建或
  重新启用；past-due job 可被错误补投。
- Code review E2E-1: e2e-up 捕获 `GW_PROCESS_START` 用于 rollback，却未在成功 identity gate 中比对它，
  foreign/reused generation 可被当作本轮成功栈。
- R8 verifier: `docs/changes/.../specs/gateway/service-lifecycle.md` 已声明 lifecycle 行为增量，
  canonical `docs/specs/gateway/service-lifecycle.md` 尚未归并，违反 `docs/SPEC_GUIDE.md` 收尾 checklist。

## R1 — Success-path Gateway generation identity

- C1 `a4b563130`: fake Gateway 可发布非本轮 birth、但保持 PID/config/argv 一致，旧 success path
  返回 0；identity 后 fake `ps` birth 漂移而 IM node 已 online 时，旧 readiness path 同样返回 0。
- Status: C2 IN PROGRESS.

## R2 — Cron activation boundary

- C1 `a19b69947`: Gateway active-before-due、job 的 persisted `eligible_at` 却在 due 之后时，旧
  `CronScheduler.tick()` 仍 submit 并写 `last_due_at`，证明 service fence 被误当作 job fence。
- Status: C2 IN PROGRESS.

## R3 — Canonical Gateway lifecycle spec merge

- Status: NOT STARTED.

## R4 — Final gates

- Status: NOT STARTED.
