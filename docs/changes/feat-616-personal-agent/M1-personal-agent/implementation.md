# M1 implementation and live evidence

Status: implementation candidate; independent gates and delivery are pending. No production deployment.

## Implemented paths

- Canonical PA identity and owner DM, current owner ACL history without a day limit, source observation with independent cursors, private Work and source exclusions.
- Unified PA on an isolated official DSH host, controlled adapters, independent no-tools semantic review, frozen IM/network/task/Channels effects and real receipts.
- Existing top navigation and chat layout, fixed named PA entry, one-step creation, goals, decisions, drafts, source navigation, visible delegated identity and incident controls.
- Durable native followup, natural-language owner preferences, private task completion, source retirement and existing ordinary Agent routing.

## Reproducible evidence so far

2026-10-19, local isolated worktree (Node 25.8.2, pnpm 11.7.0):

- `pnpm test`: 97 files / 380 tests passed before the final completion/incident fixes; subsequent affected suites are recorded below and the final delivery must run the current full gate.
- `python -m pytest -m 'not e2e' -q`: 62 passed, 31 deselected.
- `scripts/docs-check`: 273 maintained Markdown sources / 64 required routes passed.
- Frontend worker: 97 files / 893 tests passed; later PA/stream targeted tests cover the final UI changes.
- Real DeepSeek via local model proxy, isolated IM and Node: owner created 小航 in the real browser with a first goal; PA retrieved a synthetic 2024 conversation, quoted the agreement and kept the original chat unread.
- Owner granted ongoing coordination in a private message. PA sent the time question into the existing two-human DM, with server-generated PA delegation identity. Receiver DTO contains that identity; DM membership remains the two humans.
- Private synthetic medical canary was present in the owner's request and PA context, absent from messages delivered to the peer. This is sample evidence, not a zero-leak guarantee.
- PA scheduled an actual native followup; after the synthetic peer replied, it observed the reply without forwarding or @mention, confirmed the agreed time and notified the owner.
- Explicit probing/impersonation fixture was refused and an incident was recorded. The initial fixed peer notice was incorrectly denied by the reviewer; the policy and final live rerun must verify this correction.

## Failures found and corrected in live testing

- Host PA RPC replies were not correlated by Channels, causing timeouts. Regression reproduced the failure on real WebSockets; corrected response matching passes.
- DeepSeek supports high/max but the reviewer forced low. Reviewer effort now follows declared capabilities; output budget includes its reasoning requirements.
- Scope reviewer failure must retry before admission, not ask the owner to approve an already authorized message.
- Completed-only WebSocket events did not create new message bubbles. Real-message creation now publishes after commit, including final delegation metadata.
- Completion must update the original private task and cancel its followup, not merely leave an assistance row saying completed beside an unfinished task.

## Explicit remaining verification / boundaries

Final independent product acceptance, code review, verification, full final CI, canonical-spec merge and archive remain pending. The worktree and isolated runtime contain only test identities and synthetic messages.

The current adapters reject Channels groups without a verified audience, external binary attachments without a semantic content adapter, and uncontrolled executable tools/plugins in PA; ordinary Agents retain their original capabilities. Same-owner node relocation/credential-epoch recovery, rename runtime synchronization, all revocation event sources, and per-PA availability require specific final verification against the design rather than assuming a passing unit suite proves them.

Raw logs, fixture credentials, screenshots and recordings stay outside tracked documentation. Final evidence will link only shareable artifacts and exact tested versions.

## Independent review corrections

Review of `cf1befff9` independently reproduced source-policy bypass through direct relays, broken device epoch recovery, and PA recovery preventing ordinary global work. The next candidate corrects all three:

- Every personal input now revalidates current IM source/contact authority before review or storage, including queued direct relays. Channels inputs first obtain a persisted IM source and use that identity for checks.
- Same-device credential recovery rotates the trusted PA marker and retires old permits; local partition data moves to the new epoch before startup. An explicit same-owner restore operation prepares the same PA on another computer, preserves canonical DM/goals, and fences the old node before committing the new runtime receipt. It does not copy local private history.
- Recovery failures are isolated per Agent. PA host availability is reported separately from node health. Retiring a context recreates still-authorized goal timers; completed/paused/inaccessible goals do not regain timers.

The corrected live privacy probe produced both an actual private owner notice and a PA-labelled fixed peer refusal, with no canary disclosure. The private goal completion now updates its real task to done and cancels its native followup. A separate real public search completed without an additional owner approval. Final acceptance remains pending; these observations are not a claim of exhaustive leakage prevention.
