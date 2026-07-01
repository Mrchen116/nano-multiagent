# Verification Report: feat-451

## Summary

| 维度 | 结果 |
|---|---|
| Completeness | 8/8 |
| Correctness | 6/6 |
| Coherence | Followed |

No critical issues. 2 warnings to consider. Ready for PR (with noted improvements).

## Completeness

### Tasks: 8/8 complete

All exit criteria in `M1-impl/tasks.md` are marked `[x]`:

1. ✅ 向上滚动进入上方 1/3 自动加载 50 条更早消息
2. ✅ 阅读位置保持稳定；已无更早消息时不再请求并显示提示
3. ✅ 新消息到达：底部附近自动滚底，看历史时不打扰
4. ✅ 移动端 Enter 发送并清空；桌面端 Enter 发送 / Shift+Enter 换行
5. ✅ composer 随多行内容自动增高，移动端最多 4 行，桌面最多 5 行
6. ✅ 长按/右键菜单含复制；移动端单聊 fork；桌面端 hover fork 保留
7. ✅ `npm run test` 通过（progress.md 记录 63 files / 575 tests）
8. ✅ `npx tsc -b` 通过

### Spec 覆盖：6/6 requirements 有实现

| Spec Requirement | 实现位置 |
|---|---|
| 消息历史向上滚动分页加载 | `chat-workspace-page.tsx:511-526` (loadOlderMessages) + `message-pane.tsx:324-330` (scroll trigger) |
| 新消息到达不打扰看历史 | `message-pane.tsx:352-373` (smart auto-scroll effect) + `nearBottomRef` / `lastMessageIdRef` |
| 移动端输入法回车发送 | `message-pane.tsx:243-247` (handleKeyDown, 无 isMobile 前置条件) |
| composer 输入框自动增高 | `message-pane.tsx:196-201` (composerRows 计算) + `global.css:1457-1464` (max-height) |
| 消息气泡复制与长按菜单 | `message-pane.tsx:608-663` (MessageBubble 内 menu 状态 + 长按/右键处理) |
| 桌面与移动端体验一致 | 实现共用同一组件，isMobile prop 控制差异行为 |

## Correctness

| Requirement / Scenario | 实现位置（file:line） | 测试覆盖 | 状态 |
|---|---|---|---|
| 向上滚动触发加载（上方 1/3） | `message-pane.tsx:324-330` | `message-pane.test.tsx:128` + `chat-workspace.integration.test.tsx:736` | covered |
| 已到最老消息不重复请求 + 无更多提示 | `chat-workspace-page.tsx:512` (hasMoreHistory guard) + `message-pane.tsx:468-474` | `message-pane.test.tsx:258` | covered |
| 加载中 spinner 提示 | `message-pane.tsx:468-474` | `message-pane.test.tsx:258` | covered |
| 看历史时不自动滚底 | `message-pane.tsx:303-336` (nearBottomRef + handleMessagesScroll) | `message-pane.test.tsx:303` | covered |
| 底部附近新消息自动滚底 | `message-pane.tsx:363-371` | `message-pane.test.tsx:337` | covered |
| 移动端 Enter 发送 | `message-pane.tsx:243-247` | `message-pane.test.tsx:372` | covered |
| 桌面端 Shift+Enter 换行 | `message-pane.tsx:243` (`!e.shiftKey` 条件) | `message-pane.test.tsx:391` | covered |
| composer 自动增高（移动端 1→4 行） | `message-pane.tsx:196-201` | `message-pane.test.tsx:431` | covered |
| 桌面端右键菜单复制 | `message-pane.tsx:629-633` + `message-pane.tsx:814` | `message-pane.test.tsx:459` | covered |
| 移动端长按菜单复制 | `message-pane.tsx:635-653` (600ms long press) + `message-pane.tsx:814` | `message-pane.test.tsx:479` | covered |
| 移动端单聊长按 fork | `message-pane.tsx:817-826` | `message-pane.test.tsx:502` | covered |
| 桌面端 hover fork 保留 | `message-pane.tsx:787-806` | `message-pane-fork.test.tsx` (已有) | covered |
| 阅读位置保持（anchor 恢复） | `message-pane.tsx:296-322` | `message-pane.test.tsx:195` | covered |
| 容器未填满自动触发加载 | `message-pane.tsx:385-389` | 实现存在（无独立测试） | covered |
| prepend_history 合并/去重/排序 | `chat-workspace-page.tsx:102-134` | `chat-workspace.integration.test.tsx:736` | covered |
| API cursor/limit 参数 | `chat-api.ts:46-58` | `chat-api.test.ts:77` | covered |

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| 决策 1: 手动 cursor，不用 useInfiniteQuery | 是 | `chat-workspace-page.tsx:254-256` (historyCursor/hasMoreHistory/isLoadingHistory state) |
| 决策 2: 上方 1/3 滚动阈值 | 是 | `message-pane.tsx:329` (`el.scrollTop <= scrollable / 3`) |
| 决策 3: anchor 消息 id 恢复阅读位置 | 是 | `message-pane.tsx:296-322` (captureHistoryAnchor/restoreHistoryAnchor) |
| 决策 4: 最后一条 id 变化 + near-bottom 滚底 | 是 | `message-pane.tsx:183-184` (lastMessageIdRef/nearBottomRef) + `message-pane.tsx:360-372` |
| 决策 5: 移除 !isMobile 限制 | 是 | `message-pane.tsx:243` (无 isMobile 条件) |
| 决策 6: composer auto-grow 4/5 行上限 | 是 | `message-pane.tsx:196-201` + `global.css:1457-1464` |
| 决策 7: MessageContextMenu 移动端长按 + 桌面右键 | 是 | `message-pane.tsx:608-663` (menu 状态) + `message-pane.tsx:787-806` (桌面 hover fork 保留) |

