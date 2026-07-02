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

---

# Round 2 — 2026-07-01

## Verdict

- Verdict: `pass`
- Highest Required Action: `pass`
- Reviewer mode: full
- Tested entry: Web IM via Vite dev server `http://127.0.0.1:54763/chat/ac040109c6634aa19da406d7e4955202` against real IM + Gateway processes in the unit worktree.
- Test data: direct user-agent conversation with 130 seeded historical agent messages plus real Gateway-generated completed agent replies.

## Runbook Notes

- Services were restarted in the unit worktree on isolated ports: IM `127.0.0.1:54762`, Vite `127.0.0.1:54763`, Gateway node `wt-unit-feat-451-r2`.
- Vite was started in real IM mode with `VITE_CHAT_API_MODE=im` and `VITE_IM_API_BASE_URL=http://127.0.0.1:54762`.
- Gateway was auto-bound and visible through the authenticated node list as `online` with `relay_enabled=true`.
- The browser loaded Vite's `/src/main.tsx` module from this worktree, confirming the current unit frontend was under test.

## User Journeys Exercised

1. Desktop history pagination: open a direct-agent chat with more than 130 messages, verify first page, scroll upward to load older messages, continue to no-more state, and observe reading position stability.
2. Realtime message behavior: while viewing history, create a same-conversation agent message through IM's public API and verify it appears without moving the viewport; while at bottom, create another same-conversation message and verify bottom follow; then send through the real composer and wait for a completed Gateway direct-agent reply.
3. Desktop composer and actions: verify Shift+Enter newline, Enter send/clear, right-click Copy, and hover fork visibility.
4. Mobile pagination and composer: open the same chat at `390x844`, scroll upward to load older history, press Enter to send, and verify auto-grow caps at 4 rows with internal scroll.
5. Mobile long-press actions: with Chromium real touch input, long-press visible message bubbles, release, choose Copy, then long-press a completed direct-agent reply and choose fork.

## Round 1 Failures Rechecked

- Round 1 Issue 1, realtime open-chat updates: closed. Same-conversation messages appeared in the already-open chat. Off-bottom viewport stayed at `scrollTop=5180` with `scrollDelta=0`; bottom viewport stayed at `bottomDistance=0`. A real composer send produced a completed Gateway reply in the open chat (`forkable` replies `5 -> 6`, rows `51 -> 53`) and remained at bottom.
- Round 1 Issue 2, mobile long-press menu disappears on release: closed. On a `390x844` mobile viewport using CDP touch input, Copy remained visible after `touchEnd`, clipboard became `Agent historical reply 130 -- feat451 round2 anchor`, selection text stayed empty, and a completed direct-agent reply showed Copy + fork after release; choosing fork navigated to `/chat/a793ab92b63f4ae8a2d933dcbcc78dd9`.

## Issues

No in-unit acceptance issues found in Round 2.

## Acceptance Criteria Coverage

### Requirement: 消息历史可通过向上滚动分页加载更早内容 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 会话有多页历史，用户向上滚动触发加载 | `spec.md` | Desktop chat opened with latest page, then scrolled upward. | Initial render had 51 rows; first upward load increased to 101 rows and showed older `Agent historical reply 033+`. | `pass` | Reading stayed anchored near the same real message rather than jumping to bottom. |
| 已经翻到最老的消息 | `spec.md` | Continued upward loading until first history page. | Row count reached 133 and top displayed `No earlier messages`; further top scroll did not add rows. | `pass` | No-more state was visible. |
| 正在加载更早消息 | `spec.md` | Delayed older-history request in browser while still continuing to real IM. | Body contained `Loading earlier messages…` during pending request. | `pass` | Verified in desktop and mobile. |

