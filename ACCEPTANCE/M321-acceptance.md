# Final browser acceptance after M316 M318 M319 M320

- Scope ID: M321
- Verdict: pass
- Reviewed By: product-acceptance-reviewer

## Scope

Final real-browser product acceptance of the freshly restarted latest-main runtime at `http://127.0.0.1:8011`, limited to verifying the repaired direct chat path, unread badge clearing persistence for conversation A, visible lightweight timestamps in message bubbles, and prompt synchronization of the conversation-list preview with the actual latest message.

## Materials Read

- README.md
- docs/operator-runbook.md
- docs/spec-implementation-conflicts.md
- ACCEPTANCE/M311-acceptance.md
- Caller-provided milestone scope and launch instructions

## User Journeys Exercised

- Open `http://127.0.0.1:8011/` and verify the rebuilt frontend runtime is what is being served
- Verify direct chat no longer shows a false `Chat unavailable` on the repaired path
- Open conversation A at `http://127.0.0.1:8011/chat/5e82e46169d044d18662e5bc853065bb` and verify unread badge clears and stays cleared after refresh
- Verify sent and received message bubbles visibly show lightweight timestamps
- Verify conversation list preview matches the actual latest message promptly and does not visibly catch up in delayed steps after opening a chat

## Passes

- Opening `http://127.0.0.1:8011/` landed in the Web IM shell at `/chat`, and the browser reported a bundled script from the IM host itself: `http://127.0.0.1:8011/assets/index-B94-8heR.js`. Product judgment: this is consistent with the freshly rebuilt frontend runtime being served from the latest IM host entrypoint, not a separate dev server. Evidence: `.playwright-cli/page-2026-03-25T07-26-19-421Z.yml`, `.playwright-cli/page-2026-03-25T07-28-26-951Z.png`.
- The repaired direct chat path `http://127.0.0.1:8011/chat/5e82e46169d044d18662e5bc853065bb` opened successfully, showed a live composer (`Type message` + `Send`), and did not show any `Chat unavailable` card or disabled-send state. Evidence: `.playwright-cli/page-2026-03-25T07-26-52-307Z.yml`, `.playwright-cli/page-2026-03-25T07-28-25-416Z.yml`.
- Conversation A's list item preview matched the actual latest visible message in the thread (`哈哈哈并发处理直接被拒绝了 😂 还要继续吗？`) on open, immediately after reload, and again after a 2-second post-reload wait; no visible delayed catch-up behavior was observed. Evidence: `.playwright-cli/page-2026-03-25T07-26-52-307Z.yml`, `.playwright-cli/page-2026-03-25T07-28-21-817Z.yml`, `.playwright-cli/page-2026-03-25T07-28-25-416Z.yml`.
- Conversation A showed no unread badge once opened, and that cleared state persisted after refresh; the targeted direct-thread row continued to render without any `new` pill before or after reload. Evidence: `.playwright-cli/page-2026-03-25T07-26-52-307Z.yml`, `.playwright-cli/page-2026-03-25T07-28-21-817Z.yml`, `.playwright-cli/page-2026-03-25T07-28-25-416Z.yml`.
- Sent and received bubbles in conversation A visibly displayed lightweight timestamps (`16:48`, `16:50`) beside the message content, satisfying the timestamp visibility requirement. Evidence: `.playwright-cli/page-2026-03-25T07-26-52-307Z.yml`, `.playwright-cli/page-2026-03-25T07-28-25-416Z.yml`, `.playwright-cli/page-2026-03-25T07-28-26-951Z.png`.

## Issues

None.

## Retest Focus

- None
