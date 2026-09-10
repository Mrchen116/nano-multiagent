# M1 reply-images implementation record

## Scope and decisions

- Worktree: `.worktrees/unit-feat-551`, branch `unit/feat-551`, base `origin/main@f455c6220`.
- Only the approved feat-551 documentation commit was cherry-picked (`1eb93ee67`). Main checkout's unrelated changes were not moved or staged.
- 2026-09-10 user override: skip the final `change-code-review` gate because of its cost. Product acceptance, spec/design verification, corrected-delta verification, real-entry evidence and CI remain required. Do not merge the PR.
- IM backend, frontend, provider, lifecycle and shadow work used disjoint implementation agents in the unit worktree; main owns integration.
- Reuse the existing Feishu public/data safe downloader through `read_outbound_image`; local export reads and durable snapshots belong to Gateway. This avoids duplicating the pinned-DNS/security implementation.
- `ImageReplyConnection` projects at the existing outgoing IM-frame seam, covering repeated completion/roll exits without modifying model events. It is a delivery-scoped view, not another transport.
- New output keys use the already-allocated run-global bubble ordinal, retaining it when a kernel message ID arrives. Shadow stores persist it; context follows the persisted shadow key. Legacy rows receive distinct migration keys.
- Group publish qualification is the existing successfully committed `assistant_message` fact. Current contracts explicitly do not retract committed replies for later input; `try_commit_output` cannot be repeated after run terminal. Final admission rechecks visibility and session generation, not a new group revision protocol.

## Implementation baseline

- Python: `PYTHONPATH=src <main>/.venv/bin/python -m pytest -m 'not e2e' -n 4 --dist worksteal`: **3585 passed, 1 failed**, 165.73s, before product edits.
- Existing failure: `tests/contract/test_kernel_sdk_behavior_contract.py::test_submit_steer_preserves_structured_image_content`, expects two model requests but observed one. Isolated unchanged rerun passed (0.25s). The test waits for run `running`, not first model-request entry; do not count the rerun as a clean full baseline or modify kernel behavior in this unit.
- Frontend baseline: message-pane/auth-fetch **98 passed** after `npm ci`. Existing dependency audit notices recorded; no dependency upgrades.

## Test strategy and current evidence (in progress)

| Risk / owner | Existing coverage disposition | New evidence |
|---|---|---|
| Private IM image authentication, immutable bytes, fork ownership | Existing messages/uploads/fork tests keep | New private resource API integration file; 44 relevant tests passed |
| Inline image loading, account teardown, zoom | Existing message-pane/auth-fetch tests keep | New message-image lifecycle tests Red → 6 Green; frontend full suite 695 passed with `--maxWorkers=2`; build passed |
| Stream destination privacy | No prior outgoing local-image parser | New stream module tests, shared complete/stream parser; parser + snapshot tests 15 passed |
| Durable snapshots/export scope | Existing inbound-image tests keep (different direction) | New ReplyImages boundary tests: source deletion/restart, symlink/outside/type failures, limits, code examples |
| Provider preparation/publication | Existing rich-message/public-network tests keep | Existing adapter/client files extended; 45 tests passed |
| Reset/terminal retention and admission | Existing admission/stream/lifecycle tests keep; do not grow the 1174-line admission file | New reset-delivery tests and tracker extensions; 32 focused + 70 related tests passed |
| Cancellation during delivery | Failed terminal remains eligible for partial text | Stream cancel/failed contrast and stop-before-terminal tests; 34 focused tests passed |
| Shadow recovery and revoked output | Existing shadow/reconnect tests keep | New cross-module recovery file; 44 tests passed; source removed before recovery still uploads saved bytes; revoke persists across restart |
| Background reply identity | Existing subscription/control tests keep | New background image seam integration file; 30 tests passed |
| Router receipt collection | Existing router dedupe tests keep | New two-phase/cancellation file; 17 related tests passed |
| Production metadata seam | Existing exact metadata assertions updated with run/output identity, not weakened | 77 relevant tests passed |

