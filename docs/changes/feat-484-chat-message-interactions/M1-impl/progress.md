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

## 续跑说明

- 前任 worker 因 context 溢出死亡；本 worker（feat-484-M1-2）在同一 worktree 续跑。
- 已清理杂物：`debug-menu.test.tsx`、`message-pane.tsx.bak`；已移除 `message-content-policy.ts` 中的调试 `console.log`；已校正 `tasks.md` 勾选状态（仅 R1 真实完成）。

## R2 — 气泡事件路由与共享 action model

- Context: 原 `MessageBubble` 同时抢占正文事件并直接复制 `message.content`；需要把正文原生行为与消息级操作分开，且三种表面（toolbar、右键菜单、More sheet）共享同一 action model。
- Decision:
  - 移除旧长按定时器与 touch 接管逻辑；`MessageBubble` 在 capture phase 记录 `pointerdown` 的 modality/坐标/secondary kind。
  - `handleContextMenu` 调用 `resolveContextMenuModality` + `shouldKeepNativeContextMenu`：只有明确 mouse、非原生 target、且 caret point 位于当前选区外时才 `preventDefault()` 并请求 Pane 打开 IM menu；touch/pen/keyboard/unknown 一律交给浏览器。
  - 派生共享 action model：`copy-message`（始终可用）与可选 `fork`（non-candidate 不出现、offline/pending 以 `aria-disabled` 呈现并带同一 reason）。
  - 渲染 desktop toolbar（hover/focus-within 显示）与 compact/coarse More 按钮（CSS 控制可见性）。
- Rationale: 原生内容交互优先；共享 model 保证三表面动作集合与 disabled 原因一致。
- Evidence:
  - Tests: `message-pane.test.tsx` 覆盖 toolbar copy、context menu、mobile long-press 不打开自定义菜单、More action sheet。
  - Entry: N/A。
  - Frontend State Matrix: default/hover/focus/compact/disabled。
  - Browser QA: 待 R7 补齐。
  - E2E/Regression: Vitest 回归。
  - Visual/Interaction: 待 R7 截图。
  - Prototype Comparison: 待 R7。
- Rollback: 本节合并提交可 `git revert`。
- Commits: 见 R2-R6 合并提交。
- Next: R3 Pane copy coordinator。

## R3 — Pane copy coordinator、反馈与 Radix action sheet

- Context: 复制反馈与菜单是 pane 级瞬时 UI；需要避免多个气泡同时残留菜单、旧 Clipboard Promise 关闭新 surface 或污染新会话。
- Decision:
  - `MessagePane` 持有 `conversationGenerationRef`、`surfaceTokenRef`、`attemptTokenRef`、`noticeTokenRef`。
  - `requestCopy` 在写入 Clipboard 前验证 target `isConnected` 与 conversation generation；resolve/reject 通过 `publishCopyResult` 再次验证 latest attempt + generation + optional surface ownership。
  - `showCopyNotice` 用 notice token + generation guard，旧 timer 不能清掉新 notice。
  - mouse context menu 按坐标定位并做 viewport clamp；Radix Dialog action sheet 使用 Portal/Overlay/Content/Title/Description，关闭时回焦仍 connected 的 trigger。
- Rationale: 异步 Clipboard 不可取消，必须显式 handoff 与 token 隔离。
- Evidence:
  - Tests: `message-pane.test.tsx` 覆盖 Clipboard success/failure、error 时保持 menu 打开、action sheet 打开/复制。
  - Entry: N/A。
  - Frontend State Matrix: error/loading 不适用。
  - Browser QA: 待 R7。
  - E2E/Regression: Vitest 回归。
  - Visual/Interaction: 待 R7。
  - Prototype Comparison: 待 R7。
- Rollback: 本节合并提交可 `git revert`。
- Commits: 见 R2-R6 合并提交。
- Next: R4 Markdown 链接与代码块。

## R4 — Markdown 链接分类与代码块复制

