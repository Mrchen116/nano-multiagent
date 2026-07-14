# refactor-461-M9: Final generation, Cron, and canonical-spec gaps — Tasks

> 对齐：`../design.md`、M8 final code review、R8 verifier

## 目标

关闭 M8 之后独立门禁确认的三项交付缺口：e2e-up 成功路径只能接受本轮 spawn 的 Gateway
generation；运行中的 Gateway 不得补投任务到期后才创建或重新启用的 one-shot Cron；设计阶段已有的
Gateway lifecycle delta-spec 必须归并到长青契约层。

## 退出标准

- [ ] e2e-up 在公开 identity 的 PID/config/argv 之外，还验证其 process birth 等于本轮捕获的
  `GW_PROCESS_START`，且 readiness loop 每轮继续验证该 birth；不匹配时 fail closed、不得把外来
  generation 宣布为 ready。
- [ ] `at` Cron 在同一 Gateway 存活期间仍能承受延迟 tick；但 job 在其 due instant 后才新增、改 schedule
  为过去时间、或从 disabled 重新启用时不自动补投，用户须显式 `run` 才立即执行。
- [ ] `docs/specs/gateway/service-lifecycle.md` 归并本 unit 的 delta：PID/liveness-only startup
  confirmation、Gateway-owned timing 的旧值单向迁移与每文件 backup；header 对齐 refactor-461。
- [ ] 精确回归、static、full non-e2e、真实 e2e up/down 通过，随后交 independent verifier、reviewer
  和 final code review。

## 测试策略

- lifecycle generation：扩展 `test_e2e_up_process_ownership.py` fake harness，模拟 identity 出版前
  spawned PID 的 birth 漂移但其他公开字段仍吻合，以及 identity 后 `/nodes` 已 online 时 birth 漂移；
  旧代码错误地成功，修复后拒绝且不 signal 外来进程。
- Cron activation boundary：在 `test_cron_scheduler_active_lifetime.py` 以真实 `CronJobStore` /
  `CronScheduler` 固化 three-way 对比：due 前存在的 job 延迟投递、due 后新增/重启用不投递、显式手动
  `run` 的既有语义不改变。
- canonical spec：对照 `specs/gateway/service-lifecycle.md` delta 逐条机械归并，配 `git diff --check`。

## Roadpoints

### R1 — Success-path Gateway generation identity

- [x] C1 `2f5a21138`：复现 foreign/reused birth 可通过 success identity gate，及 online node
  掩盖 identity 后 birth 漂移。
- [x] C2 `b030d0f3d` + `8e5dc88d6`：identity gate 比较 captured birth，readiness 每轮及 nodes-online
  后持续使用 birth-aware status，且该检查不耗尽 startup budget。

### R2 — Cron activation boundary

- [x] C1 `c8859a742`：复现 due 后创建 `at` 任务经真实 `tick()` 被错误 submit 并写 state。
- [x] C2 `d9f19341d`：持久化 job eligibility boundary，保持 legacy/restart 与 delayed-live-tick 语义。

### R3 — Canonical Gateway lifecycle spec merge

- [x] C3：从 delta-spec 归并并对账 canonical service lifecycle requirement。

### R4 — Final gates

- [ ] C3：记录验证、真实 e2e 与独立验收结论（e2e-up script suite 已通过；full non-e2e 与独立门禁待跑）。
