# Code review R3 closure

- Mode: closure of the single surviving R2 finding only.
- Finding origin: `55defc67096df2255bf54be421619496d869c3f0` (introduced while fixing R1 at `7987f40bc`).
- Reviewed fixed head: `b970e20a60c0d1e18bc10d1d734b75d3d11cf4d6`.
- Result: **closed**. `code-review-r3.json` is `[]`; no surviving finding in this closure scope. The other seven R1 findings remain closed as recorded by R2; they were not re-audited.

## Closure evidence

The backend's `notify_conversation_membership` frame has no replay cursor and is shared by creation, rename, member changes and deletion. `GET /im/v1/conversations` returns the authenticated user's actual current memberships (`web_im.py:530-561`).

At the fixed head, `ChatStore.consume` handles the control frame before event-id deduplication, marks the chat as checking access, removes visible history and schedules an authoritative list read (`ChatStore.swift:83-92`). It retains the draft, pending send and upload selections during the check. Reconciliation distinguishes allowed chats from absent memberships (`ChatStore.swift:126-136`): allowed chats are restored to the list with updated metadata; absent chats have history, pagination, draft, attachments and pending send cleared and are marked revoked. The scheduled refresh reloads the visible authorized history. History reads and new sends are blocked while checking. The composer shows a permission-check state with retry when the list read fails (`ConversationView.swift:61-65`).

This closes the R2 trigger: a rename/add/create notification no longer permanently hides a still-authorized chat or deletes its draft, and actual removal still clears its private cached state after the authoritative membership result.

## Test evidence read and reused

- `/tmp/nano-feat578-membership-red.log`: the rename regression failed before the fix with missing draft and attachment assertions.
- `/tmp/nano-feat578-membership-green.log`: all three ChatState regressions passed (cursor-free actual removal, authorized rename, 61-message history gap).
- `/tmp/nano-feat578-xctest-r3.log`: **TEST SUCCEEDED**, 11 XCTest plus 10 Swift Testing tests.
- Simulator result bundle from the log: `/tmp/nano-ios-build/Logs/Test/Test-NanoIM-2026.10.05_01-56-09-+0800.xcresult`.

No implementation was changed and no test rerun, phone/UI control or service control was performed by this reviewer. The caller's observed peer-chat composer/send is not used as independent UI acceptance. This closes the scoped code-review finding; it does not grant product or final verification acceptance.
