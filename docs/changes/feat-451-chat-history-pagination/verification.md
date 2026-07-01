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