### Requirement: 新消息到达不打扰正在翻看历史的用户 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 用户正在看历史时收到新消息 | `spec.md` | Desktop viewport stayed in older history; same-conversation agent message was created through public IM API. | Message `Agent live offbottom r2 ...` appeared; `scrollTop` stayed `5180`, `scrollDelta=0`. | `pass` | This directly closes Round 1's missing realtime update for off-bottom reading. |
| 用户在底部时收到新消息 | `spec.md` | Desktop viewport at bottom; same-conversation message arrived, then a real composer send triggered Gateway reply. | API message appeared with `bottomDistance=0`; real Gateway reply appeared in the open chat with `forkable 5 -> 6`, rows `51 -> 53`, `bottomDistance=0`. | `pass` | Covers direct-agent reply path and bottom follow. |

### Requirement: 移动端输入法回车发送消息 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 移动端按回车发送 | `spec.md` | Mobile viewport typed `Mobile enter r2` and pressed Enter. | Textarea value became empty and message appeared in chat. | `pass` | No newline inserted. |
| 桌面端保持 Enter 发送 / Shift+Enter 换行 | `spec.md` | Desktop typed `Desktop line A`, pressed Shift+Enter, typed second line, then Enter. | Textarea contained `Desktop line A\nDesktop line B`; after Enter it cleared and message appeared. | `pass` | No regression. |

### Requirement: composer 输入框随内容自动增高 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 输入多行文字时 composer 增高 | `spec.md` | Mobile viewport filled six lines. | Textarea reported `rows="4"`, `clientHeight=100`, `scrollHeight=146`. | `pass` | Capped and internally scrollable. |

### Requirement: 消息气泡支持复制与长按菜单 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 长按/右键消息气泡调出菜单 | `spec.md` | Desktop right-click and mobile long-press were exercised. | Desktop menu showed Copy; mobile CDP touch long-press showed Copy while holding and after release. | `pass` | Browser native selection did not appear on mobile (`window.getSelection()` empty). |
| 复制消息文本 | `spec.md` | Desktop right-click Copy; mobile long-press release then Copy. | Desktop clipboard: `Agent historical reply 130 -- feat451 round2 anchor`; mobile clipboard same. | `pass` | Copy closes menu after success. |
| 移动端单聊里长按 agent 回复进行 fork | `spec.md` | Mobile long-pressed a visible completed direct-agent reply, released, then selected fork. | Menu retained Copy + fork after release; URL changed from original chat to `/chat/a793ab92b63f4ae8a2d933dcbcc78dd9`. | `pass` | Clear user-visible fork feedback through navigation. |

### Requirement: 桌面与移动端体验一致 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 在手机端向上滚动加载历史 | `spec.md` | Mobile `390x844` opened same chat and scrolled upward. | Initial mobile render had 51 rows; upward load increased to 101 rows and showed `Loading earlier messages…`. | `pass` | Reading position stayed near the loaded anchor, not bottom. |
| 在手机端长按 agent 消息 fork | `spec.md` | Mobile long-pressed completed direct-agent reply with real touch input. | Copy + fork stayed visible after release; choosing fork navigated to a new chat. | `pass` | Closes Round 1 mobile fork failure. |

## Side Findings

- Browser console still logged transient WebSocket connection warnings against both the Vite origin and IM origin during initial auth/stream setup. User-visible realtime behavior passed in this run, so I did not classify this as an acceptance issue.

## Upper-Level Document Sync

- [x] `SPEC.md` (cross-package top architecture): no update needed; this unit changes IM frontend user behavior only.
- [x] `docs/specs/im/spec.md` (canonical IM behavior contract): needs final orchestrator sync before landing; the unit delta exists under `docs/changes/feat-451-chat-history-pagination/specs/im/spec.md`, while canonical visible hits still mainly cover pre-existing fork behavior.
- [x] `AGENTS.md` / `CLAUDE.md`: no update needed.
- [x] `docs/SPEC_GUIDE.md`: no update needed.

## Recommended Next Step

Proceed toward landing after the normal orchestrator document-sync gate. No Round 3 product re-review is required for feat-451 acceptance.

---

# Round 3 — 2026-07-02

## Verdict

