# feat-451 — 验收报告

> 对齐: `spec.md` / `design.md` 的验收标准

# Round 1 — 2026-07-01

## Verdict

- Verdict: `fail`
- Highest Required Action: `fix-implementation`
- Reviewer mode: full
- Tested entry: Web IM via Vite dev server `http://127.0.0.1:<ephemeral>/chat/<conversation_id>` against real IM + Gateway processes in the unit worktree.
- Test data: direct user-agent conversation with more than 120 messages, created through the public IM API to satisfy the "history exceeds one page" precondition.

## Runbook Notes

- Services were restarted in the unit worktree before browser testing: IM, Vite dev server, and Gateway for direct-agent/fork coverage.
- The design runbook health check `GET /im/v1/health` returned 404 in this environment, but IM was reachable through OpenAPI and authenticated data APIs. I continued because the product entry and API surface were available.
- Vite loaded modules from `/Users/czj/Repos/nano-multiagent/.worktrees/unit-feat-451/...`, confirming the browser was using this unit worktree.

## User Journeys Exercised

1. Desktop chat history: sign in as `nano`, open a direct agent chat with more than one page of history, verify initial latest page, scroll upward to load older messages, continue to the oldest page, and verify "No earlier messages".
2. Desktop realtime behavior: while viewing older history, create a new agent message through IM's public API and observe whether the open chat updates without refresh.
3. Desktop composer and message actions: verify Shift+Enter newline, Enter send/clear, right-click copy, and hover fork on a real Gateway-generated agent reply.
4. Mobile chat history and composer: open the same direct chat in a mobile viewport, scroll upward to load older messages, verify mobile Enter sends/clears, and verify composer grows to 4 rows then scrolls internally.
5. Mobile long-press actions: long-press an agent message and a real Gateway-generated agent reply in a touch viewport, then release and try to choose Copy/fork.

## Issues

### Issue 1 — Open chat does not receive new messages in realtime

- Severity: `blocking`
- Regression Relation: `direct`
- Recommended Action: `fix-implementation`
- Action Rationale: The unit explicitly requires new messages/agent replies to arrive without disrupting or missing the user's current reading position. In the real Web IM journey, a newly created agent message did not appear in the open chat at all.

Reproduction:

1. Open `http://127.0.0.1:<vite>/chat/<direct-agent-conversation>` and sign in.
2. Scroll away from the bottom into older history.
3. Create a new agent message in the same conversation through the public IM API.
4. Wait 2.5 seconds without refreshing.

Expected:

- The new message arrives in the open chat.
- If the user is reading history, the viewport stays at the current reading position.
- If the user is near the bottom, the viewport follows to the new message.

Actual:

- The open chat did not show the new message at all.
- The same run showed browser WebSocket connection failures for the user event stream.
- Because the message never appeared, both "do not disturb while reading history" and "auto-scroll at bottom" cannot be accepted from the user perspective.

### Issue 2 — Mobile long-press menu disappears on release, so Copy/fork cannot be selected

- Severity: `major`
- Regression Relation: `direct`
- Recommended Action: `fix-implementation`
- Action Rationale: The unit requires mobile long-press to expose Copy, and mobile direct-agent replies to expose fork. The menu appears only while the finger is held and disappears immediately on release, leaving no usable action target.

Reproduction:

1. Open the same direct agent chat in a 390x844 mobile viewport.
2. Long-press an agent message bubble.
3. Keep holding for about 1 second, then release.
4. Repeat on a real Gateway-generated completed agent reply.

Expected:

- After long-press, an operation menu remains visible.
- The menu contains Copy for messages.
- For a completed agent reply in a direct user-agent chat, the menu contains fork and lets the user choose it.

Actual:

- While holding, the menu text included `Copy` and `fork`.
- Immediately after release, both entries disappeared.
- The user cannot select Copy or fork through the normal long-press flow.

## Acceptance Criteria Coverage

### Requirement: 消息历史可通过向上滚动分页加载更早内容 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 会话有多页历史，用户向上滚动触发加载 | `spec.md` | Desktop browser opened a direct chat with more than 120 messages. Initial request loaded only 50 latest messages; scrolling upward loaded older messages. | Initial DOM had 50 message rows; after upward scroll, DOM had 100 rows and included earlier `User historical prompt 023` / `Agent historical reply 072`. | `pass` | Reading region stayed around the same visible messages after prepend. |
| 已经翻到最老的消息 | `spec.md` | Continued scrolling upward until the oldest page loaded, then scrolled to top again. | Top of list showed `No earlier messages`; row count stayed stable after another top scroll. | `pass` | The no-more text is equivalent to the required empty state. |
| 正在加载更早消息 | `spec.md` | Delayed only the real older-history request long enough to observe the UI. | During the delayed request, the page contained a loading/earlier-history status; after response, older messages were prepended. | `pass` | Response still came from real IM API. |