### 代码模式一致性

- 命名：遵循既有 `chat-bubble-*` / `chat-pane-*` / `chat-message-*` class 命名模式。
- 注释：符合 COMMENTING_GUIDE.md，关键决策点有 `feat-451` / `feat-430` 等 issue 锚定注释。
- 组件结构：`MessageBubble` 内联在 `message-pane.tsx`，与现有 `MarkdownContent` / `renderInlineContent` 内联模式一致。
- CSS：新增样式在 `global.css` 尾部追加，与既有 `.chat-bubble-fork` / `.chat-pane-composer-input` 相邻。

### 架构自洽性

- 改动全在 `src/IM/frontend/src/features/chat/v2/` 内，未触碰后端、Gateway 或 agent 内核。
- 未引入新依赖。
- 未破坏跨包 import 边界（AGENTS.md 硬规则）。
- 复用既有 `listMessages` API / `compareMessages` 排序 / `useIsMobile` hook / `streamReducer` 合并模型，未造平行机制。

## Issues

### CRITICAL（提 PR 前必须修）

无。

### WARNING（应该修）

- **W1: `message-pane.test.tsx` 超过 1700 行，远超测试规范 400 行软上限。** 虽然文件描述的是被测组件的多种行为（history pagination / scroll / composer / menu / markdown / mention 等），但按 `docs/TESTING_GUIDE.md` §7 "单测试文件软上限 400 行，超了按行为拆分"，应考虑按 describe 块拆分为多个文件（如 `message-pane-pagination.test.tsx` / `message-pane-menu.test.tsx` / `message-pane-markdown.test.tsx`）。不影响功能正确性，但影响可维护性。
  - 位置：`src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx`
  - 建议：将 `history pagination scroll trigger` / `smart auto-scroll and composer input behavior` / `message action menu` 三个 describe 块拆到独立测试文件。

- **W2: 桌面端 Enter 发送缺少独立测试用例。** Spec scenario "桌面端保持 Enter 发送 / Shift+Enter 换行" 有 Shift+Enter 测试（`message-pane.test.tsx:391`）但无独立的桌面端 Enter 发送测试。当前隐含在移动端测试的对称逻辑中，但 spec 明确要求桌面端 Enter 发送行为，建议补充一个 `isMobile={false}` 的 Enter 发送测试用例。
  - 位置：`src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx`
  - 建议：在 `smart auto-scroll and composer input behavior` describe 块中增加 `"sends on Enter on desktop (no shift) and clears the composer"` 测试。

