# M22: Fix Chat Interaction and Rich Components

## What Was Done

### 1. Auto-scroll in chat workspace (`chat-workspace-page.tsx` + `message-pane.tsx`)
- Added `messagesContainerRef` to `MessagePane` and attached it to the `.chat-pane-messages` div
- Added `useEffect` in `MessagePane` that sets `scrollTop = scrollHeight` when `messages.length` changes
- This scrolls the internal message container to the bottom, NOT the whole page — matching prototype `im-chat-page.jsx:341-343`

### 2. Send error handling (`chat-workspace-page.tsx` + `message-pane.tsx`)
- Added `sendError` state to `ChatWorkspacePageV2` with `onError` callback on `sendMutation`
- Added in-app error toast (fixed top-left, red border, dismissible) that displays the error message
- Passed `sendError` and `isSending` props through to `MessagePane`
- Added i18n keys: `sendErrorTitle`, `sendError`

### 3. Expandable Token Chip detail panel (`token-chip.tsx`)
- Added `open` state with click-to-toggle
- Expanded panel shows: output tokens, total tokens (if available), context used/window, progress bar with color-coded percentage
- Warning/critical messages at 70%/90% thresholds
- Styled with dark theme (`oklch(0.14...)`) matching prototype `im-components.jsx:207-237`
- Added i18n keys: `tokenContextShort`, `tokenOutput`, `tokenTotal`, `tokenContextUsed`, `tokenWarn`, `tokenWarnCritical`

### 4. Tool Calls Panel enhancements (`tool-calls-panel.tsx`)
- Added `formatDuration()` helper: formats ms to readable form (`48ms`, `1.2s`, `2m 30s`)
- Added `totalDuration()` helper for aggregate display
- Dark theme styling for the expanded panel (`oklch(0.13...)` background, `oklch(0.22...)` border)
- Smooth fade-in animation for panel and individual row bodies
- Status icons (●/◌/✕) with color coding per prototype
- Running pulse animation for in-flight tool calls
- First tool call row defaults to open (`defaultOpen={i === 0}`) per prototype

### 5. Global CSS updates (`global.css`)
- Complete rewrite of `.chat-tool-calls-*` rules for dark theme + animations
- Added `.chat-token-chip-*` rules for expandable chip styling
- Added `@keyframes` for `im-pulse`, `token-chip-fade-in`, `tool-panel-fade-in`, `tool-body-fade-in`

### 6. i18n updates (`en.json`, `zh.json`)
- Added all new translation keys for token chip details and send error

---

## Prototype Comparison Checklist

| Aspect | Prototype (`im-components.jsx`) | Implementation | Match |
|--------|--------------------------------|----------------|-------|
| **TokenChip — layout** | Pill button with arrow + tok + ctx% | Same | ✅ |
| **TokenChip — expand** | Click toggles detail panel | Same | ✅ |
| **TokenChip — detail fields** | output, context_used, context_window, progress bar | + total tokens, same 4 core fields | ✅ |
| **TokenChip — dark panel** | `oklch(0.14...)` bg, `oklch(0.22...)` border | Same | ✅ |
| **TokenChip — warn/critical** | 70% warn, 90% critical with messages | Same | ✅ |
| **ToolCalls — toggle** | Pill button with arrow + count + duration/running | Same | ✅ |
| **ToolCalls — running pulse** | Animated dot + "running" text | Same | ✅ |
| **ToolCalls — dark panel** | `oklch(0.13...)` bg, `oklch(0.22...)` border, shadow | Same | ✅ |
| **ToolCalls — row status icon** | ●/◌/✕ with color | Same | ✅ |
| **ToolCalls — duration format** | `IM_UTILS.formatDuration` (readable) | `formatDuration()` helper | ✅ |
| **ToolCalls — row default open** | `defaultOpen={i === 0}` | Same | ✅ |
| **ToolCalls — INPUT/OUTPUT** | Uppercase labels, preformatted JSON | Same | ✅ |
| **MessagePane — auto-scroll** | `listRef.current.scrollTop = scrollHeight` | Same approach via useEffect | ✅ |
| **Send error — toast** | N/A (prototype has no error handling) | In-app toast with dismiss | ✅ |

