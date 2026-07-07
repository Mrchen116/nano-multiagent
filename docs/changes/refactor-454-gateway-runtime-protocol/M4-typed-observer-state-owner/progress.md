# refactor-454-M4 — Progress

## Baseline

- Context: M4 starts from `origin/unit/refactor-454` at `6e5e409c`, after M3 closed relay lifecycle ownership and typed-store fresh accepted receipt but verifier round-2 still found observer typed-store ownership open.
- Decision: Re-run the full M4/M3 gate before editing, then add typed-store behavioral regressions before changing observer/context.
- Rationale: The blocker is an architecture/behavior state-owner gap hidden behind green compatibility tests. A green baseline prevents mixing pre-existing failures with M4 changes, and red behavior tests prove the typed state itself is currently stale.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/contract/test_personal_assistant_main_contract.py` -> 117 passed, 2 warnings.
  - Entry: Gate covers Gateway lifecycle, observer side effects, heartbeat/cron, IM websocket API and main contract; no services started yet.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: Existing unit/integration/contract suite above is the starting safety net.
  - Visual/Interaction: N/A.
- Rollback: N/A.
- Commits: plan=<pending>.
- Next: R1 red regressions.