### SUGGESTION（可以修）

- **S1: `shouldFollowBottom` 条件中 `!lastMessageChanged && nearBottomRef.current` 分支与 `nearBottomRef.current` 条件重叠。** `message-pane.tsx:363-368` 中 `shouldFollowBottom` 已包含 `nearBottomRef.current`，后续 `if (shouldFollowBottom || (!lastMessageChanged && nearBottomRef.current))` 的 `||` 右侧在 `nearBottomRef.current` 为 true 时已被左侧覆盖。虽然不影响正确性，但增加认知负担。
  - 位置：`src/IM/frontend/src/features/chat/v2/components/message-pane.tsx:363-370`
  - 建议：简化为 `if (shouldFollowBottom)` 或添加注释说明右侧分支的意图。

# Round 2

## Verification Report: feat-451

### Summary

| 维度 | 结果 |
|---|---|
| Completeness | 16/16 tasks complete |
| Correctness | 16/17 scenarios covered; 1 critical gap |
| Coherence | Mostly followed; transition-state leak remains |

1 critical issue found. Fix before PR.

### Scope

- Verified HEAD: `3767fad7` (`origin/unit/feat-451`, `merge(feat-451/M2): fix acceptance review findings`).
- Baseline requested by orchestrator: `3767fad7`.
- Reviewed docs: `spec.md`, `design.md`, `M1-impl/tasks.md`, `M2-fix-acceptance-code-review/tasks.md`, prior `verification.md`, `SPEC.md`, `docs/TESTING_GUIDE.md`, `COMMENTING_GUIDE.md`, `docs/specs/im/spec.md`.
- Local test rerun: attempted `npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx && npx tsc -b` in the verify worktree. It failed before test execution because the isolated worktree has no installed frontend deps (`vitest: command not found`). A no-write retry with the main worktree's frontend `.bin` also failed during Vite config loading because `@vitejs/plugin-react` was not resolvable from the verify worktree. Per verifier rules, I did not run `npm ci` or create `node_modules`. Worker progress records `npm run test` and `npx tsc -b` as passed in `M2-fix-acceptance-code-review/progress.md:35-40`.

## Completeness

### Tasks: 16/16 complete

- M1: all 8 exit criteria in `M1-impl/tasks.md` are marked `[x]`.
- M2: all 8 exit criteria in `M2-fix-acceptance-code-review/tasks.md` are marked `[x]`.

### Round 1 issue closure

| Round 1 / M2 focus | Evidence | Status |
|---|---|---|
| Open chat same-conversation new messages appear in real time | Shared user stream dispatches chat WS events at `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx:560-564`; reducer appends `message.created` at `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.ts:97-133`; regression test at `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx:344-368`. | closed for already-seeded active conversation |
| Bottom follows, off-bottom does not disturb | `nearBottomRef` and auto-scroll gate at `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx:332-375`; component coverage in `message-pane.test.tsx` smart auto-scroll block. | closed |
| Mobile long-press menu remains selectable after release | Touch lifecycle keeps menu open and ignores the synthetic same-card mousedown at `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx:641-716`; tests at `message-pane.test.tsx:576-642`. | closed |
| History anchor refs reset on conversation switch | `MessagePane` resets anchor/loading refs on `conversation.id` at `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx:343-350`; test at `message-pane.test.tsx:258-318`. | closed for anchor refs |
| Duplicate older-history same-cursor request guard | Synchronous `historyRequestRef` set before state commit at `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx:512-538`; test at `chat-workspace.integration.test.tsx:817-870`. | closed |
| Unknown history metadata does not show no-more | `hasMoreHistory` is tri-state at `chat-workspace-page.tsx:251-252` and `message-pane.tsx:470-475`; tests at `message-pane.test.tsx:348-362` and `chat-workspace.integration.test.tsx:872-895`. | closed |
| Copy failure is user-observable | Clipboard unavailable/rejected branches set visible error at `message-pane.tsx:673-685` and render it at `message-pane.tsx:862-865`; en/zh strings at `en.json:366`, `zh.json:363`; tests at `message-pane.test.tsx:663-707`. | closed |
| Desktop Enter send independent test | `isMobile={false}` Enter-send test at `message-pane.test.tsx:469-486`. | closed |