Full implementation, live browser/Feishu evidence and independent gates are not yet complete. These test counts are scoped runs, not a sum or a real-provider success claim.

## Runtime evidence

- Native IM/Gateway launched with `scripts/e2e-up.sh` in controlled tmux session `feat551-e2e`, default isolated config; IM port `62232`, node `wt-unit-feat-551-18135`.
- Test browser logged in with the dedicated configured identity and observed both E2E Agents online.
- Real Agent generated a 480×240 PNG using its bash/Python tool. The first answer used invalid bare-path Markdown with spaces and correctly produced a per-image failure; the product prompt now explicitly specifies literal angle brackets around paths. A second real answer using valid angle-bracket syntax displayed the image between its two explanatory paragraphs.
- Desktop 1280px: displayed width 320px, natural size 480×240. Mobile 390px: image width 250.8px and document width 390px (no horizontal overflow). Click opened the image dialog; Escape closed it and restored focus. Browser warning/error logs were empty.
- Reload retained the image. Then the test Gateway was stopped and the original file moved to a `.retention-test-backup` name; a fresh page load still obtained a complete 480px image through an IM-backed blob URL while the node displayed offline. This is a real persistence check, not a source-file/cache claim.
- Durable screenshots: [desktop](evidence/web-im-1280.png), [mobile](evidence/web-im-390.png), [zoom](evidence/web-im-zoom.png), [Gateway offline](evidence/web-im-gateway-offline.png). Desktop/mobile compare against prototype `#reply`: text/image/text order, constrained proportional size and zoom match. Pending/error full reference comparison is not yet complete. These screenshots predate the summary-path correction and are not evidence for that correction.
- Live validation found a separate sidebar preview leak: lifecycle report/receipt summary still contained raw Markdown while `messages.content` and `message.completed` already contained private image URLs. The outgoing report/receipt now uses `[图片]` for image references, retaining code examples and the original runtime text. Completed messages are authoritative for previews, with destinations reduced to `[alt]`; startup reconstruction uses the same projection. Regression tests reproduced the original failure before the correction. A fresh-stack browser check remains required.
- Feishu profile authentication checked: test Bot and user verified, user token valid. No Feishu test message sent yet; explicit sending confirmation requested under the lark-im skill.

## Broad regression (2026-09-10)

- CI-equivalent Python shards: **1802 passed** (agent/PA, 20.45s) and **1841 passed** (remaining, 58.41s), no skips added. These ran before the final sidebar preview correction.
- An intermediate PA-only run had one transient `FileNotFoundError` reading a user-global `lark-wiki/SKILL.md`; the unchanged isolated test passed, then both complete shards above passed. No global skill files or unrelated runtime behavior were changed.
- Frontend rerun: **695 passed** / 72 files, 30.75s, `npm run test -- --maxWorkers=2`. Production build passed (`index-dWoMkIuG.js`); audit critical threshold passed with 7 pre-existing low/moderate/high notices and no dependency changes.
- Ruff check, all-file format check and staged diff-check passed. Documentation integrity passed (240 maintained Markdown sources, 70 required routes).

## Pause / resumable state

- Dedicated E2E stack stopped using `e2e-down.sh`; owned tmux session `feat551-e2e` removed. No production process was restarted. Test data and the unit worktree are retained as unfinished implementation state, not a running service.
- Sending confirmation is pending for the dedicated Feishu test identity/Bot. Consequently, no real Feishu success claim, independent final gates, canonical merge, archive, PR or deployment has been performed.

## Remaining

Complete integration and real-entry verification, update as-built design/deltas, run product reviewer/verifier, merge verified canonical specs, run CI equivalents, archive, create ready PR, wait CI green, clean owned runtime/worktree. Code-review gate omitted by explicit user override.
