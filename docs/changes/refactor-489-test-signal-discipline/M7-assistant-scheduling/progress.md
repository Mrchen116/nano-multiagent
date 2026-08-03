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
- Decision: 按 orchestrator 裁决保留该测试，暂停此时序簇；M7 不改产品/spec，交付时列为 out-of-unit 后续修复候选，不声称已解决。后续由 [#224](https://github.com/Mrchen116/nano-multiagent/issues/224) 跟踪。

## R1 — 删除迁移基线与假链路

- Context: 派发切片中有 OpenClaw 逐字 prompt/provenance、已退役 prompt vars/参数、module/class/interface exists，以及测试内手写 stream/context seeding 后再断言自己结果的临时基线。`test_heartbeat_im_delivery.py` 又在 unit 层跨 PA→IM DB 重述了 delivery 链路。
- Decision: 删除无当前风险的历史措辞/布局断言和自证假链路；将 heartbeat 静默风险收敛为 `reply_visibility` 上的 current `HEARTBEAT_OK` 协议断言，主动冒泡仍由现有 critical-path E2E 拥有；保留 cron enqueue/history/startup、awareness 和 heartbeat silent-run cleanup 的实际产品调用。
- Rationale: 精确协议 token 是 current spec 允许的文本断言；上游项目原文、来源注释和退役符号不是本仓当前契约。已有 E2E 保护用户冒泡，unit 不再复制 IM 全链路。
- Evidence:
  - Tests: `pytest -q` 运行 `test_heartbeat_reply_visibility.py` + 保留的 background/cron delivery/cron awareness/heartbeat trim，`26 passed, 1 warning in 2.44s`。
  - Entry: `tests/e2e/critical_paths/test_heartbeat_bubble_critical_path.py` 仍可收集；与上述保留 unit 合计 `27 tests collected`。本 milestone 不运行 slow/live E2E。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面代码变更）。
  - E2E/Regression: 保留 `test_heartbeat_bubble_critical_path.py::test_heartbeat_bubbles_actionable_message`，collect-only PASS；本 R 的回归是 `test_heartbeat_reply_visibility.py`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Rollback: 回退本 R 提交至 `b13ca469b`。
- Commits: 本 R 提交（SHA 以 Git history 为准）。
- Next: R2 收敛 cron 工具、调度、执行与历史测试。

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| 统一 heartbeat 过期一次性 `at` 任务与 current spec 的不补跑语义 | `docs/specs/gateway/heartbeat-cron.md` + product code/test follow-up unit | heartbeat scheduler | 本页 `Paused Out-of-Unit Finding` 的 spec→source→test 证据；[#224](https://github.com/Mrchen116/nano-multiagent/issues/224) |