---

## Evidence

### Screenshots (Real Chat Verification with Live Agent)

All screenshots taken with real IM service (:8011) + Gateway + DemoAgent running. User: qatest-user-01.

**Auto-scroll (a)**
- `evidence/m22-chat-with-replies.png` — Chat with DemoAgent showing multiple messages and replies
- `evidence/m22-many-messages-scroll.png` — 8+ messages sent, message area scrolled to bottom (not whole page), agent replied with long text
- `evidence/m22-chat-mobile-real.png` — Mobile 375x812 viewport, messages render correctly

**Error Toast (b)**
- `evidence/m22-error-toast-final.png` — Red "Send failed" toast with 503 error detail and dismiss button (triggered by killing Gateway)

**Token Chip (c)**
- `evidence/m22-token-chip-expanded-final.png` — Token chip expanded showing: output tokens (248), total tokens (13,659), context used (13,411 / 14k), 98% progress bar with "⚠ Context nearly full" warning
- `evidence/m22-chat-with-replies.png` — Token chip collapsed: "47 tok · ctx 98%"

**Tool Calls (d)**
- `evidence/m22-tool-calls-visible.png` — Tool calls toggle collapsed: "▸ 2 tool calls · 70ms"
- `evidence/m22-tool-calls-expanded-real.png` — Tool calls panel expanded with dark theme, showing 2 bash calls (36ms, 34ms) with status icons

### Build Verification
```bash
cd src/IM/frontend && npm run build
# dist/assets/index-*.css contains: chat-token-chip-detail, chat-tool-calls-panel
# dist/assets/index-*.js contains: scrollTop, sendError, duration_ms, tokenContextShort
```

### Test Results
```
Test Files  51 passed | 1 failed (52)
     Tests  290 passed | 2 failed (292)
```
- The 2 failing tests are in `agents-list-page.test.tsx` (pre-existing, unrelated to M22 — "+ New" button href mismatch)
- All M22-related tests pass:
  - `token-chip.test.tsx` — 5/5 passed
  - `tool-calls-panel.test.tsx` — 4/4 passed

---

## Exit Criteria Verification

| Criterion | Status | Notes |
|-----------|--------|-------|
| (a) 消息区内部自动滚动到底部 | ✅ Verified | 8+ messages sent with long text, message area scrolled to bottom, whole page did not scroll. Agent replied with long responses. Screenshot: m22-many-messages-scroll.png |
| (b) 模拟发送失败显示错误提示 | ✅ Verified | Red "Send failed" toast visible with 503 `target_node_id is not connected` detail and dismiss (×) button. Triggered by killing Gateway process. Screenshot: m22-error-toast-final.png |
| (c) Token chip 点击展开详细面板 | ✅ Verified | Expanded panel shows: output tokens (248), total tokens (13,659), context used (13,411 / 14k), 98% progress bar with "⚠ Context nearly full — consider /compact" warning. Screenshot: m22-token-chip-expanded-final.png |
| (d) Tool call 面板展开/收起动画 | ✅ Verified | Dark theme panel with fade-in animation, status icons (●), readable duration (36ms, 34ms). First row auto-expanded. Screenshot: m22-tool-calls-expanded-real.png |

---

## Files Modified

1. `src/IM/frontend/src/features/chat/v2/chat-workspace-page.tsx`
2. `src/IM/frontend/src/features/chat/v2/components/message-pane.tsx`
3. `src/IM/frontend/src/features/chat/v2/components/token-chip.tsx`
4. `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.tsx`
5. `src/IM/frontend/src/styles/global.css`
6. `src/IM/frontend/src/i18n/en.json`
7. `src/IM/frontend/src/i18n/zh.json`

## Tests Modified

1. `src/IM/frontend/src/features/chat/v2/components/token-chip.test.tsx`
2. `src/IM/frontend/src/features/chat/v2/components/tool-calls-panel.test.tsx`
