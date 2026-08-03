# refactor-489-M7 — Progress

## Startup Baseline

- Context: 派发范围为 32 个 scheduling/background/liveness 测试文件与 M7 产物，不改产品代码或 spec。
- Decision: 以 M1 的受影响测试处置表为交付接口，按风险簇建表，不做全仓台账。
- Evidence:
  - Baseline: `origin/unit/refactor-489@1a4eecaff` 上运行全部 M7 匹配文件，`229 passed, 2 warnings in 5.27s`。
  - Scope: `git ls-files` 精确命中 32 个文件。
- Next: R1 删除迁移基线与假链路。

## Paused Out-of-Unit Finding — heartbeat expired-at 语义

- Context: current spec 与当前产品实现/测试对 heartbeat 过期一次性 `at` 任务的语义相反。
- Direct evidence:
  - Spec: `docs/specs/gateway/heartbeat-cron.md` 的“过期的一次性任务不补跑” scenario 同时覆盖 cron/heartbeat。
  - Source: `src/personal_assistant/scheduler/heartbeat_scheduler.py` 构造 `_AtSchedule(..., check_expiry=False)`，过期后仍触发。
  - Test: `tests/unit/personal_assistant/test_schedule_primitives.py::TestAtSchedule::test_heartbeat_mode_fires_even_when_expired` 直接锁定该当前行为。
- Decision: 按 orchestrator 裁决保留该测试，暂停此时序簇；M7 不改产品/spec、不创建 issue，交付时列为 out-of-unit 后续修复候选，不声称已解决。

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| 统一 heartbeat 过期一次性 `at` 任务与 current spec 的不补跑语义 | `docs/specs/gateway/heartbeat-cron.md` + product code/test follow-up unit | heartbeat scheduler | 本页 `Paused Out-of-Unit Finding` 的 spec→source→test 证据 |
