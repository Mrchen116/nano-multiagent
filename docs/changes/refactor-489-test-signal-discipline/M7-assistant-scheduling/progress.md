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

## R2 — 收敛 cron 工具、调度与执行保护

- Context: cron 切片同时有 public action/schema 风险和 description/provenance 措辞基线；job/store/scheduler 重复测 dataclass getter、固定文件布局、空列表与私有 `_compute_due_jobs`；runner 用两个测试分别锁“不传某 kwarg”和“使用返回 session”，history 还锁了内部文件读取次数。
- Decision: 将 cron tool 收敛为当前 action/schema 和结构化 history 结果，不锁 description；用参数化权限结果保护读/写分类；用一个 store roundtrip 覆盖持久化/update/remove/enabled filter；cron/at 只经公开 `tick()` 证明 wiring；runner 用 strict shim 返回的 session id 实际进入 submit 取代反向 kwarg 断言。保留 admission linearization、terminal owner、run history restart/concurrency、manual-run per-agent isolation 与 drain 收拢。
- Rationale: 这些断言直接经过 model/tool/Gateway 使用的 seam，而不依赖实现如何读文件或传参。真实并发与关机风险未以“可能不稳”为由删除。
- Evidence:
  - Tests: 全部当前 `test_cron*.py` + `test_schedule_primitives.py` 运行 `83 passed, 1 warning in 1.99s`。
  - Entry: `cron` tool 从 public `run()` 验证 add/list/remove/run/runs；scheduler 从 public `tick()` 验证 every/cron/at；Gateway startup 保留真线程收敛 stale runs。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面代码变更）。
  - E2E/Regression: `test_cron_tool_public_shape.py`, `test_cron_tool_closure.py`, `test_cron_scheduler_tick.py`, `test_cron_execution_owner_chain.py`, `test_cron_run_history.py`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
  - Quality: focused `ruff check` 通过；cron 切片已无 `inspect.getsource` / source-negative / private `_compute_due_jobs` 测试。
- Rollback: 回退本 R 提交至 `b6ef951af`。
- Commits: 本 R 提交（SHA 以 Git history 为准）。
- Next: R3 收敛 heartbeat 节律、开关与 session 保护。

## R3 — 收敛 heartbeat 节律、开关与 session 保护

- Context: heartbeat scheduler 同时用多个测试重复证明 config cadence 和 enabled gate，并锁定退役的 Markdown top-level interval、多 schedule parser、私有 payload tuple 与 transcript ownership；canonical binding 又分别测 store method 存在、私有 SQL 排序、预填 map 和 tick-time lookup。
- Decision: cadence 保留 live config、config-over-Markdown、默认 30m 和 per-task rhythm；enabled 正反例合并到 mixed-agent 行为，active hours 参数化覆盖窗口内外；canonical session 用一次真实 binder lookup 同时证明不创建 fallback 且 submit 使用当前 binding，stable-session 测试明确让两个 tick 都到期。保留 model route、agent metadata、busy session、revision ownership、silent cleanup 与 reply visibility。
- Rationale: 保留测试直接穿过公开 scheduler `tick()` 并检查用户/运维可观察结果；删除的 parser/tuple/方法存在断言只保护内部形状。stable-session 原测试没有证明第二个 tick 到期，显式设置 1s config cadence 后才真正覆盖复用风险。
- Evidence:
  - Tests: 全部当前 `test_heartbeat*.py` + `test_schedule_primitives.py`，`37 passed in 0.33s`。
  - Entry: `HeartbeatScheduler.tick()` 覆盖 live catalog、gate、cadence、active hours、canonical lookup/session reuse/runtime refresh、model 与 metadata route。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（零用户面代码变更）。
  - E2E/Regression: `test_heartbeat_scheduler_config_every.py`, `test_heartbeat_scheduler_gate.py`, `test_heartbeat_session_binding.py`, `test_heartbeat_session_trim.py`, `test_heartbeat_reply_visibility.py`。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
  - Quality: focused `ruff check` 通过；[#224](https://github.com/Mrchen116/nano-multiagent/issues/224) 对应的 expired-at 测试原样保留，未把冲突升级为已解决。
- Rollback: 回退本 R 提交至 `616ccf150`。
- Commits: 本 R 提交（SHA 以 Git history 为准）。
- Next: R4 稳定 background / polling / liveness 时序保护。

## Promotion Candidates

| Candidate | Suggested owner | Scope | Evidence |
|---|---|---|---|
| 统一 heartbeat 过期一次性 `at` 任务与 current spec 的不补跑语义 | `docs/specs/gateway/heartbeat-cron.md` + product code/test follow-up unit | heartbeat scheduler | 本页 `Paused Out-of-Unit Finding` 的 spec→source→test 证据；[#224](https://github.com/Mrchen116/nano-multiagent/issues/224) |