- Verdict: `fail`
- Highest Required Action: `fix-implementation`
- Reviewer mode: full, focused Round 3 recheck after M3.
- Prior result inherited: Round 2 was `pass`; this round focused on M3-visible paths around conversation switching and scroll/realtime correctness.
- Tested entry: Web IM via Vite dev server `http://127.0.0.1:54550/chat/...` against isolated IM `127.0.0.1:54549` in the unit worktree.
- Test data: independent user `feat451r3d_1782925907`; Conversation A with 75 seeded historical messages, Conversation B with 17 messages, and a fresh delayed Conversation C with 5 messages. A second user was added to Conversation A for external live-message arrival.

## Runbook Notes

- Services were restarted for this round on isolated ports: IM `127.0.0.1:54549`, Vite `127.0.0.1:54550`.
- Vite was started in real IM mode with `VITE_CHAT_API_MODE=im` and `VITE_IM_API_BASE_URL=http://127.0.0.1:54549`.
- Browser loaded the Vite dev entry `/src/main.tsx` from this worktree.
- Playwright used the local system Chrome executable because Playwright's bundled Chromium cache was not installed in this environment.

## User Journeys Exercised

1. Conversation switch isolation: opened Conversation A, switched to B, then created a fresh C conversation and delayed C's history response in the browser to verify that C's pane did not show A messages while C history was pending.
2. Realtime and scroll policy: while reading older content in Conversation A, created a same-conversation message through the public IM API, then repeated with a second user participant to simulate another user/external sender.
3. Basic regression spot checks: scrolled A upward to load earlier history and reach `No earlier messages`; right-clicked a desktop bubble for Copy; opened mobile viewport and long-pressed a bubble to confirm Copy remained visible after release.

## Issues

### Issue 1 — Open chat pane does not render same-conversation live messages

- Severity: `blocking`
- Regression Relation: `direct`
- Recommended Action: `fix-implementation`
- Action Rationale: The unit and M3 both require same-conversation live arrivals to update the already-open chat while preserving scroll position. In Round 3, the conversation list preview updated, but the active message pane did not render the new message, so neither "do not jump while reading history" nor "follow bottom when already at bottom" can be accepted from the user perspective.

Reproduction:

1. Open `http://127.0.0.1:54550/chat/a829fba9a89b46deb47ae992c0be1b1c`.
2. Scroll the message list away from the bottom into older loaded history.
3. Create `R3 external retry live` in the same conversation through `POST /im/v1/conversations/{id}/messages`.
4. Wait 3 seconds.
5. Add a second user participant and create `R3 other-user live` from that second user in the same conversation.
6. Wait another 3.5 seconds.

Expected:

- The new same-conversation message appears in the open message pane.
- If the user is reading history, the pane stays at the current reading position.
- If the user is at the bottom, the pane follows to the new bottom.

Actual:

- The sidebar preview updated to `R3 external retry live` / `R3 other-user live`.
- The active message pane stayed on historical messages (`R3 A history ...`) and did not contain either live message.
- The browser console repeatedly logged user-stream WebSocket handshake failures against both the Vite origin and IM origin.
- Because the message never appeared in the pane, the scroll policy itself cannot be accepted for live arrivals.

## Round 3 Focus Coverage

### Requirement: 新消息到达不打扰正在翻看历史的用户 — group result: `fail`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 用户正在看历史时收到新消息 | `spec.md`; M3 tasks around scroll state correctness | Desktop browser stayed off-bottom in Conversation A; same-conversation messages were created via the public IM API, first as the current user and then as a second user participant. | Sidebar preview updated, but `.chat-pane-messages` did not include `R3 external retry live` or `R3 other-user live` after waiting. Console showed user-stream WebSocket handshake failures. | `fail` | The viewport was not disturbed, but only because the live message never rendered in the active pane. |
| 用户在底部时收到新消息 | `spec.md`; M3 tasks around scroll state correctness | Not accepted after the off-bottom same-conversation live path failed. | The prerequisite user-visible live append did not work in the open pane. | `fail` | Bottom-follow cannot be accepted when the live message does not arrive in the pane. |

### M3 Focus: 会话切换期间不显示旧会话消息 — result: `pass`