## Correctness

### CRITICAL

- **C1: Conversation switch/loading transition can render the previous conversation's messages under the newly selected conversation.** `ChatWorkspacePageV2` resets pagination refs on `conversationId` change (`src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx:504-510`) but does not clear or re-scope `streamState.messages`. The render path then passes `streamState.messages` directly into `MessagePane` for whatever `activeConversation` is currently selected (`src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx:775-779`). If the user switches from conversation A to B while B's `/messages` query is still loading, B's title/participants render with A's message list until B's query resolves and dispatches `reset` (`chat-workspace-page.tsx:482-502`). This is exactly the class of loading-transition cross-session contamination M2 was supposed to eliminate; the current tests only assert that "No earlier messages" is suppressed during unknown metadata, not that old messages disappear.
  - Fix: on `conversationId` change, immediately clear the visible message list for the new conversation before the new history fetch resolves. Two acceptable patterns: dispatch a reset with the new `conversationId` and `messages: []` in the `conversationId` effect, or pass `messages={streamState.conversation_id === conversationId ? streamState.messages : []}` to `MessagePane`. Add a regression test that delays the second conversation's messages response, switches from `c1` to `c2`, and asserts a `c1` message such as `Hi Planner` is not visible under the `Research Squad` heading while `c2` metadata/history is still loading.
  - Related hardening: because shared owner-scoped user events are now dispatched before any active conversation state may be seeded, guard chat-event dispatch by `payload.conversation_id === conversationIdRef.current` at `chat-workspace-page.tsx:560-564`, or make `applyWsEvent` ignore events when `state.conversation_id === null`. This prevents an event for another conversation from entering an unscoped reducer during initial load.

### WARNING

- **W1: `message-pane.test.tsx` still exceeds the 400-line soft limit in `docs/TESTING_GUIDE.md` §7.** This was already noted in round 1. M2 intentionally expanded the existing file per its task strategy, which is reasonable for the fix milestone, but the file remains a maintenance risk.
  - Location: `src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx`
  - Fix: after the blocking transition leak is fixed, split pagination/scroll, composer, and message-menu tests into behavior-named files without changing assertions.

### SUGGESTION

无新增。

## Coherence

- Design decisions 1-7 remain implemented with the intended local IM frontend scope: manual cursor, upper-third trigger, anchor restore, smart bottom-follow, mobile/desktop Enter behavior, composer rows cap, and long-press/right-click message menu.
- M2 correctly removed the prior redundant bottom-follow condition and added copy failure i18n without introducing new cross-package dependencies.
- The remaining C1 issue is not an architecture-boundary violation across packages, but it violates the design's "single active conversation cache slice" expectation by rendering an unscoped message list during conversation transitions.

# Round 3

## Verification Report: feat-451

### Summary

| 维度 | 结果 |
|---|---|
| Completeness | 25/25 tasks complete |
| Correctness | Round 2 critical closed; 6/6 spec requirements implemented |
| Coherence | Followed, with 1 transition-edge warning |

No critical issues. 2 warning(s) to consider. Ready for PR (with noted improvements).

### Scope

- Verified HEAD: `980c1bfd` (`origin/unit/feat-451`, `merge(feat-451/M3): fix verification round 2`).
- Baseline requested by orchestrator: `980c1bfd`.
- Reviewed docs: `spec.md`, `design.md`, `M1-impl/tasks.md`, `M2-fix-acceptance-code-review/tasks.md`, `M3-fix-verification-round2/tasks.md`, all three milestone `progress.md` files, prior `verification.md`, `SPEC.md`, `docs/TESTING_GUIDE.md`, `COMMENTING_GUIDE.md`, `docs/specs/im/spec.md`.
- Local test rerun: attempted `npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` in the verify worktree. It failed before test execution because the isolated worktree has no installed frontend deps (`vitest: command not found`). A no-write retry using the main worktree `.bin` also failed during Vite config loading because `@vitejs/plugin-react` was not resolvable from the verify worktree. Per verifier rules, I did not run `npm ci` or create `node_modules`. Worker progress records the narrow test, full `npm run test`, and `npx tsc -b` as passed in `M3-fix-verification-round2/progress.md`.

