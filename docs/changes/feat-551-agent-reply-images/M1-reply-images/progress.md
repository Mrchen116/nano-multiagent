# M1 reply-images implementation record

## Scope and decisions

- Worktree: `.worktrees/unit-feat-551`, branch `unit/feat-551`, initial base `origin/main@f455c6220`; synchronized to `origin/main@6ec610be5` before independent gates.
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

## Test strategy and current evidence

| Risk / owner | Existing coverage disposition | New evidence |
|---|---|---|
| Private IM image authentication, immutable bytes, fork ownership | Existing messages/uploads/fork tests keep | New private resource API integration file; 44 relevant tests passed |
| Inline image loading, account teardown, zoom | Existing message-pane/auth-fetch tests keep | New message-image lifecycle tests Red → 6 Green; frontend full suite 695 passed with `--maxWorkers=2`; build passed |
| Stream destination privacy | No prior outgoing local-image parser | New stream module tests, shared complete/stream parser; parser + snapshot tests 15 passed |
| Durable snapshots/export scope | Existing inbound-image tests keep (different direction) | New ReplyImages boundary tests: source deletion/restart, PNG/JPEG/WebP, exact and exceeded 10 MiB, unreadable/symlink/outside/type failures, five-source limit, public/data snapshots and code examples |
| Provider preparation/publication | Existing rich-message/public-network tests keep | Existing adapter/client files extended; 45 tests passed |
| Reset/terminal retention and admission | Existing admission/stream/lifecycle tests keep; do not grow the 1174-line admission file | New reset-delivery tests and tracker extensions; 32 focused + 70 related tests passed |
| Cancellation during delivery | Failed terminal remains eligible for partial text | Stream cancel/failed contrast and stop-before-terminal tests; 34 focused tests passed |
| Shadow recovery and revoked output | Existing shadow/reconnect tests keep | New cross-module recovery file; 44 tests passed; source removed before recovery still uploads saved bytes; revoke persists across restart |
| Background reply identity | Existing subscription/control tests keep | New background image seam integration file; 30 tests passed |
| Router receipt collection | Existing router dedupe tests keep | New two-phase/cancellation and failed-send/restart tests: receipts precede public send; same App reuses the saved key and another App uploads separately |
| Production metadata seam | Existing exact metadata assertions updated with run/output identity, not weakened | 77 relevant tests passed |

Implementation and the main live Web IM/Feishu journeys are complete. These test counts are scoped runs rather than a synthetic total; the real-provider evidence is recorded separately below.

## Runtime evidence

- Native IM/Gateway launched with `scripts/e2e-up.sh` in controlled tmux session `feat551-e2e`, default isolated config; IM port `62232`, node `wt-unit-feat-551-18135`.
- Test browser logged in with the dedicated configured identity and observed both E2E Agents online.
- Real Agent generated a 480×240 PNG using its bash/Python tool. The first answer used invalid bare-path Markdown with spaces and correctly produced a per-image failure; the product prompt now explicitly specifies literal angle brackets around paths. A second real answer using valid angle-bracket syntax displayed the image between its two explanatory paragraphs.
- Desktop 1280px: displayed width 320px, natural size 480×240. Mobile 390px: image width 250.8px and document width 390px (no horizontal overflow). Click opened the image dialog; Escape closed it and restored focus. Browser warning/error logs were empty.
- Reload retained the image. Then the test Gateway was stopped and the original file moved to a `.retention-test-backup` name; a fresh page load still obtained a complete 480px image through an IM-backed blob URL while the node displayed offline. This is a real persistence check, not a source-file/cache claim.
- Durable screenshots: [desktop](evidence/web-im-1280.png), [mobile](evidence/web-im-390.png), [zoom](evidence/web-im-zoom.png), [Gateway offline](evidence/web-im-gateway-offline.png). Desktop/mobile compare against prototype `#reply`: text/image/text order, constrained proportional size and zoom match. These screenshots predate the summary-path correction and are not evidence for that correction.
- Live validation found a separate sidebar preview leak: lifecycle report/receipt summary still contained raw Markdown while `messages.content` and `message.completed` already contained private image URLs. The outgoing report/receipt now uses `[图片]` for image references, retaining code examples and the original runtime text. Completed messages are authoritative for previews, with destinations reduced to `[alt]`; startup reconstruction uses the same projection. Regression tests reproduced the original failure before the correction.
- A fresh-stack browser check on IM `57321` confirmed the corrected sidebar preview contains only `已停止当前操作，并已开始新会话。`, with no workspace path. The success and partial-failure images loaded through authenticated `blob:` URLs at their natural dimensions (480×270 and 360×200); the partial failure stayed inline between `中间文字` and `结束`. The zoom dialog opened and closed, browser warning/error logs were empty, and [the fresh-stack screenshot](evidence/web-im-feishu-partial-failure.png) records the result.
- Independent Round 1 acceptance delayed and interrupted real authenticated image reads to verify the transient UI states. Loading and error remained at both image positions while surrounding text stayed readable, at [desktop 1280×900 loading](evidence/web-im-desktop-loading.png), [mobile 390×844 loading](evidence/web-im-mobile-loading.png), [desktop error](evidence/web-im-desktop-error.png), and [mobile error](evidence/web-im-mobile-error.png). These durable screenshots close the prototype pending/error must-match matrix; the accepted journey also retried one failed image without disturbing its neighbour.
- Round 2 verification correctly found that the two original 390×844 pending/error screenshots still overflowed the Agent bubble. Browser geometry isolated the cause to the Markdown grid item's automatic minimum width: the 256.08px content area retained the child state's 320px intrinsic width, making the state end at x=385 while its card ended at x=334. Setting `min-width: 0` on direct `.im-md` grid items lets the existing `max-width: 100%` state constraint resolve against the real content width. The same 390px browser probe then measured a 256.08px state fully inside its 282.08px card and `documentElement.scrollWidth === clientWidth === 390`; final real-product screenshots are refreshed in the targeted acceptance pass.

