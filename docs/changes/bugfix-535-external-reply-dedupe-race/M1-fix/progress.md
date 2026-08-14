# M1-fix Progress

## Scope and decision

- Scope: only the process-local race between observer-final mirror and terminal-final fallback in `OutboundRouter.send_text()`.
- Decision: atomically reserve every derived dedupe key before provider I/O. A competing call is suppressed only for completed keys; overlapping in-flight keys make it wait for the owner result. Owner success atomically completes the keys; owner failure releases them so the waiter can reserve and retry.
- Rationale: final contexts use different physical keys but share a derived `run_id:final_text:<text>` semantic key. Reservation prevents duplicate provider I/O, while condition notification preserves terminal fallback if observer delivery fails after the fallback has already arrived.
- Non-dedupe sends use the same direct provider-send behavior: an empty key set takes no reservation/cache mutation.

## R1 — Deterministic regression protection

- Context: sequential cross-path coverage did not hold one provider send open, so both worker threads could pass baseline check-send-remember.
- Decision: add a blocking adapter test in the existing router semantic-owner file. It starts an observer-like final send, waits until its adapter send is in flight, then starts a terminal-like final send with an intersecting semantic key.
- Evidence:
  - RED: `pytest -q tests/unit/personal_assistant/test_gateway_web_relay_adapter.py` → `1 failed, 10 passed`; the terminal send did not finish while the mirror send was held, demonstrating that baseline entered a second provider send.
  - Regression: `test_outbound_router_dedupes_concurrent_external_final_reply_paths` asserts one physical send and one non-`None` result; `test_outbound_router_releases_dedupe_reservation_after_send_failure` protects retry after a raised provider send.
- Rollback: revert this unit commit after creation.

## R2 — Atomic reservation and rollback

- Context: `_sent_dedupe_keys` was only updated after `channel.send()` returned.
- Decision: add a `Lock` plus separate in-flight reservation set. Check-and-reserve is atomic across the complete multi-key set; success commits reservations to the pre-existing bounded completed cache; exceptions release reservations.
- Evidence:
  - `pytest -q tests/unit/personal_assistant/test_gateway_web_relay_adapter.py` → `12 passed in 0.13s`.
  - `pytest -q tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` → `49 passed in 2.98s`.
  - `ruff check src/personal_assistant/gateway/outbound_router.py tests/unit/personal_assistant/test_gateway_web_relay_adapter.py` → `All checks passed!`.
  - `ruff format --check src/personal_assistant/gateway/outbound_router.py tests/unit/personal_assistant/test_gateway_web_relay_adapter.py` → `2 files already formatted`.
  - Revalidated after merging `origin/main@bf8b3cb10` into the unit at `adffefdb4`: router owner file `12 passed`, nearby external-visible/lifecycle suites `50 passed`, and both Ruff commands passed.
- Rollback: revert this unit commit after creation.

## R3 — Dedicated Feishu real-entry validation

- Context: the previous attempt was blocked before service launch, so unit tests could not prove that a real Feishu user saw only one final message. This rerun used the exact milestone worktree on unit baseline `adffefdb4` and the repository-owned `feishu:e2e` profile only.
- Decision: verify the private env is mode `0600`, the named CLI profile is non-default, and its App/Bot/user identities match before launch; then run `e2e-up.sh --feishu`, the repository probe, and a P2P history query against the same test Bot.
- Evidence:
  - Entry: `./scripts/e2e-feishu-probe.py --wt /Users/czj/Repos/nano-multiagent/.worktrees/bugfix-535-M1` passed for real nonce `nano-e2e-feishu-probe-bb1084b16753b3bb`. The isolated Gateway wrote one Feishu user message and completed the actual Agent run with one intermediate and one final assistant bubble in its shadow conversation.
  - User-visible result: the real Feishu P2P history contained the one probe user message `om_x100b68daac3d30b4c1c019dbbdc738b` and two Bot messages for the run window: one intermediate message plus exactly one message containing the unique final suffix `bb1084b16753b3bb`. The sole matching final was `om_x100b68daa8dc98a4c433c1bcb127682` at position `341`; the isolated IM shadow independently contained exactly one agent message with that suffix. No duplicate final appeared.
  - Isolation: the source was `config/e2e/gateway.yaml`; `--feishu` enabled only `feishu:e2e` in the worktree copy. Preflight proved `private_env_mode=0600`, `dedicated_profile_non_default=true`, and matching verified test App/Bot/user identities. The IM used high port `65315`; default/production Bot credentials and port `8011` were not used.
  - Cleanup: `e2e-down.sh --wt /Users/czj/Repos/nano-multiagent/.worktrees/bugfix-535-M1` stopped IM PID `28876` and Gateway PID `29038`; both PIDs were gone, TCP `65315` had no listener, the dedicated listener lock and tmux session were absent, and `.e2e-ports.env`, PID files, JWT secret, generated Gateway config, channel credential key/manifest, config receipts, and Feishu LLM trace were absent.