## Completeness

### Tasks: 25/25 complete

- M1: all 8 exit criteria in `M1-impl/tasks.md` are marked `[x]`.
- M2: all 9 exit criteria in `M2-fix-acceptance-code-review/tasks.md` are marked `[x]`.
- M3: all 8 exit criteria in `M3-fix-verification-round2/tasks.md` are marked `[x]`.

### Round 2 critical closure

| Round 2 / M3 focus | Evidence | Status |
|---|---|---|
| Switching conversations must not show old messages while the new history response is pending | `visibleMessages` only passes reducer messages when `streamState.conversation_id === conversationId` at `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx:479-481`; `MessagePane` receives that scoped list at `chat-workspace-page.tsx:781-783`. Regression test delays c2 history and asserts c1 text is absent under the c2 heading at `src/IM/frontend/src/features/chat/v2/chat-workspace.integration.test.tsx:897-920`. | closed |
| Shared owner-scoped user stream events for other conversations must not pollute the active pane or seed an unbound reducer | User stream dispatch is guarded by `chatEvent.conversation_id === conversationIdRef.current` at `chat-workspace-page.tsx:564-568`; out-of-conversation events still refresh the sidebar via the conversations invalidation branch at `chat-workspace-page.tsx:609-626`. Regression test emits c2 while c1 history is delayed and asserts c2 content never appears in c1 at `chat-workspace.integration.test.tsx:923-960`. | closed |
| Send failure/no append must not leave stale force-scroll state; successful local user append still follows bottom | `commit()` clears the flag on synchronous send exceptions at `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx:220-225`; `sendError` clears it at `message-pane.tsx:361-363`; the auto-scroll gate only honors the flag when the last message changed and is self-authored at `message-pane.tsx:376-387`, then clears it at `message-pane.tsx:393`. Tests cover no-append no scroll at `message-pane.test.tsx:576-618` and local user append scroll at `message-pane.test.tsx:620-660`. | closed |
| `restoreHistoryAnchor()` must recompute near-bottom so later live arrivals do not incorrectly pull to bottom | `restoreHistoryAnchor()` calls `updateNearBottom()` immediately after setting `scrollTop` at `message-pane.tsx:318-329`. Regression test verifies a live message after anchor restore keeps `scrollTop` at the restored historical position at `message-pane.test.tsx:258-343`. | closed |

### Spec coverage: 6/6 requirements implemented

| Spec Requirement | Implementation evidence | Test / progress evidence |
|---|---|---|
| 消息历史可通过向上滚动分页加载更早内容 | Manual cursor/loading state and `listMessages(... beforeMessageId ...)` at `chat-workspace-page.tsx:516-543`; upper-third trigger at `message-pane.tsx:333-339`; history status UI at `message-pane.tsx:489-496`. | M1 progress final evidence; integration/component tests retained. |
| 新消息到达不打扰正在翻看历史的用户 | `nearBottomRef` updates on scroll at `message-pane.tsx:341-349`; auto-scroll gate follows only initial hydration, local self append, or near-bottom at `message-pane.tsx:365-393`; M3 fixes stale state after anchor restore and failed/no-op send. | M1/M2/M3 progress plus `message-pane.test.tsx:258-343` and `message-pane.test.tsx:576-660`. |
| 移动端输入法回车发送消息 | `commit()` is called for Enter without an `isMobile` exclusion; slash picker still owns its Enter path. | M1/M2 progress; desktop independent regression retained. |
| composer 输入框随内容自动增高 | 1/4 mobile rows and 2/5 desktop rows are derived from draft line count at `message-pane.tsx:199-204`; CSS max/overflow remains in `global.css`. | M1 progress final evidence. |
| 消息气泡支持复制与长按菜单 | Bubble contextmenu/touch handlers and menu render are at `message-pane.tsx:790-875`; copy failure remains observable from M2. | M1/M2 progress; menu regression tests retained. |
| 桌面与移动端体验一致 | Same `MessagePane` component drives desktop/mobile; mobile fork menu and desktop hover fork are both present, with `isMobile` controlling only the affordance. | M1/M2 browser evidence and tests retained. |

