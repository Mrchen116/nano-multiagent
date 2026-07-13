# refactor-461-M5 — Progress

## Baseline

- Context: unit integration head `d8df1b124` 上执行 post-acceptance fix round 4。
- Scope: `src/personal_assistant/main.py`、`scripts/e2e-up.sh`、`scripts/e2e-down.sh` 与相关 launch/identity/e2e regression；不修改 canonical/acceptance/verification，不发送 P2P。
- Evidence: `/Users/czj/Repos/nano-multiagent/.venv/bin/pytest -m "not e2e" -q` → `3558 passed, 1 skipped, 23 deselected, 16 warnings in 134.59s`，exit 0。
- Plan: R1 startup publication transaction；R2 shared process snapshot + birth identity；R3 e2e rollback/evidence cleanup transaction；R4 automated + real-entry signoff。

## R1 — Startup publication transaction

- Status: DONE。
- Context: parent waiter 成功后 state write 位于 rollback `try` 外；foreground handler 安装后 identity/PID publication 位于 `try/finally` 外；失败 child 的第二次 wait timeout 被 suppress，caller 无法区分已回收与仍存活。
- Decision: background start confirmation 与 atomic/durable state publication 组成一个 post-spawn transaction。任一步失败先 TERM/process-group TERM，再 KILL/process-group KILL 并二次确认；确认退出后只条件清本 PID/identity/state，未确认则抛 `GatewayProcessCleanupError(pid)` 并保留全部 evidence。外层 `GatewayStartupError` 以 `ExceptionGroup` 同时保留 startup cause 与 cleanup failure。foreground 从 identity build 起全部进入 handler `try/finally`，identity、PID、state 共用 atomic write + file fsync + replace + directory fsync primitive，finally 只按本 identity/PID 条件删除。
- Rationale: publication 也是启动成功的一部分；只要 operator state 不可持久化，就不能返回一个无法正常管理的“成功” child。cleanup 的 confirmed/failed 结果必须成为控制流事实，不能由 suppress 猜测。
- Evidence:
  - Tests: startup publication + launch + process identity + PID lifecycle + forced stop → `37 passed, 2 warnings in 2.02s`。
  - Entry: public `launch_gateway_in_background()` 覆盖 state post-write failure 与二次 wait timeout；public `run_gateway()` 覆盖 identity/PID publish failure 和 handler restore。真实入口统一在 R4 执行。
  - Frontend State Matrix: N/A。
  - Browser QA: N/A。
  - E2E/Regression: `tests/unit/personal_assistant/test_gateway_startup_publication.py`；非长驻 public lifecycle regression，marker 无。
  - Visual/Interaction: N/A。
  - Prototype Comparison: N/A。
- Debug note: 首轮 Green 的 cleanup-failure case 传入 `subprocess.TimeoutExpired`，但共享 `_FakeProcess` 只对 `TimeoutError` 执行 raise，导致 timeout 被当普通 wait 返回值。逐字追栈后确认是 C1 夹具未进入预期边界，不是 cleanup 实现；改为 fixture 支持的 `TimeoutError`，并把 child evidence 移到 spawn 时写入，避免 launch preflight 把预置 stale PID 清掉。
- Rollback: 回退 `704f770ce` 恢复非原子 PID/state publication 和 suppress cleanup；C1 两提交保留失败契约。
- Commits: C1=`87e730077`,`e53c6e431`；C2=`704f770ce`；C3=本提交。
- Next: R2 shared process snapshot and birth identity。

## R2 — Shared process snapshot and birth identity

- Status: TODO。

## R3 — e2e rollback and evidence cleanup transaction

- Status: TODO。

## R4 — Full validation and live signoff

- Status: TODO。
