# feat-451-M2 — Progress

## Baseline

- Context: 新 worker 接 round 1 fix milestone；unit 分支已有 M1、verification pass、acceptance fail 和 M2 design 行。
- Evidence:
  - Sync gate: local `unit/feat-451` = `origin/unit/feat-451` at `dcbeb1636f9547663b3d23ba0062820b86c0e59e`.
  - `cd src/IM/frontend && npm run test`: initial run failed because worktree had no `node_modules` (`vitest: command not found`); after `npm ci`, baseline passed: 63 files / 575 tests, with existing React `act(...)` and `--localstorage-file` warnings.
  - `cd src/IM/frontend && npx tsc -b`: passed.
- Root-cause notes before implementation:
  - Realtime blocking: current page has two separate user stream paths. `openChatStream` opens a raw socket once from `useAuthStore.getState()` and does not share the existing resume/ping/reconnect machinery in `attachUserConversationStream`; tests seed auth before render, masking real browser timing and recovery. The correct architecture for open-chat bubbles is to consume the same shared user stream and filter current conversation events.
  - Mobile menu major: long-press opens menu from `touchstart` timer, but document `mousedown` outside handling and lack of touch/pointer ownership make release/tap fragile in real mobile browsers; no regression currently exercises release before selecting. Copy failure is explicitly fire-and-forget and closes the menu.

## R1 — 实时消息与历史分页状态正确性

- Context: 修复 reviewer blocking 的同会话新消息不可见问题，以及 code review confirmed 的 history anchor 泄漏、同 cursor 重复请求、metadata unknown 误显 no-more 三项 correctness bug。
- Decision: 当前聊天气泡不再开启独立 `openChatStream`；改为复用 `attachUserConversationStream` 的 owner-scoped 用户流，把 `message.*` / tool / thinking / permission 事件转换为 `WsEvent` 后交给同一个 reducer。历史分页改为三态 `hasMoreHistory`（unknown / true / false），并用同步 `historyRequestRef` guard 同一会话同 cursor 的并发请求；会话切换时同步 reset loading / cursor / request / MessagePane anchor refs。
- Rationale: 共享用户流已经承载侧边栏刷新、resync、node/agent status，且具备真实浏览器需要的 owner token 生命周期；会话内气泡沿用该通道可消除双 socket 分叉。历史分页的 bug 都源于仅靠 async React state 表达“正在请求”和把 unknown 折叠为 false，必须用同步 ref 和明确 unknown 状态建模。
- Evidence:
  - Tests: `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx` passed: 2 files / 95 tests. New red→green coverage includes shared user stream same-conversation append, duplicate older-history guard, conversation-switch unknown metadata, MessagePane anchor reset, and MessagePane unknown metadata no-more suppression.
  - Entry: `ChatWorkspacePageV2` now consumes live message events through shared user stream; `MessagePane` receives `hasMoreHistory` as boolean/null.
  - Frontend State Matrix: loading/empty/missing nullable data covered by targeted component/integration tests; desktop/mobile scroll-follow still covered by existing MessagePane tests.
  - Browser QA: pending R2 C3 combined true-browser run for reviewer blocking/major scenarios.
  - E2E/Regression: `cd src/IM/frontend && npx tsc -b` passed.
  - Visual/Interaction: no visual asset changes; scroll behavior regressions covered by MessagePane tests for off-bottom no disturb and bottom follow.
- Rollback: Revert `0e831b65` and C1 test commit `2d32b995` if the shared stream conversion causes live event regressions; this restores the previous independent `openChatStream` path and previous history state semantics.
- Commits: C1=`2d32b995`, C2=`0e831b65`, C3=`222ef617`
- Next: R2

## R2 — 移动菜单、Copy 失败反馈、桌面 Enter 与浏览器验收

