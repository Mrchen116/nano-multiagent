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

## 2026-07-16 — R2 completed

- Context: `CronExecutionService` 把 Kernel stream consumption 和可选 IM observer 合成 nullable `stream_delivery`；当 observer 不可用时直接把 submitted run 写成 `completed/no_delivery_path`，真实 failed/cancelled/missing-terminal 永远无人消费。
- Decision: runner-based service 构造期强制要求 `CronTerminalConsumerPort`；concrete `CronRunTerminalConsumer` 始终消费 shared stream，只把 observer 作为可选 adapter；composition root 无条件构造 terminal consumer。仅 typed `completed` 写 awareness，其他终态原样持久化，stream/missing-terminal 失败写 `stream_failed`。
- Rationale: Kernel run 的生命周期属于 cron execution owner，IM 是否在线或 owner id 是否可用只影响投递，不能改变 run 的事实终态。
- Evidence:
  - Tests: C1 `5c25fb9bb` 为 5 red；C2 `b051f7c5b` 后 owner/composition/shutdown/shared-stream 聚焦 `38 passed`。全仓 Ruff 通过；非 e2e `3426 passed, 1 skipped, 20 deselected`。
  - Entry: `CronExecutionService.enqueue()` 公共入口在 no-observer 配置下分别从 accepted/running 收敛到 completed/failed/cancelled；missing terminal 收敛 failed，`runs_store.list_by_job()` 返回真实 terminal，只有 completed 调用 awareness。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: 永久回归位于 `test_cron_execution_owner_chain.py`；真 Kernel + fixture + CronTool/history 证据在 milestone verification 补齐。
  - Visual/Interaction: N/A（非前端）。
  - Prototype Comparison: N/A（无原型）。
- Rollback: 回退 C2 `b051f7c5b` 将恢复 no-delivery 伪 completed；C1 会重新阻断。
- Commits: C1=`5c25fb9bb`, C2=`b051f7c5b`, C3=本提交。
- Next: R3 incremental cron history owner。

## 2026-07-16 — R3 completed

- Context: `CronRunsStore.update_status()` 每次都从 `runs.jsonl` 全量 replay，单个 run 的多次状态更新会让累计文件读取量随历史长度增长，长期形成 O(runs²) I/O；旧测试还混在超大 delivery-chain 文件中，无法单独钉住存储 owner 的复杂度和并发语义。
- Decision: store 首次使用时在 `RLock` 内 materialize 一次 owner-wide index；后续 append/update 先 durable append，再原子发布内存索引。update 在同一锁内完成 read/build/append，restart 由新实例重新 replay 一次，未知 request 继续保持 no-op。run-history 回归拆到专属测试文件。
- Rationale: append-only JSONL 是 durable truth，进程内 index 是同一个 owner 的增量读模型；锁住“基于旧状态生成新状态 + durable append + index publish”才能同时避免重复 replay 和并发 lost update。
- Evidence:
  - Tests: C1 `cec690a31` 精确暴露 25 次 update + 2 次 list 触发 `27` 次文件读取（期望 `1`）；C2 `437159d83` 后 run-history/delivery/owner/tool/size-contract 聚焦 `46 passed`。全仓 Ruff 通过；非 e2e `3426 passed, 1 skipped, 20 deselected`。
  - Entry: 新 `test_cron_run_history.py` 从公开 `append/update_status/list_by_job` 驱动首次装载、60 条并发 append/update、restart、newest/limit 与 stale convergence；instrumented `Path.read_text` 证明同一实例只读一次。
  - Frontend State Matrix: N/A（非前端）。
  - Browser QA: N/A（非前端）。
  - E2E/Regression: 真 Kernel + 高位 Anthropic fixture 通过公开 `CronTool add/run/runs` 接受运行；在拿到真实 `kernel_run_id` 后通过公开 `kernel.cancel()` 产生 typed `cancelled`，`observer=None` 的 mandatory terminal consumer 将 history 收敛为 `cancelled` + `finished_at`，且 transcript 无 awareness。完整记录见 `evidence/live-no-observer-cron-terminal.md`。
  - Visual/Interaction: N/A（非前端）。
  - Prototype Comparison: N/A（无原型）。
- Rollback: 回退 C2 `437159d83` 后 instrumented regression 恢复为每次 update 全量读；并发/restart 行为仍由同一专属测试文件守护。
- Commits: C1=`cec690a31`, C2=`437159d83`, C3=本提交。
- Next: rebase 含 M9 的 `unit/refactor-463`，重跑 milestone/full gate，合入并清理 worktree/fixture。
