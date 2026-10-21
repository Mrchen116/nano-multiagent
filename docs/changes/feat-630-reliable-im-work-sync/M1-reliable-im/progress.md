# M1 implementation evidence

Base: `5665af409426f22eec86d03d68e6ffbb1c935d00`. Implementation is isolated in the attached `unit/feat-630` worktree; production and dirty main are untouched.

## Regression ownership

- Keep PA Inbox, controls, personal admission, correction/revalidation and single-thread coverage. Update existing fixtures to supply distinct relay identities for distinct inputs, acknowledge the new small scope request, and retain original behavioral assertions.
- Extend channels coverage at its real WebSocket seam. `realtime-window.test.ts` owns the newly concurrent transport window, lost/late ACK isolation and reserved control slots; existing lifecycle/redaction tests remain.
- Work HTTP cursor/parts and its client recovery have separate protocol owners. Dedicated tests cover bounded bodies, machine-only auth, atomic projection, restart, hashes, quotas and cancellation.
- Ordinary Web sending owns IndexedDB attempt persistence and normal Composer interaction. Existing optimistic history/echo tests are retained; assertions wait for the durable completion boundary.
- Existing private background retry test changes from accepting a mutated key to requiring 409, retaining the frozen relay background assertion.
- Real center reconnect/window recovery is protected at the existing process E2E seam. The manual `tests/e2e/reliability/im-load.mts` load harness creates only isolated test identities and exercises real HTTP/WS and SQLite admission.

## Meaningful RED

- Channels: lost business ACK blocked the subsequent receipt; window overflow had no bounded rejection. Both new real-WS cases failed before implementation (2026-10-21 20:46 CST).
- PA: unavailable runtime caused input to be missing from Inbox; duplicate receipt obligation API was absent. Both cases failed before implementation (20:48 CST, after required workspace package build).
- Work: valid offline runtime token GET cursor returned 401 instead of 200 (20:45 CST).
- Web: three response-loss API cases and four ordinary Composer identity/reload cases failed before implementation; implementation slice reports are retained in task history.

## Current validation

- Workspace build and typecheck passed after integration.
- PA/channels integration regression first pass: 168/176, with identified migration/observation/fixture issues; affected PA cases after corrections: 49/49 then 48/48 including controls and durable admission.
- Work server/client: 12/12. Ordinary backend helper: 7/7.
- Frontend related regression first slice: 165/165; final focused Composer/API/workspace: 85/85. Full suite exposed asynchronous completion assertions; corrected affected suites: 65/65.
- First full backend run: 506/508; repaired two obsolete fixture expectations and moved dispatcher timer ownership into server lifecycle. Full rerun remains required.
- Real stack is created only with scripts/e2e-up.sh and cleaned with scripts/e2e-down.sh. Browser, fault and sustained-load acceptance are in progress; no final acceptance claim is made here.