- Rollback: N/A; R3 changed no product code. Revert the milestone closeout docs commit to remove this evidence record.
- Commits: product fix `40ed2199c`; blocked-attempt evidence `66235198f`; this roadpoint is evidence-only.
- Next: milestone complete; run final gates, integrate into `unit/bugfix-535`, push, and remove the milestone worktree/branch.

## R4 — Review fix: preserve fallback after concurrent owner failure

- Context: review at `pre_fix_head=125fd6b20` confirmed a blocking final-loss order. Observer reserved the shared semantic key and blocked in provider I/O; terminal fallback saw the reservation and returned `None`; observer then failed and released the key, but no retry remained. The existing failure test covered only a later explicit retry.
- Decision: replace the reservation `Lock` with a `Condition`. A caller that intersects an in-flight key waits without holding provider I/O; `_remember_dedupe_keys()` and `_release_dedupe_keys()` publish success/failure with `notify_all()`. The waiter then either observes completed state and suppresses, or atomically takes the released reservation and performs the fallback send. Observer and terminal production callers remain on their existing `asyncio.to_thread` seams.
- Rationale: the Router owns both the shared physical/semantic key state and provider-send outcome, so it is the narrowest layer that can distinguish “duplicate already delivered” from “owner still may fail.” Returning early at the reservation boundary discarded that distinction.
- Process: omitted `change-impl-worker §3` because this review finding is self-contained and the behavior change is one revertible commit limited to the Router plus its existing semantic-owner test file.
- Evidence:
  - Reproduction before RED: deterministic two-thread probe returned `fallback_finished_before_owner_outcome=True`, `terminal_result_before_owner_outcome=[None]`, `observer_error=RuntimeError`, `provider_calls=1`, and `terminal_sent=False`.
  - RED: `pytest -q tests/unit/personal_assistant/test_gateway_web_relay_adapter.py -k 'dedupes_concurrent_external_final_reply_paths or fallback_sends_after_inflight_final_send_fails'` → `2 failed, 11 deselected`; both failures showed terminal had already exited while owner outcome remained blocked.
  - Tests: owner suite `13 passed`; nearby `test_external_visible_delivery.py` + `test_gateway_relay_lifecycle.py` `50 passed`; Ruff check and format passed.
  - Entry: dedicated `feishu:e2e` probe `nano-e2e-feishu-probe-41bad4e930bc0528` entered the isolated Gateway and completed an Agent run. Real P2P history contained one probe user message and exactly one Bot message with final suffix `41bad4e930bc0528`; after an 8-second quiet window the count remained one. Final message id `om_x100b68c465beeca4dd1b42239cb80a5`, position `344`; isolated IM shadow also contained exactly one matching final.
  - Isolation: private env mode `0600`, non-default profile, and matching verified test App/Bot/user identities were checked before launch. The source was `config/e2e/gateway.yaml`, and only its worktree copy enabled `feishu:e2e`; production/default Bot credentials and port `8011` were not used.
  - Cleanup: `e2e-down.sh` stopped IM PID `51998` and Gateway PID `52082`; TCP `55805`, the dedicated listener lock, tmux session, PID files, JWT secret, generated Gateway config, channel credentials/manifest, config receipts, and Feishu LLM trace were absent afterward.
- Rollback: revert `ccd5feb31`.
- Commits: `ccd5feb31`.
- Next: run final docs/code gates, integrate into `unit/bugfix-535`, push, and remove the milestone worktree/branch.
- Promotion Candidates: none.