| Path | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 从会话 A 切到新会话 C，C 历史未返回前不显示 A 旧消息 | M3 milestone exit criteria | Opened A, then navigated to fresh C while delaying C messages response by 2.5s. | C pane showed `R3 Conversation C Pending` with `No messages yet`; message area had no `R3 A history`. After response, it showed `R3 C history 001` through `005`. | `pass` | This directly covers the M3 conversation-switch leak from a user-visible angle. |
| 从 A 切到 B 后继续使用 | User prompt focus | Switched from A to B and waited for B history. | B pane contained `R3 B history 001` through `017` and no A messages. | `pass` | B had loaded too quickly to observe pending state, so the delayed C check above covers pending. |

### M3 Focus: 发送失败 / 无新增消息后的 stale force-scroll — result: `inconclusive`

| Path | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 发送失败/无新增消息后，下一条外部消息不因 stale force-scroll 拉到底 | User prompt focus; M3 milestone exit criteria | Intended browser journey: fail a send/no-op append, stay off-bottom, then inject external same-conversation message. | Could not produce valid user-visible evidence because external same-conversation messages did not render in the active pane at all. | `inconclusive` | This remains blocked by Issue 1; once live append works, this path needs re-review. |

### Round 2 Regression Spot Checks — result: `pass-with-limits`

| Path | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 历史分页没有明显回归 | Round 2 pass inheritance + user prompt | In Conversation A, initial pane had 50 bubbles. Scrolling to the top loaded older history. | Bubble count increased to 78; pane showed `R3 A history 001` and `No earlier messages`; it did not jump to bottom. | `pass` | Basic pagination still works. |
| 移动长按 Copy 菜单没有明显回归 | Round 2 pass inheritance + user prompt | Mobile `390x844` viewport long-pressed a bubble, held, then released. | Copy was visible while holding and remained visible after release. | `pass` | Clipboard read returned `CLIPBOARD_ERR` in headless Chrome permission context, so this round only confirms menu persistence. |
| 移动 fork 入口 | Round 2 pass inheritance + user prompt | Not expanded after Issue 1 blocked the M3 live-message path. | Round 2 had passed real mobile fork. Round 3 did not create a fresh direct-agent/Gateway fork journey. | `not-applicable` | No new fork-specific regression was observed, but this path was not fully re-run in Round 3. |

## Side Findings

- The active page's conversation list reflected externally created messages even when the message pane did not, which made the failure visible as an inconsistent UI state: sidebar says a new message arrived, but the open thread does not show it.
- Headless Chrome did not allow reading clipboard contents after Copy in this run; I treated this as an environment permission limit, not a product issue, because the menu behavior was the focus of the Round 3 spot check.

## Upper-Level Document Sync

- [x] `SPEC.md` (cross-package top architecture): no update needed; this unit changes IM frontend user behavior only.
- [x] `docs/specs/im/spec.md` (canonical IM behavior contract): still needs final orchestrator sync before landing; Round 3 does not change the expected contract.
- [x] `AGENTS.md` / `CLAUDE.md`: no update needed.
- [x] `docs/SPEC_GUIDE.md`: no update needed.

## Recommended Next Step

Route back to implementation. Re-review is required after the open chat pane renders same-conversation live arrivals again; the stale force-scroll path should be rechecked only after that prerequisite passes.

---

# Round 4 — 2026-07-02

## Verdict

- Verdict: `pass`
- Highest Required Action: `pass`
- Reviewer mode: full.
- Tested entry: Web IM via Vite dev server `http://127.0.0.1:59613/chat/...` against isolated IM `127.0.0.1:59612` and an isolated Gateway `wt-feat451-r4` for direct-agent fork coverage.
- Test data: user `feat451r4ok_1782957560`; primary conversation `ac00f842d8044bfaa59c8aa1746a616d` with 75 historical messages; switch conversation `1241a5eaf3e6473c9f69f1504349fff9`; direct user-agent conversation `ef4fe2eb34d74dd8bca0920bb0387388` with a completed `r4-agent` reply.

## Runbook Notes

