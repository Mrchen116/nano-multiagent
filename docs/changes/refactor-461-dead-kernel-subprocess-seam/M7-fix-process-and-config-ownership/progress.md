# refactor-461-M7 — Progress

## Baseline

- Context: unit integration head `14cd8af19` 上执行 post-acceptance fix round 6。Round 6 reviewer/verifier 正常旅程 verdict 均为 pass；full code review 的 8 个 candidates 均经独立 Phase 2 真实/受控复现确认为 `CONFIRMED`。
- Scope: `src/personal_assistant/{main.py,config/local_store.py}`、`scripts/{e2e-up.sh,e2e-down.sh,e2e-owned-processes.sh}` 与相关 config/public/e2e regression；不发送 P2P，不修改 reviewer/verifier 历史结论。
- Confirmed findings: stale whole-config save lost update；foreground shared-PGID collateral kill；public stop 遗留 detached tool；foreground bypass single-instance claim；freeze failure 遗留 STOP descendant；up 擦除 live internal owner；down missing IM evidence 半拆栈；IM numeric PID reuse误杀。
- Baseline gates: M6 affected `104 passed`；上一轮唯一 full `3598 passed, 1 skipped`。Round 6 verifier full 为 `6 failed, 3592 passed, 1 skipped`：1 个全仓负载 ticker 抖动，5 个 shell/e2e 固定 timeout/lock 持有失败单跑通过；同轮实际留下的 `Ts` descendants 已安全清理并成为 freeze finding 的额外证据。
- Plan: R1 narrow config mutation；R2 public instance/descendant ownership；R3 e2e IM/freeze failure ownership；R4 final gates。

## R1 — Narrow config mutations

- Status: TODO。

## R2 — Public instance and descendant ownership

- Status: TODO。

## R3 — e2e IM and freeze failure ownership

- Status: TODO。

## R4 — Final gates

- Status: TODO。
