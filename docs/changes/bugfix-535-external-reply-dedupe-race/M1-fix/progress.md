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
- Rollback: revert this unit commit after creation.

## R3 — Dedicated Feishu real-entry validation

- Attempted: verified the documented private profile before any live action with `lark-cli --profile <dedicated non-default profile> auth status --json --verify`; output verified the dedicated test App, Bot, and user identities. Read and prepared the documented `./scripts/e2e-up.sh --wt /Users/czj/Repos/nano-multiagent/.worktrees/unit-bugfix-535 --feishu` followed by `./scripts/e2e-feishu-probe.py --wt ...` flow.
- Outcome: BLOCKED. The execution environment denied permission to launch the isolated Feishu E2E environment because it launches network-facing services. No E2E services were started, no Feishu probe was sent, and therefore no actual final reply could be verified.
- Required follow-up: grant permission to run the documented isolated `e2e-up.sh --feishu` / probe flow; then exercise the actual final-reply chain and always run `e2e-down.sh --wt /Users/czj/Repos/nano-multiagent/.worktrees/unit-bugfix-535` to clean up.
- Commit: pending.
