# refactor-454-M3 — Progress

## Baseline

- Context: M3 starts from `origin/unit/refactor-454` at `2b03986c`, after M1/M2 were merged and round-1 verifier/code review found relay lifecycle ownership still in `main.py` plus a typed-store accepted receipt regression.
- Decision: Run the exact M3 gate before editing, then split work into red regressions, implementation, and live evidence.
- Rationale: The bug is in production typed `RunDeliveryContextStore` wiring; a green baseline is required before attributing new failures to M3.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/contract/test_personal_assistant_main_contract.py` -> 114 passed, 2 warnings.
  - Entry: Existing unit/integration/contract gate includes Gateway websocket API plus relay lifecycle reports/receipts; no long-running live stack started yet.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: Existing regression suite above is the starting safety net.
  - Visual/Interaction: N/A.
- Rollback: N/A.
- Commits: plan=`8e232299`.
- Next: R1 red regressions.

## R1 — Red regressions for lifecycle owner and typed accepted receipt

- Context: Round-1 verifier/code review found two behavior/architecture gaps that existing tests missed: production typed `RunDeliveryContextStore` fresh accepted relay skipped the accepted receipt, and `main.py` still owned relay lifecycle delivery semantics. M3 also needs a guard against observer entry immediately replacing the typed store with the legacy dict view.
- Decision: Added regressions in the existing lifecycle and main contract files: typed-store fresh accepted relay must both seed context and send `node.delivery_receipt(delivery_status="sent")`; `main.py` must not define `_build_relay_lifecycle_callback`; observer source must not contain the entry assignment `run_context_store = run_context_store.legacy_contexts`.
- Rationale: These are the exact production path and ownership regressions reported by verifier/reviewer. The tests fail on current code before implementation and stay close to existing lifecycle/contract coverage instead of adding a milestone-specific test file.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/contract/test_personal_assistant_main_contract.py` -> expected red: 3 failed, 25 passed, 2 warnings. Failures were `test_typed_store_fresh_relay_accepted_still_sends_sent_receipt`, `test_personal_assistant_main_does_not_define_relay_lifecycle_callback`, and `test_runtime_delivery_observer_keeps_typed_store_owner_at_entry`.
  - Entry: N/A for red tests; this step only proves the missing behavior/architecture guard.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: Permanent regressions added in `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` and `tests/contract/test_personal_assistant_main_contract.py`.
  - Visual/Interaction: N/A.
- Rollback: Revert `1654a2dd`.
- Commits: C1=`1654a2dd`.
- Next: R2 implementation.

## R2 — Move lifecycle owner to runtime_delivery and fix typed-store receipt

- Context: `main.py` still contained `_build_relay_lifecycle_callback()`, `_protocol_conversation_id()`, and Feishu processing-start ack helper. The typed-store accepted branch called `seed_from_lifecycle(...)` then returned before relay receipt/report code ran. `observer.py` also immediately rebound typed stores to `legacy_contexts`, making typed store a caller-side adapter rather than the production owner.
- Decision: Added `src/personal_assistant/gateway/runtime_delivery/lifecycle.py` as relay lifecycle owner. `main.py` now imports `build_relay_lifecycle_callback` as a wiring alias and no longer defines lifecycle semantics. The new lifecycle builder seeds typed/legacy context and then continues to relay receipt/report handling, so fresh accepted relay sends `delivery_status=sent`. Observer now creates an explicit `context_map` compatibility view and keeps the original typed-store parameter as the owner-facing input.
- Rationale: This closes the actual ownership defect rather than patching one branch in `main.py`. Keeping the legacy dict as a named compatibility view avoids rewriting the whole observer while removing the unconditional entry downgrade called out by verifier.
- Evidence:
  - Tests: `ruff check src/personal_assistant/main.py src/personal_assistant/gateway/runtime_delivery/lifecycle.py src/personal_assistant/gateway/runtime_delivery/observer.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/contract/test_personal_assistant_main_contract.py` -> All checks passed. `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/contract/test_personal_assistant_main_contract.py` -> 28 passed, 2 warnings. Full M3 gate `pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/contract/test_personal_assistant_main_contract.py` -> 117 passed, 2 warnings.
  - Entry: Unit/integration gate covers the Gateway lifecycle and IM websocket API paths; live stack evidence is recorded in R3.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: `test_typed_store_fresh_relay_accepted_still_sends_sent_receipt` guards the production typed-store accepted receipt; main contract guards lifecycle ownership.
  - Visual/Interaction: N/A.
- Rollback: Revert `e91198d4` after reverting red-test commit `1654a2dd` if needed.
- Commits: C2=`e91198d4`.
- Next: R3 live isolated evidence.

## R3 — Evidence and live isolated check

- Context: M3 is a runtime delivery refactor/fix; automated tests must be complemented by a true Gateway + IM entry check for the user-visible Web IM direct relay path and relay accepted/completed closeout.
- Decision: Started a worktree-local isolated stack with `scripts/e2e-up.sh --wt <mktemp> --main-config ~/.nano-assistant/config.yaml` using the repo `.venv` first on `PATH`. Drove the same HTTP entry used by Web IM: login as `nano`, wait for the worktree Gateway node online, create a direct conversation with `default-agent`, send a user message, poll REST messages and the isolated IM SQLite relay/event rows, then clean with `scripts/e2e-down.sh` and remove the temp dir.
- Rationale: This verifies the fixed lifecycle path through real processes and the IM relay status tables instead of relying only on mocked unit callbacks. Feishu/Lark was not faked because the available config has only `web_relay`.
- Evidence:
  - Tests: Full M3 gate already recorded in R2: 117 passed, 2 warnings.
  - Entry: Live isolated check passed. Evidence JSON: `agent_id=default-agent`, `agent_reply_content=M3LIVE1783402335`, `agent_reply_status=completed`, `relay_status=completed`, `relay_receipt_status=completed`, `relay_receipt_detail=M3LIVE1783402335`, `event_types=[message.sent, relay.accepted, relay.processing, relay.report, relay.completed, message.delivered]`, `relay_task_id=356ca32a6647420ba30a83a107bb3bfa`, `user_message_id=2586bbd39af64f0680ca6e4ab4e3ec19`.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A; no frontend client code changed. The live check used the Web IM backend HTTP entrypoint and observed REST/DB user-visible status closeout.
  - E2E/Regression: One-shot live evidence only; no new permanent e2e file added.
  - Visual/Interaction: N/A.
- Rollback: Revert `e91198d4` and `1654a2dd`; docs evidence commit can be reverted independently.
- Commits: C3=docs evidence commit; final report records the commit hash.
- Next: Merge milestone branch into `unit/refactor-454`.

## Caveats

- Feishu/Lark true-platform journeys were not run. Current `~/.nano-assistant/config.yaml` channel list is only `web_relay`, so there is no credentialed Feishu/Lark channel in this isolated run. No fake inbound was used.