- Services were restarted for this round on isolated ports: IM `127.0.0.1:59612`, Vite `127.0.0.1:59613`, Gateway node `wt-feat451-r4`.
- Vite was started in real IM mode with `VITE_CHAT_API_MODE=im` and `VITE_IM_API_BASE_URL=http://127.0.0.1:59612`.
- Browser loaded `/src/main.tsx` from the worktree Vite server.
- The direct-agent fork precondition required a real Gateway-bound agent; `r4-agent` appeared online in IM nodes/agents before the fork journey.

## User Journeys Exercised

1. Desktop history pagination: open a 75-message conversation, verify initial latest page is capped at 50 rows, scroll into the upper portion, observe older messages prepended, no-more state, and stable reading position.
2. Round 3 live-arrival regression: while off-bottom in the active conversation, create a same-conversation message and verify both active pane and sidebar preview show it without jumping to bottom; repeat at bottom and verify bottom follow.
3. Conversation switch regression: navigate from the primary conversation to a second conversation and verify the second pane contains only its own messages.
4. Desktop and mobile input/actions: desktop Shift+Enter newline and Enter send; desktop right-click Copy; mobile Enter send, composer auto-grow cap, long-press Copy.
5. Mobile direct-agent fork: start an isolated Gateway, produce a completed direct-agent reply, long-press the agent reply on mobile, select fork, and verify the fork request succeeds with visible navigation to a new chat.

## Round 3 Failure Rechecked

- Round 3 Issue 1, open chat pane does not render same-conversation live messages: closed. Off-bottom live text `R4 live offbottom 1782957717086` appeared in `.chat-pane-messages` and `.chat-sidebar`; scroll stayed in history (`bottomDistance` increased from `1976` to `2043`, no bottom jump). Bottom live text `R4 live bottom 1782957717948` appeared in both places and stayed at `bottomDistance=0`.
- Conversation switching regression remains closed. Switching to `R4 Switch Clean OK` showed `R4 B history 001` through `006` and no `R4 A history` or live messages from the prior conversation.

## Issues

No in-unit acceptance issues found in Round 4.

## Acceptance Criteria Coverage

### Requirement: 消息历史可通过向上滚动分页加载更早内容 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 会话有多页历史，用户向上滚动触发加载 | `spec.md` | Desktop opened 75-message conversation and scrolled upward into the upper loaded region. | Initial pane had 50 rows and latest `R4 A history 075`; after scroll it had 75 rows and older `R4 A history 001`/`025` content. | `pass` | Reading stayed in history, not bottom. |
| 已经翻到最老的消息 | `spec.md` | Continued top scroll after older page loaded. | `No earlier messages` was visible and row count stayed at the full history size. | `pass` | Empty/no-more state is clear. |
| 正在加载更早消息 | `spec.md` | Delayed the real older-history request in the browser while still continuing to IM. | `Loading earlier messages...` was visible during the delayed request; older content appeared after response. | `pass` | Delay was only to observe the user-visible loading state. |

### Requirement: 新消息到达不打扰正在翻看历史的用户 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 用户正在看历史时收到新消息 | `spec.md`; M4 exit criteria | Off-bottom in primary conversation, then same-conversation message was created through public IM API. | Active pane and sidebar both showed `R4 live offbottom 1782957717086`; `scrollTop` stayed in the historical region (`2465 -> 2427`), with no bottom jump. | `pass` | This directly closes Round 3's pane/sidebar inconsistency. |
| 用户在底部时收到新消息 | `spec.md`; M4 exit criteria | Scrolled primary conversation to bottom, then created same-conversation message. | Active pane and sidebar both showed `R4 live bottom 1782957717948`; bottom distance stayed `0 -> 0`. | `pass` | Bottom follow works. |

### Requirement: 移动端输入法回车发送消息 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 移动端按回车发送 | `spec.md` | Mobile `390x844`: typed `R4 mobile enter send` and pressed Enter. | Message appeared in pane; textarea value became empty. | `pass` | No newline inserted. |
| 桌面端保持 Enter 发送 / Shift+Enter 换行 | `spec.md` | Desktop typed one line, pressed Shift+Enter, typed second line, then Enter. | Textarea held `R4 desktop line A\nR4 desktop line B`; after Enter, message appeared and composer cleared. | `pass` | Existing desktop behavior preserved. |

