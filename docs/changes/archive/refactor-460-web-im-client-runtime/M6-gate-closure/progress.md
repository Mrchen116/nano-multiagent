# refactor-460-M6 — Progress

## 启动与根因

- 2026-07-13：M5 合入 unit 后，独立 verifier 与 full-diff code review 只读复核；用户明确要求确认问题由 orchestrator 亲自修复，不再委派 impl worker。
- external 首帧缺失的直接根因是 `queryClient.fetchQuery` 继承 conversations query 的 fresh `staleTime`，所谓权威查询实际零 HTTP；查询失败时事件又已被消费，没有恢复队列。
- 其余确定性红测确认：refresh promise 跨账号共享；history stale response 覆盖同 id live completion；failed completion 被硬编码 completed；异步发送失败先清稿；多气泡 roll 清 marker 后未为新正文恢复；非 lifecycle event 重复持久化同一 accumulator。

## R1 — external classification authority / retry

- Status: DONE
- Decision: external 歧义分类使用 `staleTime: 0` 的 authoritative fetch；每个 message key 记录 in-flight/retry，失败不标记已通知，recovery 刷新 conversations 后重试。
- Evidence: fresh-cache 与 authority-failure 两组红测分别由 `b90afaac`、`7fc9ab7b` 建立，修复为 `9b2f67ce`、`86de959e`；toast focused 15 passed。

## R2 — continuity gate closure

- Status: DONE
- Decision: refresh Map 以 user/refresh-token snapshot 为 key；history reset 对 in-flight live ids 优先保留 reducer row；completion 只接受 completed/failed terminal；composer await mutation 成功后清稿并用 ref 同步 singleflight；新 bubble 正文恢复 visibility；accumulator state identity 不变不写 storage。
- Evidence: 红测提交 `4acfc593`，实现提交 `0340d661`。Frontend focused 6 files / 185 tests passed；Gateway observer focused 3 passed；user-stream 17 passed；production build 与相关 ruff passed。

## R3 — full gates / docs / independent closure

- Status: DONE
- Docs: 已校正 shared pre-fanout validation、toast accumulator owner、M4 global event-store max 和 M5/M6 milestone 演进。
- Full gates: frontend clean rerun 64 files / 596 tests passed；首次与 backend 并行时 1 个无关 Agent detail 5s timeout，原入口隔离复跑通过。Production build passed；`pytest -m "not e2e"` 3513 passed / 1 skipped / 23 deselected；`ruff check src tests` passed。
- Round 5 readonly verifier/code review 先确认 3 个 history/external critical 与 1 个 attachment warning；orchestrator 亲自补红测和实现。修复后 frontend full 64 files / 600 tests passed，workspace/toast/composer focused 136 passed，build passed。
- 后续 targeted closure 连续攻击 authority/query/cache 乱序，依次补齐 canonical cache 回写、新旧 query 时序、preview/toast 单调与 cached external fast path 的统一 event clock；最终 toast focused 19/19。第五次 targeted verifier=`pass`、code review=`no findings`，`requires_full_verification=false`。

## Commits

- external fresh-cache red/fix：`b90afaac` / `9b2f67ce`
- external failure recovery red/fix：`7fc9ab7b` / `86de959e`
- gate issues red/fix：`4acfc593` / `0340d661`
- final gate races red/fix：`db214251` / `3a581f3e`
- external cache convergence：`136e238e` / `48c62723`
- authority/query ordering：`976b83ec` / `2e900f4a`
- external monotonic candidates：`98d19a9d` / `001414fb`
- cached external fast path：`b0a06d62` / `5dbf63db`
