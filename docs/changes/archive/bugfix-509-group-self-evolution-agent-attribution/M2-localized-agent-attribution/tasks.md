# M2 localized-agent-attribution

## Roadpoints

- [x] Red/Green: REST/live Message types and reducer preserve the optional notice.
- [x] Red/Green: one narrow formatter maps direct/group × skills/memory/both to complete zh/en i18n sentences and rejects unknown/malformed notices to content fallback.
- [x] Red/Green: MessagePane keeps the existing system row, shows snapshot name only in groups, and adds no message actions/avatar/sender header.
- [x] Run focused frontend tests/build and preserve desktop/mobile real-browser evidence.

## 测试策略

- 保护的回归风险与可观察 seam: live reducer drops the sidecar; UI hardcodes English, repeats the Agent in direct chat, omits it in groups, or renders malformed notices instead of stored content.
- 已有保护与处置: extend `chat-stream-reducer.test.ts`; the 2600+ line `message-pane.test.tsx` remains `keep` and receives no independent behavior. New focused formatter/component files are justified by a distinct stable notice-rendering owner and the existing file-size cap.
- 落层/目录/marker: frontend Vitest, marker: none; real browser is one-time acceptance evidence.
- 文件归属: extend reducer test; add focused `system-notice.test.ts` and `components/system-notice-message.test.tsx`.
- 可选依赖 importorskip: none.
- 本 milestone 产生的一次性验收证据: desktop/mobile screenshots and browser console/network observations under `evidence/`.

### 受影响的既有测试处置

| 风险 / 行为 | 既有测试 | 处置 | 理由与保留或替代保护 | 验证 |
|---|---|---|---|---|
| live sidecar projection | `chat-stream-reducer.test.ts` | rewrite-merge | Add one observable property to the existing canonical event case. | focused Vitest |
| ordinary MessagePane behavior | `components/message-pane.test.tsx` | keep | Existing behavior remains protected; new independent matrix avoids growing the oversized file. | existing suite |
| i18n runtime switching | `i18n/i18n.test.ts` | keep | Shared locale owner already covered; notice formatter/component tests exercise the new keys. | focused Vitest |