### Requirement: composer 输入框随内容自动增高 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 输入多行文字时 composer 增高 | `spec.md` | Mobile filled six lines into composer. | Textarea reported `rows="4"`, `clientHeight=100`, `scrollHeight=146`. | `pass` | It capped and became internally scrollable. |

### Requirement: 消息气泡支持复制与长按菜单 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 长按/右键消息气泡调出菜单 | `spec.md` | Desktop right-clicked a message; mobile long-pressed a visible message and released. | Desktop menu showed `Copy`; mobile menu showed `Copy` during hold and after release. | `pass` | Menu remained selectable after release. |
| 复制消息文本 | `spec.md` | Desktop chose Copy; mobile chose Copy after long-press release. | Desktop clipboard became `R4 A history 028 other`; mobile clipboard became `R4 live bottom 1782957717948`. | `pass` | Clipboard permission was granted in browser context. |
| 移动端单聊里长按 agent 回复进行 fork | `spec.md` | Mobile long-pressed completed `r4-agent` reply in direct user-agent chat, then selected fork. | Menu showed `Copy` + `fork`; `POST /im/v1/conversations/.../fork` returned `201`; URL changed from `/chat/ef4fe2...` to `/chat/e3aaf59263e64b7980f039d305620c5a`. | `pass` | Navigation is clear user feedback. |

### Requirement: 桌面与移动端体验一致 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 在手机端向上滚动加载历史 | `spec.md` | Mobile `390x844` opened the same primary conversation and scrolled upward into the upper loaded region. | Initial mobile pane had 50 rows; after upward scroll it had 78 rows, showed older history / `No earlier messages`, and stayed off-bottom (`bottomDistance=1976`). | `pass` | Reading position stayed in history rather than jumping to bottom. |
| 在手机端长按 agent 消息 fork | `spec.md` | Mobile direct-agent completed reply long-press. | `fork` stayed visible after release; click returned `201` and navigated to a new chat. | `pass` | Direct-agent fork is usable on mobile. |

## Side Findings

- Browser console still logged transient user-stream WebSocket handshake/reconnect warnings during page load and route changes. User-visible live arrivals, sidebar preview, and active pane behavior passed despite those warnings.
- An incorrectly created API-only agent conversation that omitted the current user showed a product-level send error (`sender_user_id is not a participant of conversation`). I did not classify it as an in-unit issue because the correct direct user-agent conversation path was subsequently verified and fork passed.

## Upper-Level Document Sync

- [x] `SPEC.md` (cross-package top architecture): no update needed; this unit changes IM frontend user behavior only.
- [x] `docs/specs/im/spec.md` (canonical IM behavior contract): still needs final orchestrator sync before landing; this unit's delta remains under `docs/changes/feat-451-chat-history-pagination/specs/im/spec.md`.
- [x] `AGENTS.md` / `CLAUDE.md`: no update needed.
- [x] `docs/SPEC_GUIDE.md`: no update needed.

## Recommended Next Step

Proceed toward landing after the normal orchestrator document-sync gate. No further product re-review is required for feat-451 acceptance.

---

# Round 5 — 2026-07-02

## Verdict

- Verdict: `pass`
- Highest Required Action: `pass`
- Reviewer mode: full, focused after M5 internal consistency fix.
- Tested entry: Web IM via Vite dev server `http://127.0.0.1:54758/chat/...` against isolated IM `127.0.0.1:54757`.
- Test data: user `feat451r5_1782962933539`; primary conversation `56c2e2548d694d3492261dab5ac530d9` with 75 seeded history messages plus live/browser messages; switch conversation `e047fa44878143dfa63b177c3160059f` with 8 messages.

## Runbook Notes

