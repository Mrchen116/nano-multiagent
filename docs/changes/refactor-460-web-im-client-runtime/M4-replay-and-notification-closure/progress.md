# refactor-460-M4 — Progress

## 启动记录

- 2026-07-13：完整读取 motivation/design、Round 2 acceptance/verification、AGENTS/SPEC/注释与测试规范、LOGBOOK、worker/systematic-debugging skill；M4 目录起始仅有 `.gitkeep`。
- worktree：`milestone/refactor-460-M4` 基于同步的 `origin/unit/refactor-460` / `2158cc87`；`npm ci` 只生成 ignored dependencies。
- 基线：frontend 62 files / 581 tests passed，production build passed；`ruff check src tests` passed；`pytest -m "not e2e"` 3505 passed / 1 skipped / 23 deselected。
- systematic-debugging 初步根因：server 在 replay 前加入 live registry；resume 单批 LIMIT 500；cursor-ahead 未进入 resync；EventBridge 与 repositories 都暴露 notify；runtime 每帧读写 storage 且 <=cursor 仍 dispatch；Chat mapper 只按 event type cast；toast/notifier accumulator 分叉且 completion 身份非自包含；canonical/relay key 无共同 identity；natural silence 只有 exact token 才置 discard。
- 范围澄清：orchestrator 授权最小 Gateway `runtime_delivery/{observer.py,context.py}` 范围扩展；IM 不按空正文猜测静默，协议语义仍由 run lifecycle + visibility policy owner 决定；worker 不改 design.md。

## R1 — direct Web 静默终态归属

- Status: TODO
- Context: pending C1 deterministic reproduction.
- Decision: pending.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: 先在任何实现改动前完成 Round 2 双浏览器与 natural silence 基线取证。

## R2 — IM replay/live 无缝交接与唯一发布

- Status: TODO
- Context: pending R1.
- Decision: pending.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: pending.

## R3 — 浏览器 cursor 与 domain recovery 连续性

- Status: TODO
- Context: pending R2.
- Decision: pending.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: pending.

## R4 — 共享通知生命周期与全量真栈收口

- Status: TODO
- Context: pending R3.
- Decision: pending.
- Rationale: pending.
- Evidence: pending.
- Rollback: pending.
- Commits: pending.
- Next: pending.