### Feishu authorization run

- User authorized the dedicated test user/Bot messages. After a false start in an ephemeral terminal (both IM and Gateway exited with that terminal, local saga count stayed zero), the stack was restarted in an owned persistent tmux session. The repository runtime probe then passed and observed exactly one runtime card plus its plain shadow content.
- A real image request reached the feat-551 Agent, which generated a valid PNG under `exports`. It exposed a multi-bubble identity bug: when the second assistant bubble began, the first bubble's intermediate provider delivery used the new bubble's `output_key`; the immutable image manifest for `bubble:1` was therefore frozen with the first text and the final image could not replace it. `test_each_external_bubble_freezes_images_under_its_own_output_key` reproduced this failure before the fix. The observer now passes the rolled snapshot's key for the prior intermediate bubble, including IM-offline delivery; the focused integration tests pass.
- A pre-existing `feat546` test Gateway initially competed for the dedicated App/Bot. After the user explicitly authorized stopping all of that isolated test stack, its Gateway, IM, children and tmux session were stopped while unrelated ref-550 processes were left untouched. A fresh feat-551 stack acquired the exclusive listener lock and its repository probe passed.
- Real success request `om_x100b6513bf9ff8a0b283de3b6cf5e87` reached feat-551 run `run_e396e706390a34a9`. The Agent generated a 480×270 PNG; Gateway persisted the final bubble snapshot, IM receipt and app-scoped Feishu receipt, and the real Feishu Post contained pre-text, the uploaded image and post-text. The actual resource downloaded from the Feishu message is preserved as [feishu-real-image-C.png](evidence/feishu-real-image-C.png).
- Real partial-failure request `om_x100b6513b96924b8b2c08d7c59339df` reached run `run_51f9b90634fec55b` and produced one valid image plus one missing export. The real Feishu Post contained the valid image, `中间文字`, `（图片未能展示：图片来源不可用）`, and `结束`; only the valid ordinal received a provider receipt. The delivered valid resource is [feishu-partial-failure-valid-D.png](evidence/feishu-partial-failure-valid-D.png).
- For `/new`, request `om_x100b651c4d199888b481fd87a332f1f` entered the controlled 90-second wait and `/new` `om_x100b651c4d3ef0b8b489e8ec60bb3d2` followed about two seconds later. The old run was discarded, no reply-image manifest or late Bot image appeared after more than 95 seconds, and the only Bot response was `已停止当前操作，并已开始新会话。`. This is a real waiting-run cancellation; the integration suite covers the narrower upload-in-progress, admitted-publication and reset-failure interleavings.

## Broad regression (2026-09-10)

- After synchronizing bugfix-549 from latest main, its only merge conflict with feat-551 was the `message-pane.tsx` import block; both feature imports were retained and the two focused frontend files passed **19 tests**.
- CI-equivalent Python shards on the synchronized head: **1804 passed** (agent/PA, 19.66s) and **1842 passed** (remaining, 51.65s), no skips added. The later verifier-finding corrections have **46 focused tests** green; final full post-fix shards remain before PR.
- An intermediate PA-only run had one transient `FileNotFoundError` reading a user-global `lark-wiki/SKILL.md`; the unchanged isolated test passed, then both complete shards above passed. No global skill files or unrelated runtime behavior were changed.
- Frontend synchronized-head rerun: **708 passed** / 73 files, 28.59s, `npm run test -- --maxWorkers=2`. Production build passed during independent acceptance; audit critical threshold passed with 7 pre-existing low/moderate/high notices and no dependency changes.
- Ruff check, all-file format check and staged diff-check passed. Documentation integrity passed (240 maintained Markdown sources, 70 required routes).

## Current state

- The dedicated feat-551 IM/Gateway stack was stopped with `e2e-down.sh` after the fresh browser check, and its owned `feat551-e2e` tmux session was removed. The user-authorized feat-546 test services remain off. No production service was changed or deployed.
- Real Web IM and exclusive Feishu journeys are complete. Independent product acceptance passed Round 1 at `89986aa1a` with all 11 scenarios and zero issues; its Round 2 functional failure-classification check also passed.
- Independent verification closed the public/data classification, boundary-matrix and provider receipt-reentry findings, then correctly kept the pending/error prototype contract open because the committed 390px screenshots exposed mobile overflow. The one-line grid minimum-width correction is ready for real-product revalidation and replacement evidence.

## Remaining

Commit the mobile overflow correction, refresh the real 390px loading/error evidence, run targeted acceptance/verification closure, reconcile and verify the corrected delta, merge canonical specs, run final CI equivalents, archive the unit, create a ready PR, wait for CI green, and remove owned runtime artifacts. Code-review gate is omitted by explicit user override.