- Services were restarted for this round on isolated ports: IM `127.0.0.1:54757`, Vite `127.0.0.1:54758`.
- Frontend production build was regenerated before review: `cd src/IM/frontend && npm run build`.
- Vite was started in real IM mode with `VITE_CHAT_API_MODE=im` and `VITE_IM_API_BASE_URL=http://127.0.0.1:54757`.
- Browser loaded `/src/main.tsx` from the worktree Vite server; the rebuilt dist bundle contains the feat-451 user-facing markers (`No earlier messages`, `Loading earlier messages`, `Copy`, `fork`).
- Runbook health-check note: `GET /im/v1/health` returned 404 on this branch, but the IM service was live and data-plane APIs (`auth/register`, `conversations`, `messages`) worked. I treated this as a runbook endpoint mismatch, not a product issue in this unit.

## User Journeys Exercised

1. Desktop regression path: open a long-history conversation, load earlier history, verify no-more state and stable off-bottom reading position.
2. Round 4/M5 live-arrival path: while off-bottom in the active conversation, create a same-conversation message through the public IM API and verify both active pane and sidebar preview show it without jumping to bottom; repeat while already at bottom and verify bottom follow.
3. Conversation switch isolation: navigate from the primary conversation to the second conversation and verify the active pane contains only second-conversation messages.
4. Desktop and mobile input/actions: desktop Shift+Enter newline and Enter send; desktop right-click Copy; mobile Enter send, composer auto-grow cap, and touch long-press Copy.
5. Fork spot check: full direct-agent fork evidence remains Round 4. Round 5 did not start a Gateway-bound direct-agent stack; it spot-checked the adjacent mobile long-press menu surface with real touch events and confirmed a non-direct/non-forkable agent-like bubble did not incorrectly expose fork.

## Round 5 Focus Recheck

- Active-pane live arrivals remain closed after M5. Off-bottom live text `R5 live offbottom 1782963094566` appeared in both `.chat-pane-messages` and `.chat-sidebar`; the pane stayed in the historical region (`bottomDistance` remained large: `2704 -> 2601`) instead of jumping to bottom. Bottom live text `R5 live bottom 1782963097095` appeared in both places and the pane stayed at `bottomDistance=0`.
- Conversation switching remains closed. Directly opening the switch conversation showed only `R5 B history 001` through `R5 B history 008` in `.chat-pane-messages`; no `R5 A history`, `R5 live`, or `agent-like` text appeared in the active pane.
- History pagination remains usable. Desktop initial render showed 50 rows (`R5 A history 027` through latest); upward scroll loaded the full 76-row history, showed `No earlier messages`, and stayed off-bottom. Mobile initial render showed 50 rows; upward scroll loaded 79 rows and stayed off-bottom (`bottomDistance=2103`).

## Issues

No in-unit acceptance issues found in Round 5.

## Acceptance Criteria Coverage

### Requirement: 消息历史可通过向上滚动分页加载更早内容 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 会话有多页历史，用户向上滚动触发加载 | `spec.md` | Desktop opened a long-history conversation and scrolled upward into the upper loaded region. | Initial pane had 50 rows; after scroll it had 76 rows and included `R5 A history 001` through `075` plus latest agent-like row. | `pass` | Reading stayed off-bottom (`bottomDistance=2060`), not forced to latest. |
| 已经翻到最老的消息 | `spec.md` | Continued top scroll after the older page loaded. | `No earlier messages` was visible and row count stayed at the full history size. | `pass` | Empty/no-more state remains clear. |
| 正在加载更早消息 | `spec.md` | Inherited from Round 4; M5 did not change loading UI. | Round 4 delayed the real older-history request and observed `Loading earlier messages...`; Round 5 rebuilt the frontend and confirmed the marker remains in the bundle. | `pass` | No Round 5 user-visible regression observed around pagination. |

### Requirement: 新消息到达不打扰正在翻看历史的用户 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 用户正在看历史时收到新消息 | `spec.md`; M4/M5 exit criteria | Off-bottom in primary conversation, then same-conversation message was created through public IM API. | Active pane and sidebar both showed `R5 live offbottom 1782963094566`; `bottomDistance` stayed large (`2704 -> 2601`). | `pass` | Active pane/sidebar consistency did not regress after M5. |
| 用户在底部时收到新消息 | `spec.md`; M4/M5 exit criteria | Scrolled primary conversation to bottom, then created same-conversation message. | Active pane and sidebar both showed `R5 live bottom 1782963097095`; bottom distance stayed `0`. | `pass` | Bottom follow works. |

