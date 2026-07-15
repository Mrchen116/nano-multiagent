# refactor-463-M3 — Progress

## 启动基线

- Context: M2 及正式签收 closure 已合入并推送 `unit/refactor-463`；milestone worktree 从 `origin/unit/refactor-463` 的 `a3ce27d93170fb13cde7f7c8004ab5df198a8ab1` 创建。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m 'not e2e' -n 4 --dist worksteal` 收集 3370 items 并全绿。
- Leader alignment: M3 必须原子迁移 queue/active/steer/stop/terminal，保留 M2 O(1) seal/async settle/shared-deadline drain；live 证据必须是隔离真 Gateway + IM + LLM 的用户可见结果，pytest/stub 仅作回归补充。

## R1 — 建立 coordinator admission 与线性化 owner

- Context: 旧 pipeline 用 queue active set、active map、active-map lock 与 drain lock 分别协同；normal `kernel.submit()` 后还要 await active-map lock 才发布 marker，stop/steer 因而可能观察 Kernel 已接纳但 Gateway 仍 idle。M2 queue lifecycle 已闭合，M3 只能私有复用，不能另写 queue。
- Decision: 新增 concrete `SessionRunCoordinator` 与 frozen `InboundRunRequest` / `StopRunRequest`。Coordinator 私有持有原 `SessionRunQueue`、active/interrupt state 与 bounded per-session transition locks；normal queue head 在同一 lock 内 resolve/prepare，同步 `submit()` 后下一语句发布 marker且中间无 await；steer 在同一 lock 内完成 active-check、binding、destructive group drain、image resolve 与 atomic submit，lost-race 只把同一 prepared parts 交 FIFO fallback。stop 在该 lock 内执行 mark -> interrupt -> append，terminal finally 以同一 lock 单点清 marker。
- Rationale: queue 继续只负责 FIFO/resource lifecycle，coordinator 隐藏跨 queue、Kernel 与 delivery 的 session state machine；调用方只需 dispatch/stop/is_session_busy/seal/settle/drain。transition lock 统一取代旧 active-map/drain 双锁观察，且只串行同 session，不影响跨 session 并行。
- Evidence:
  - Tests: `pytest -q test_session_run_coordinator_admission.py test_run_queue.py test_gateway_session_binder.py test_test_naming_and_size_contract.py` -> 15 passed；`ruff check src tests` -> passed；`pytest -m 'not e2e' -n 4 --dist worksteal` -> 3373 passed, 1 skipped（32.69s）。
  - Entry: public coordinator dispatch 覆盖同 session lost-steer fallback 串行、另一 session 同时进入 stream；连续两次 steer 共用 original run/stream；accepted lifecycle 的首个 post-submit await 被故意暂停时，public stop 已观察完整 `run-1` marker并按固定顺序 interrupt/append。R1 是尚未切生产 façade 的内部 owner，真 Gateway/IM/LLM 入口统一在 R3 一次切线后验证，避免双 owner 中间态冒充 live evidence。
  - Frontend State Matrix: N/A（无前端变更）。
  - Browser QA: N/A（无前端变更）。
  - E2E/Regression: `tests/unit/personal_assistant/test_session_run_coordinator_admission.py` 永久覆盖 public admission；steer lost-race 断言第二消息的 image resolver 只调用一次，group buffer 只 destructive drain 一次，steer/fallback parts 完全相同。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Debugging note: 首轮 Green 运行在 `ControlledKernel.wait_stream("run-1")` 稳定触发 `KeyError`。逐栈反查确认 dispatch task 尚未获得首个 event-loop turn，测试 helper 就索引尚未由 sync submit 建立的 event；产品逻辑尚未运行，不是 coordinator 并发缺陷。对照既有 event-based test pattern 后，单一假设用 submit-change event 验证为真；helper 改为等待“run event 已创建 / submit count 已到达”的明确条件并带 timeout，没有加入猜测 sleep，随后 7 个聚焦测试全绿。
- Rollback: 回退 C2 `ce9eddc2d` 删除新 owner/DTO，现有生产 pipeline 完全未切线；C1 可随同回退。
- Commits: C1=`1bf7c7e1c`；C2=`ce9eddc2d`；C3=本次 docs commit。
- Next: R2 C1 锁定 terminal/stop/watchdog/NO_REPLY/failure 与 narrow façade 的 public behavior。

## R2 — 迁入 stop/terminal/watchdog 并收窄 pipeline

- Context: 待完成。
- Decision: 待完成。
- Rationale: 待完成。
- Evidence: 待完成。
- Rollback: 待完成。
- Commits: C1=待完成；C2=待完成；C3=待完成。
- Next: R1 完成后开始。

## R3 — 切换 composition/heartbeat/contracts 并完成真栈验收

- Context: 待完成。
- Decision: 待完成。
- Rationale: 待完成。
- Evidence: 待完成。
- Rollback: 待完成。
- Commits: C1=待完成；C2=待完成；C3=待完成。
- Next: R2 完成后开始。
