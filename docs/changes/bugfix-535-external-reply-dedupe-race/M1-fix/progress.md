# M1-fix Progress

## Scope and decision

- Scope: only the process-local race between observer-final mirror and terminal-final fallback in `OutboundRouter.send_text()`.
- Decision: atomically reserve every derived dedupe key before provider I/O. A competing call is suppressed if any physical or final semantic key is completed or reserved. On provider exception, release all reserved keys and re-raise; on success, atomically move all keys into the existing bounded completed-key `OrderedDict`.
- Rationale: final contexts use different physical keys but share a derived `run_id:final_text:<text>` semantic key. Reserving the whole key set prevents either caller from crossing provider I/O while preserving fallback when observer delivery fails.
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
