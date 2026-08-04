# refactor-489-M19 — Progress

## Baseline / Audit

- Claim: PR #227 frontend CI failure is deterministic test-harness queue interference, not a production user-stream ordering defect.
- Baseline: `origin/unit/refactor-489@bb47d8c50` (archived unit head), clean branch `milestone/refactor-489-M19-fix-frontend-ci`; CI workflow run `30800996075`, frontend job `91645258513` reported the same three cases.
- Method: 完整读取 archived motivation/design、M16 task/progress、current IM user-stream contract、frontend README/package/Vite config、CI workflow、testing/evidence/change workflow rules与 `change-impl-worker` / `systematic-debugging` instructions；比较 M16 R3 将精确时间推进替换为 next-timer 的 diff；随后以 Node `v20.20.2` 在本 worktree 执行 clean `npm ci` 和定向 Vitest。
- Result: clean Node 20 first run 与连续三次 baseline 都是 `15 tests | 3 failed`：ping case 未见 `{"op":"ping"}`，epoch-resync 与 later-corruption cases 均在 `FakeSocket.instances[1]` 为 `undefined` 时调用 `open()`。
- Locator: 测试 `user-stream.test.ts:141/341/411`；runtime 在 `user-stream-runtime.ts:330-334` 安排 ping interval，在 `255-263` 安排 retry，并在 `286-320` 的 async `beginConnection()` 创建 socket。
- Limit: Vitest/jsdom + fake socket 只能证明 queue/transport state seam；不替代真实 browser 或 IM service validation。该 milestone 不改 production runtime，因此不引入新的产品验证范围。

## R1 — 固定 CI 基线与时序因果链

- 状态: DONE
- Context: M16 R3 把三个相关 case 的确定性 `advanceTimersByTimeAsync(...)` 改为单次 `advanceTimersToNextTimerAsync()`，意图避免把 1s/25s 常量当作产品契约。CI Linux clean environment 随即稳定出现三个 failure。
- Decision: 在未修改 source 的 clean Node 20 worktree 中重复运行原 suite；临时 trace `vi.getTimerCount()` 与 mocked `Date.now()`，并阅读 Vitest 3.2.4 的 `advanceTimersToNextTimerAsync` 实现和 M16 之前的通过版本，先建立时序证据再选择最小修复。
- Rationale: “next timer”只在队列从 test-owning timer 开始时等价于“next runtime timer”；若 runner 已有 timer，单次推进不保证驱动 ping/retry。三个不同外显失败指向同一同步前提，而不是三个 runtime 缺陷。
- Evidence:
  - Tests: `npm run test -- src/realtime/user-stream/user-stream.test.ts` 在 Node 20 连续 3 次均为 `12 passed / 3 failed`，失败位置和 CI 一致。
  - Queue trace: `vi.useFakeTimers()` 后、runtime setup 前为 1 个 timer；socket open 后为 2 个。首次 `advanceTimersToNextTimerAsync()` 后 mocked clock 保持原值、timer 数变为 1、`sent` 仍只有 resume frame。这说明该次推进消费的是继承 timer，而非 runtime 的 25s ping/retry timer。
  - Code/pattern: M16 R3 diff 是唯一改变这三个 wait 的近期提交；runtime 的 `onopen` 同步挂入 ping interval，close/resync failure 均先调用 `scheduleReconnect()`，没有产品顺序反转或丢失 retry 的证据。
  - CI: `.github/workflows/ci.yml` 明确为 Node 20、`npm ci`、`npm run test`；本地 clean run 精确复现，因此不依赖环境猜测。GitHub job log 查询遇到两次 TLS handshake timeout，但父任务提供的 job id / failure positions 与本地结果一致。
- Rollback: 本 milestone 仅改测试 harness；回退该行即可恢复原先的 queue interaction，无 production data 或 runtime 迁移。

## R2 — 在 runtime harness 边界隔离继承 timer

- 状态: DONE
- Context: three tests first call `setup()`, then subscribe/open a fake socket and advance the next timer. The inherited timer can exist between `beforeEach` and the test body, so clearing in `beforeEach` is too early; the runtime setup boundary is the last point before the test creates its own queue.
- Decision: 在 common `setup()` 的第一行调用 `vi.clearAllTimers()`，带注释说明只隔离 Vitest/jsdom worker 已携带的 timer。保留每个 case 原有的 `advanceTimersToNextTimerAsync()`、`settle()`和对 ping/second socket/recovery/cursor/event 的 assertions。
- Rationale: 这不是删断言、延长睡眠或重试。它明确隔离 test harness 的外部 queue，令“next timer”准确对应本测试刚创建的 runtime timer，同时继续检查原有产品风险。
- Evidence:
  - Tests: Node 20 clean dependency tree 上，修复后的定向 suite `15 passed`。
  - Scope: only `src/IM/frontend/src/realtime/user-stream/user-stream.test.ts` changed in code; no `user-stream-runtime.ts`, adapter, config, product or spec changes.
  - Production assessment: current runtime's open → resume → interval and close/resync failure → reconnect paths match the behavior asserted by the test once its timer queue is isolated; no product ordering bug found.
- Rollback: 回退 `setup()` 中的一行 harness isolation 即恢复 baseline；无产品数据或 schema 影响。

## R3 — 最终 CI 等价验证与交付

- 状态: DONE
- Context: R2's focused pass must survive a clean repeated Node 20 run and the exact complete frontend CI command, while the archive record and M16 disposition update remain documentation-only additions.
- Decision: 在 Node `v20.20.2`、clean `npm ci` dependency tree 上连续运行定向 suite 三次，再运行 CI 原样 `npm run test`；随后运行 docs/whitespace/scope checks。只保留 milestone worktree/branch 供 parent clean integration，不合并或写入 `unit/refactor-489`。
- Evidence:
  - Tests: `npm run test -- src/realtime/user-stream/user-stream.test.ts` 连续三次均为 `15 passed`；完整 `npm run test` PASS，`59 test files / 555 tests passed in 19.15s`。
  - Quality: `PYTHON="/Users/czj/Repos/nano-multiagent/.venv/bin/python" ./scripts/docs-check` PASS（186 maintained Markdown sources / 65 required routes）；`git diff --check` PASS。
  - Scope: 相对 `origin/unit/refactor-489` 只含 `user-stream.test.ts`、M16 task ledger、M19 `tasks.md` 与 `progress.md`；没有 production `user-stream-runtime.ts`、adapter、spec、CI config 或 lockfile 改动。
  - Cleanup: `npm ci` 产生的 `src/IM/frontend/node_modules/` 被 ignore；没有启动服务或遗留 listener。milestone worktree/branch 在 push 后保留，等待 parent 在指定 clean worktree 集成。
- Rollback: 回退本 milestone commit 即恢复原 test harness queue behavior和文档状态；无 production data、schema 或运行进程影响。
- Commits: final milestone commit（SHA 以 Git history 为准）。

## Promotion Candidates

None.
