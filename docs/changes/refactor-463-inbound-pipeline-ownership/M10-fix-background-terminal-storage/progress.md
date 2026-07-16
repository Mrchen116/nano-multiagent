# M10 Progress

## 2026-07-16 — Planning

- Round 4 issue fingerprint `heartbeat-late-baseline` 首次出现：consumer 在 scheduler submit 后才统计 transcript，快 run 会把本轮 prompt/ack 纳入基线。
- Round 4 issue fingerprint `heartbeat-terminal-ignored` 首次出现：typed failed/cancelled outcome 被当作普通静默完成并可能 trim。
- Round 4 issue fingerprint `cron-no-delivery-success` 首次出现：支持的 `stream_delivery=None` 路径 submit 后立即写 completed。
- Round 4 issue fingerprint `cron-runs-or2` 首次出现：每次 status update 全量 materialize 无界 runs.jsonl，累计 I/O 为 O(runs²)。
- 正确修复边界：terminal consumption 是 background owner 的必选职责，用户投递/observer 是可选 adapter；持久化 owner 维护单次装载后的 materialized state。

## 2026-07-16 — R1 completed

- Context: scheduler 提交后才由 runner 读取 transcript 行数，快完成 run 会把本轮 prompt/ack 算进 baseline；共享 stream 虽返回 typed terminal，heartbeat consumer 却只按 delivery context 是否静默决定 trim。
- Decision: scheduler 在同步 submit 前构造 immutable `HeartbeatTranscriptBaseline` 并随 `HeartbeatRunRecord` 交给 consumer；共享 background stream 在 context 仍存活时为 failed/cancelled 发出 canonical `run_terminal_reconcile`；heartbeat 只有 `completed` 才允许 silent trim。
- Rationale: transcript 截断依据必须和 submit 保持 happens-before；terminal UI 事件必须在 stream helper pop delivery context 前完成，不能在 consumer 事后补发。
- Evidence:
  - Tests: C1 `717f0e4b5` 精确 4 red；C2 `8a55cd798` 后 heartbeat/stream 聚焦 `37 passed`，相关 Ruff 通过。全量非 e2e 为 `3420 passed, 1 skipped` 加一条外网 DDGS 检查因 `No route to host` 失败；该单例立即独立重跑 `1 passed`，非本分支代码回归。
  - Entry: 通过 `PollingHeartbeatRunner.start()/close()` 公共生命周期驱动快完成 completed 与 failed/cancelled stream；completed 精确回滚到 submit 前 1 条历史，非成功保留本轮 transcript 并发出 failed reconcile。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: 永久回归位于 `test_heartbeat_scheduler.py` 与 `test_heartbeat_session_trim.py`；真 Kernel/公开 cron history 证据在 R2 补齐。
  - Visual/Interaction: N/A（非前端）。
  - Prototype Comparison: N/A（无原型）。
- Rollback: 回退 C2 `8a55cd798` 后恢复 Round 4 已确认缺口；C1 继续稳定复现。
- Commits: C1=`717f0e4b5`, C2=`8a55cd798`, C3=本提交。
- Next: R2 mandatory cron terminal consumer。
