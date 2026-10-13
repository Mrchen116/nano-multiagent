# Code review: bugfix-585

- Review mode: `full`.
- Reviewed snapshot: `6bb37a069` → `48287332f5979e0c7aa5fa736aa67d0a2b0fcd4e`.
- Independent reviewer: `/root/static_review`; did not implement the change.
- Scope: complete implementation/test/dependency diff, current contracts, approved design, delta specs, actual Node/IM/Channels/frontend callers.

```json
[]
```

No confirmed or plausible code defect remains in the reviewed diff. Heartbeat expiry uses recoverable 1012 without changing authority; real account suspension and device replacement retain terminal 1008 behavior. Current-connection fencing prevents late close callbacks from taking a replacement offline. Offline persistence precedes socket close, online registration clears last_error, and owner-scoped node/Agent events reach the existing cache consumers. Presence-only updates preserve Agent detail drafts.

Channels retains fresh credentials/registration, bounded exponential backoff and delivery uncertainty semantics. The added diagnostic sink uses local categories/whitelists and redacts unknown close reasons; callback failure cannot block cleanup/reconnect. Node writes the structured events to its existing stderr/gateway.log sink. No DSH imports, execution loop, runtime cross-package dependency or offline-submission mechanism was added. The IM dependency on Channels is test-only and imports the public package entrypoint.

Validation reused from the same product tree: focused backend 12 and frontend 13 tests; full backend 59 files/167 tests; frontend 87 files/826 tests; backend/frontend build and typecheck; Python architecture/helper 54 tests; Ruff and documentation checks. The reviewer independently checked the full diff with `git diff --check 6bb37a069..48287332f` (pass) and inspected the observable-seam assertions and their source wiring. No redundant full-suite rerun was needed. Product/browser/LLM acceptance belongs to the separate reviewer; these tests do not substitute for it.

The pre-existing service-lifecycle replay wording and the ownership of the recovery delta are document-reconciliation matters recorded in `verification.md`, not defects introduced by this implementation diff.

## Patch review: shutdown ordering

- Review mode: `patch`; frozen range `48287332f..684122882e410c870e37595b5b3d00e76bb8da62`.
- Retained: all full-review source/caller/dependency conclusions outside this two-file patch.

```json
[]
```

The Gateway preClose hook now registers before @fastify/websocket, so its 1001/server_shutdown close is sent before the plugin's default client.close(). The actual installed plugin's preClose registration/default close path was inspected. SIGTERM/SIGINT already route through app.close() in IM main.ts. Database teardown stays onClose, after connection cleanup. The new regression invokes real app.close() and asserts the close facts observed by the Relay diagnostic callback, which protects the plugin-order seam rather than merely calling Gateway.shutdown directly. Reused caller evidence: IM+Channels 13 tests passed, build/typecheck passed; red reproduction before the patch. Independent patch diff check passed. No additional issue or widened implementation scope was found.

## Patch review: resumed browser presence

- Review mode: `patch`; frozen range `684122882..8e453ab963fb93469a2a8933f0f320d13935349d`.
- Retained: full review and shutdown patch conclusions outside this two-file patch.

```json
[]
```

Gateway.replay now emits current node/non-stale Agent presence only to the resuming authenticated browser, after historical replay, without inserting chat events or altering cursor semantics. Queries restrict both node and Agent ownership and join matching node owner; no cross-owner presence is sent. Replay is synchronous, so no concurrent callback can slip between its snapshot and ready state. Existing frontend stream accepts presence without event_id and does not deduplicate it against the chat cursor; Nodes/Chat/Agent detail already consume these event types. The deterministic real-socket regression registers while the owner browser is open but not resumed, observes both current node/Agent state after resume and proves outsider isolation. Existing tests were adapted to account for initial offline snapshots while retaining their timeout/replacement assertions. Reused final evidence on `8e453ab96`: focused IM+Channels 14 tests; build/typecheck; full backend 59 files/169 tests (`/tmp/nano-bugfix585-resume-backend.log`). Independent patch diff check passed. Gate 2 R5 approved the matching design/IM delta. No issue survives this patch review.

## Final integration retention

- validated_at: `8e453ab963fb93469a2a8933f0f320d13935349d` (latest executed scope; earlier unaffected evidence retained as documented above).
- executed_base / effective_base: `6bb37a06925c20bb5714f6986f94e92f2d3f78d5`. Final fetch found no main increment.
- effective_through: final PR head, whose product source/test tree is unchanged from validated_at. Only reviewed delta-to-canonical merge, report completion and whole-unit archive follow; the PR records the exact final SHA.
- No gate invalidation from those documentation-only operations; code, product and corrected-delta conclusions retained.
