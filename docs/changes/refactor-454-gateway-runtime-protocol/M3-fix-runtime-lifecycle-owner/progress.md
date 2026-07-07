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
- Commits: planning commit pending.
- Next: R1 red regressions.

## R1 — Red regressions for lifecycle owner and typed accepted receipt

- Context: pending.
- Decision: pending.
- Rationale: pending.
- Evidence:
  - Tests: pending.
  - Entry: pending.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: pending.
  - Visual/Interaction: N/A.
- Rollback: pending.
- Commits: pending.
- Next: R1.

## R2 — Move lifecycle owner to runtime_delivery and fix typed-store receipt

- Context: pending.
- Decision: pending.
- Rationale: pending.
- Evidence:
  - Tests: pending.
  - Entry: pending.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: pending.
  - Visual/Interaction: N/A.
- Rollback: pending.
- Commits: pending.
- Next: R2.

## R3 — Evidence and live isolated check

- Context: pending.
- Decision: pending.
- Rationale: pending.
- Evidence:
  - Tests: pending.
  - Entry: pending.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: pending.
  - Visual/Interaction: N/A.
- Rollback: pending.
- Commits: pending.
- Next: R3.
