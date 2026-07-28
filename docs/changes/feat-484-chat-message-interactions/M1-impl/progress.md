# feat-484-M1 — Progress

<!-- 每个 roadpoint 完成后实时追加 -->

## R1 — 内容策略与单元测试

- Context: 消息交互改造需要把「正文原生行为」与「产品操作」分开；所有内容规则（链接分类、选区判定、序列化、代码提取）集中到一个无副作用纯策略文件，便于测试和后续 UI 组件复用。
- Decision: 新增 `message-content-policy.ts`，暴露 `classifyChatLink`、`resolveContextMenuModality`、`shouldKeepNativeContextMenu`、`serializeMessageBody`、`extractCodeText`；配套 `message-content-policy.test.ts` 覆盖 design.md 列出的全部策略契约。
- Rationale: 纯函数不读 React state、不写 Clipboard、不导航，UI 组件只负责调用和承担 DOM 副作用；策略层可独立稳定测试。
- Evidence:
  - Tests: `npm run test -- src/features/chat/components/message-content-policy.test.ts` → 37 tests passed.
  - Entry: N/A（纯策略单元）。
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: N/A.
  - Visual/Interaction: N/A.
  - Prototype Comparison: N/A.
- Rollback: `git revert <R1-hash>`.
- Commits: 8c749f04a.
- Next: R2 改造 MessageBubble 事件路由与共享 action model。