- Context: 修复 reviewer major 的移动端长按菜单，以及 code review confirmed 的 copy failure 静默问题；补 verifier warning 的桌面 Enter 独立测试，并跑真服务/真浏览器覆盖 reviewer blocking + major 路径。
- Decision: 移动长按菜单在 `touchstart` 定时打开后由菜单自身持有生命周期，`touchend` 不关闭菜单，并忽略一次同气泡上的合成 `mousedown`；移动/桌面 contextmenu 均 `preventDefault`，移动端额外用 CSS 抑制 touch callout/selection。Copy 改为 async success/failure 分支，clipboard 缺失或 rejected 时显示可观察错误并保持菜单打开；成功后才关闭菜单。移动菜单保留 Copy 和 fork，桌面右键 Copy 与 hover fork 路径保持。
- Rationale: 原 bug 的触发点在真实移动浏览器的事件序列：长按 timer 刚打开菜单，松手后的合成鼠标事件会被 document outside handler 当成外部点击并关闭菜单。把“同一气泡长按后的下一次 mouse down”识别为同源事件可以保留桌面 outside-click 语义，同时不牺牲移动菜单可点性。Copy failure 必须停止 fire-and-forget，否则用户无法分辨失败和成功。
- Evidence:
  - Tests:
    - `cd src/IM/frontend && npm run test -- src/features/chat/v2/components/message-pane.test.tsx` passed: 74 tests.
    - `cd src/IM/frontend && npm run test -- src/features/chat/v2/chat-workspace.integration.test.tsx src/features/chat/v2/components/message-pane.test.tsx && npx tsc -b` passed: 2 files / 99 tests, TS build passed.
    - `cd src/IM/frontend && npm run test` passed: 63 files / 584 tests, with existing React `act(...)` and `--localstorage-file` warnings.
    - `cd src/IM/frontend && npx tsc -b` passed.
  - Entry:
    - `MessagePane`: mobile long-press menu lifecycle, mobile contextmenu prevention, copy failure status, desktop Enter send regression.
    - `ChatWorkspacePageV2`: shared user stream realtime dispatch from R1 was exercised through the browser path below.
  - Frontend State Matrix:
    - `error`: clipboard missing/rejected shows `chat.messagePane.copyError` and keeps menu open; en/zh both updated.
    - `submitting`: desktop `isMobile=false`, Enter without Shift sends and clears.
    - `mobile viewport`: long-press release keeps menu selectable; Copy works; completed direct-agent reply fork works.
    - `desktop viewport`: right-click Copy works; hover fork remains visible/enabled and navigates.
  - Browser QA:
    - Environment: worktree ephemeral IM/Gateway/Vite; `IM_URL=http://127.0.0.1:63475`, `VITE_URL=http://127.0.0.1:63476`; chat URL `http://127.0.0.1:63476/chat/be4b9546005d422f856584b7934bb463`.
    - Desktop viewport `1366x900`: opened chat with 50 visible history messages. Sent a prompt through the real composer; Gateway produced a new agent bubble in the already-open chat (`agent count 0 -> 1`) and scroll followed bottom (`scrollTop=2854`, `clientHeight=670`, `scrollHeight=3524`, `bottomDistance=0`).
    - Desktop viewport `1366x900`: while away from bottom, injected another user prompt through the real REST/Gateway path; new agent bubble arrived in the already-open chat (`agent count 1 -> 2`) and the viewport did not jump (`scrollTop` stayed `1527`; `bottomDistance` increased `2715 -> 2836`).
    - Desktop viewport `1366x900`: right-click menu showed `Copy`, Copy closed the menu; hover fork on completed agent reply was visible/enabled and navigated to `http://127.0.0.1:63476/chat/cd0a19b53b48412094e40c3c0ef2ae7a`.
    - Mobile viewport `390x844`, `isMobile=true`, `hasTouch=true`: long-press user bubble, release, menu still showed `Copy`; `window.getSelection()` remained empty; Copy succeeded and closed the menu.
    - Mobile viewport `390x844`, `isMobile=true`, `hasTouch=true`: long-press completed direct-agent reply, release, menu showed enabled `Fork`; clicking it navigated to `http://127.0.0.1:63476/chat/a06e972b23144657b4b4be85db04ced8`.
    - Console/network: no `pageerror`; browser console only showed transient WebSocket close warnings during context teardown/reconnect, after the expected live events had already arrived.
  - E2E/Regression: true-browser path used real IM service, real Gateway, real Vite proxy, and real Playwright Chromium contexts; no committed e2e fixture added for this fix milestone.
  - Visual/Interaction: no layout shift observed during off-bottom live arrival. Menu positioning hardcoded clamp was not rewritten in this milestone because the major failure was lifecycle/event ownership, and current en/zh labels plus error text fit the existing menu width in desktop/mobile verification.
- Issue mapping:
  - 1 realtime blocking: fixed by `0e831b65`; browser evidence shows same-conversation agent messages entering open chat, bottom follow, and off-bottom no disturb.
  - 2 mobile long-press menu: fixed by `0462a1e5`; component tests and mobile browser evidence cover release-stable Copy/fork and no text selection.
  - 3 history anchor reset: fixed by `0e831b65`; `message-pane.test.tsx` covers `conversation.id` switch reset.
  - 4 duplicate `loadOlderMessages`: fixed by `0e831b65`; integration test covers same cursor only one concurrent request.
  - 5 unknown metadata no-more: fixed by `0e831b65`; component/integration tests cover nullable history metadata and conversation switch.
  - 6 copy failure: fixed by `0462a1e5`; component tests cover missing clipboard and rejected `writeText`; en/zh text added.
  - 7 desktop Enter: covered by `9af603f1`; `isMobile=false`, Enter/no Shift sends and clears.
  - 8 cleanup: token usage / permission request merge duplication reduced through `mergeMessageWithExisting`; redundant bottom-follow branch simplified. Menu clamp left unchanged for the reason above.
- Rollback: Revert `0462a1e5` and C1 test commit `9af603f1` for mobile/copy/Enter only; revert `0e831b65` and `2d32b995` for realtime/history only. Browser-created local QA conversations were in the ephemeral worktree IM DB and are removed with the worktree cleanup.
- Commits: C1=`9af603f1`, C2=`0462a1e5`, C3=`this docs commit`
- Next: Milestone integration