- Context: 外部链接需要新标签打开并带可访问提示；代码块需要独立复制入口；inline code 保持纯文本。
- Decision:
  - `MarkdownContent` 的 `components.a` 使用 `classifyChatLink` 分四类：same-origin-document（无 target）、external（target="_blank" rel="noopener noreferrer" + aria-label）、system（mailto，无 target）、unsupported（span）。
  - 具名 external 用 CSS pseudo-element `↗`，不进入 selectable DOM text。
  - `components.pre` 包一层 `im-code-block`，右上角放 copy button；`onCopyCode` 把单个 code element 交给 Pane coordinator。
- Rationale: 链接分类在渲染时稳定决定；pre component 天然拿到单一代码块范围。
- Evidence:
  - Tests: `message-content-policy.test.ts` 覆盖 URL 四分类与 rich-copy fixture；`message-pane.test.tsx` 覆盖 code block copy button 与 inline code 无按钮。
  - Entry: N/A。
  - Frontend State Matrix: N/A。
  - Browser QA: 待 R7。
  - E2E/Regression: Vitest 回归。
  - Visual/Interaction: 待 R7。
  - Prototype Comparison: 待 R7。
- Rollback: 本节合并提交可 `git revert`。
- Commits: 见 R2-R6 合并提交。
- Next: R5 i18n + CSS。

## R5 — i18n 与 CSS

- Context: 新增文案需要中英一致；中文界面不得出现孤立英文 `fork`；交互表面需要样式支持。
- Decision:
  - `en.json` 新增 `copyMessage`、`copyCode`、`copySuccess`、`messageActions`、`branchFromHere`、`branchPending`、`linkOpensInNewTab`。
  - `zh.json` 新增对应中文并把 `fork`/`forkOffline`/`forkError`/`forkToastTitle`/`forkToastSub` 中的英文 `fork` 改为「分支」。
  - `global.css`：移除 `.chat-bubble-card` 的 `-webkit-touch-callout: none` 与 coarse 下的 `user-select: none`；新增 `.chat-message-toolbar`、`.chat-message-more`、`.chat-message-actions`、`.chat-message-action`、`.chat-action-sheet-overlay/content/title`、`.chat-copy-notice`、`.im-md-link-indicator`、`.im-code-block`、`.im-code-copy`。
- Rationale: 正文恢复原生选择；样式按现有 token 微调，不改结构/层级。
- Evidence:
  - Tests: `message-pane.test.tsx` 覆盖英文文案；`i18n.test.ts` 全绿（无键冲突）。
  - Entry: N/A。
  - Frontend State Matrix: 待 R7 检查 computed `user-select`、`-webkit-touch-callout`、focus ring、触控区。
  - Browser QA: 待 R7。
  - E2E/Regression: Vitest 回归。
  - Visual/Interaction: 待 R7。
  - Prototype Comparison: 待 R7。
- Rollback: 本节合并提交可 `git revert`。
- Commits: 见 R2-R6 合并提交。
- Next: R6 门禁与测试补全。

## R6 — 扩展测试与完整门禁

- Context: 需要确保新行为有回归保护、旧 fork 语义不变、全仓测试不红。
- Decision:
  - 修复 `MessageActionList`：引入 `surface` prop（toolbar/context-menu/action-sheet），copy 按钮不再自动关闭 surface，由 coordinator 在 success 时关闭；action sheet 中按钮 role 为 `button`。
  - 恢复被 R2 WIP 误删的 `draftSeed` useEffect（否则 ChatWorkspacePage 的 skill distillation 预填充失效）。
  - 改写 `message-pane.test.tsx` 中 feat-451 旧长按测试为新行为；更新 `message-pane-fork.test.tsx`。
  - 跑 `npm run test`（全 69 文件 690 tests）、`npm run build`、`git diff --check` 全绿。
- Rationale: 共享 action model 的正确关闭行为是跨表面一致的关键；恢复 draftSeed 避免破坏 worktree 外的主线功能。
- Evidence:
  - Tests: `npm run test` → 69 files / 690 tests passed; `npm run build` → success; `git diff --check` → clean.
  - Entry: N/A.
  - Frontend State Matrix: N/A.
  - Browser QA: 待 R7.
  - E2E/Regression: 全仓 Vitest 回归通过.
  - Visual/Interaction: 待 R7.
  - Prototype Comparison: 待 R7.
- Rollback: 本节合并提交可 `git revert`.
- Commits: 见 R2-R6 合并提交.
- Next: R7 真浏览器验收与证据归档.