## Correctness

### CRITICAL

无。

### WARNING

- **W1: Same-conversation live events can be dropped during the conversation-switch loading window.** M3 correctly prevents old or out-of-conversation messages from rendering, but it does so by passing `visibleMessages=[]` until REST history resets the reducer (`chat-workspace-page.tsx:479-481`) and by dispatching active-conversation stream events into the existing reducer state (`chat-workspace-page.tsx:564-568`). If the user switches from c1 to c2 and a c2 `message.created` event arrives before c2 history resolves, `conversationIdRef.current` allows the dispatch, but `applyWsEvent` still sees `state.conversation_id === "c1"` and drops the event at `src/IM/frontend/src/features/chat/v2/chat-stream-reducer.ts:90-94`. This does not reopen the Round 2 critical leak, but it can delay or miss an active c2 live message until a later refetch if the in-flight history response does not include it.
  - Fix: bind the reducer to the newly selected conversation immediately on `conversationId` change by dispatching `reset` with `{conversationId, messages: []}` before the history request returns, or change the stream-event path to seed/reset the reducer when `chatEvent.conversation_id === conversationIdRef.current` but `streamState.conversation_id !== conversationIdRef.current`. Add a regression test that switches to c2, delays c2 history, emits a c2 `message.created`, and asserts the c2 message appears without reintroducing c1 leakage.

- **W2: `message-pane.test.tsx` still exceeds the 400-line soft limit in `docs/TESTING_GUIDE.md` §7.** The file is now over 2,000 lines and M3 added more behavior coverage there. This is understandable for a targeted fix milestone that extends existing coverage, but it remains a maintenance warning rather than a product correctness blocker.
  - Location: `src/IM/frontend/src/features/chat/v2/components/message-pane.test.tsx`
  - Fix: after this unit lands, split pagination/scroll, composer/send, message-menu, markdown/rendering, and mention/slash picker coverage into behavior-named test files, preserving the existing assertions.

### SUGGESTION

无。

## Coherence

| design 决策 | Round 3 status | Evidence |
|---|---|---|
| 决策 1: 手动 cursor，不用 `useInfiniteQuery` | followed | `chat-workspace-page.tsx:516-543` keeps manual cursor/loading state. |
| 决策 2: 上方 1/3 滚动阈值 | followed | `message-pane.tsx:333-339`. |
| 决策 3: anchor 消息 id 恢复阅读位置 | followed | `message-pane.tsx:304-330`; M3 adds near-bottom recomputation. |
| 决策 4: 最后一条 id 变化 + near-bottom 滚底 | followed | `message-pane.tsx:365-393`; M3 narrows force-scroll to self-authored local append. |
| 决策 5: 移动端 Enter 发送、桌面 Shift+Enter 换行 | followed | Existing commit path has no mobile exclusion; retained tests cover mobile and desktop behavior. |
| 决策 6: composer auto-grow 4/5 行上限 | followed | `message-pane.tsx:199-204`. |
| 决策 7: 长按/右键菜单，移动端 fork 放进菜单 | followed | `message-pane.tsx:790-875`; desktop hover fork remains at `message-pane.tsx:838-858`. |

### Architecture self-consistency

- All M3 code changes stayed inside `src/IM/frontend/src/features/chat/v2/`; no backend, Gateway, CLI, or agent kernel code was modified.
- No cross-package import boundary from `SPEC.md` / AGENTS.md was violated.
- The implementation reuses existing IM frontend mechanisms: `attachUserConversationStream`, `streamReducer` / `applyWsEvent`, `listMessages`, and `MessagePane` scroll state. It does not introduce a parallel stream, API, or state model.

No critical issue(s) found. Ready for PR with the warnings above tracked.