### Requirement: 新消息到达不打扰正在翻看历史的用户 — group result: `fail`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 用户正在看历史时收到新消息 | `spec.md` | Desktop browser stayed in older history; a new agent message was created in the same conversation through public IM API. | API returned 201, but the open chat did not show `Agent live update offbottom 451` after 2.5 seconds. | `fail` | User position was not disturbed, but only because the new message never arrived in the open chat. |
| 用户在底部时收到新消息 | `spec.md` | Could not accept this path because the same open chat did not receive new messages in realtime. | Browser user event stream reported WebSocket failures; externally created messages were not rendered until a later navigation/refresh. | `fail` | Sending one's own message via composer did clear and render locally, but that does not prove incoming new-message behavior. |

### Requirement: 移动端输入法回车发送消息 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 移动端按回车发送 | `spec.md` | Mobile viewport: typed `Mobile enter send 451` in composer and pressed Enter. | Composer value became empty; message appeared in the chat. | `pass` | No newline was inserted. |
| 桌面端保持 Enter 发送 / Shift+Enter 换行 | `spec.md` | Desktop viewport: typed one line, pressed Shift+Enter, typed second line, then pressed Enter. | Textarea value after Shift+Enter was `Desktop line A\nDesktop line B`; after Enter it was empty and the message appeared. | `pass` | Desktop behavior did not regress. |

### Requirement: composer 输入框随内容自动增高 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 输入多行文字时 composer 增高 | `spec.md` | Mobile viewport: filled six lines into the composer. | Textarea reported `rows="4"`, `clientHeight=100`, `scrollHeight=146`, confirming it capped and became internally scrollable. | `pass` | Desktop send/newline behavior also stayed usable. |

### Requirement: 消息气泡支持复制与长按菜单 — group result: `fail`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 长按/右键消息气泡调出菜单 | `spec.md` | Desktop right-click and mobile long-press were both exercised. | Desktop right-click opened a Copy menu. Mobile long-press showed `Copy` only while holding, then the menu disappeared on release. | `fail` | Desktop path passes; mobile path is not usable. |
| 复制消息文本 | `spec.md` | Desktop: right-click agent message and choose Copy. Mobile: long-press an agent message and release. | Desktop clipboard became `Agent historical reply 120 -- acceptance anchor`. Mobile menu disappeared after release, so Copy could not be selected. | `fail` | Required mobile copy flow is not usable. |
| 移动端单聊里长按 agent 回复进行 fork | `spec.md` | Mobile viewport: long-pressed a real Gateway-generated completed agent reply in a direct user-agent chat. | While holding, menu text included `fork`; after release it disappeared and could not be selected. | `fail` | The user receives no usable fork action or feedback. |

### Requirement: 桌面与移动端体验一致 — group result: `fail`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 在手机端向上滚动加载历史 | `spec.md` | Mobile viewport opened the same chat. Initial latest page had 50 rows; upward scroll triggered older page load. | After upward scroll, DOM had 100 message rows and included older history starting around `User historical prompt 027`. | `pass` | Loading state was visible during the older-history request. |
| 在手机端长按 agent 消息 fork | `spec.md` | Mobile viewport long-pressed a real completed agent reply in a direct agent chat. | `fork` appeared while holding, then disappeared on release before it could be tapped. | `fail` | Same underlying symptom as Issue 2. |

## Side Findings

- The design runbook health check path `GET /im/v1/health` did not exist in this run. This did not block product testing because OpenAPI and authenticated IM APIs were available.
- Older-history requests were observed twice for a single threshold crossing in both desktop and mobile runs. I did not classify this as a user-facing issue because the user-visible list state still loaded correctly and showed no duplicate message rows.

## Upper-Level Document Sync

- [x] `SPEC.md` (cross-package top architecture): no update needed; this unit changes IM frontend user behavior only.
- [x] `docs/specs/im/spec.md` (canonical IM behavior contract): needs update before landing; this unit has a delta spec under `docs/changes/feat-451-chat-history-pagination/specs/im/spec.md`, but canonical still says it is aligned to `feat-445`.
- [x] `AGENTS.md` / `CLAUDE.md`: no update needed for product behavior; runbook health path mismatch may be handled separately if desired.
- [x] `docs/SPEC_GUIDE.md`: no update needed; this unit does not change the documentation system.

## Recommended Next Step

Route back to implementation. Re-review is required after fixing realtime message arrival in the open chat and making the mobile long-press menu remain selectable after release.