### Requirement: 移动端输入法回车发送消息 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 移动端按回车发送 | `spec.md` | Mobile `390x844`: typed `R5 mobile enter send` and pressed Enter. | Message appeared in pane; textarea value became empty. | `pass` | No newline inserted. |
| 桌面端保持 Enter 发送 / Shift+Enter 换行 | `spec.md` | Desktop typed one line, pressed Shift+Enter, typed second line, then Enter. | Textarea held `R5 desktop line A\nR5 desktop line B`; after Enter, message appeared and composer cleared. | `pass` | Existing desktop behavior preserved. |

### Requirement: composer 输入框随内容自动增高 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 输入多行文字时 composer 增高 | `spec.md` | Mobile filled six lines into composer. | Textarea reported `rows="4"`, `clientHeight=100`, `scrollHeight=146`. | `pass` | It capped and became internally scrollable. |

### Requirement: 消息气泡支持复制与长按菜单 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 长按/右键消息气泡调出菜单 | `spec.md` | Desktop right-clicked a message; mobile used CDP touch long-press on a visible message and released. | Desktop menu showed `Copy`; mobile menu showed `Copy` during hold and after release. | `pass` | Real touch event injection was required; mouse hold did not count as mobile evidence. |
| 复制消息文本 | `spec.md` | Desktop chose Copy; mobile chose Copy after touch long-press release. | Desktop clipboard became `R5 live bottom 1782963097095`; mobile clipboard became `R5 mobile enter send`. | `pass` | Clipboard permission was granted in browser context. |
| 移动端单聊里长按 agent 回复进行 fork | `spec.md` | Inherited full direct-agent fork from Round 4; Round 5 spot-checked the menu surface only. | Round 4 direct-agent fork returned `201` and navigated to a new chat. Round 5 touch long-press on a non-direct/non-forkable agent-like bubble kept Copy visible and did not incorrectly expose fork. | `pass` | M5 did not touch fork behavior; no obvious menu regression was observed. |

### Requirement: 桌面与移动端体验一致 — group result: `pass`

| Scenario | Expected Source | Verification | Evidence | Result | Notes |
|---|---|---|---|---|---|
| 在手机端向上滚动加载历史 | `spec.md` | Mobile `390x844` opened the same primary conversation and scrolled upward into the upper loaded region. | Initial mobile pane had 50 rows; after upward scroll it had 79 rows, showed older history / `No earlier messages`, and stayed off-bottom (`bottomDistance=2103`). | `pass` | Reading position stayed in history rather than jumping to bottom. |
| 在手机端长按 agent 消息 fork | `spec.md` | Inherited full direct-agent fork from Round 4; Round 5 touch spot check verified the long-press menu did not regress. | Copy stayed visible after release; non-forkable agent-like bubble did not show fork. | `pass` | Full fork navigation was already verified in Round 4 and M5 did not alter that surface. |

## Side Findings

- Full direct-agent fork navigation was not re-run in Round 5 because this isolated stack did not start a Gateway-bound agent. I did not classify this as an issue because Round 4 already passed the full direct-agent fork journey, and M5 is an internal history reset consistency fix with no fork-surface changes.
- The documented `/im/v1/health` health check returned 404, while real data-plane APIs and the browser product route worked. This is a runbook mismatch to clean up outside this product acceptance decision.

## Upper-Level Document Sync

- [x] `SPEC.md` (cross-package top architecture): no update needed; this unit changes IM frontend user behavior only.
- [x] `docs/specs/im/spec.md` (canonical IM behavior contract): still needs final orchestrator sync before landing; this unit's delta remains under `docs/changes/feat-451-chat-history-pagination/specs/im/spec.md`.
- [x] `AGENTS.md` / `CLAUDE.md`: no update needed.
- [x] `docs/SPEC_GUIDE.md`: no update needed.

## Recommended Next Step

Proceed toward landing. No further product re-review is required for feat-451 acceptance.
