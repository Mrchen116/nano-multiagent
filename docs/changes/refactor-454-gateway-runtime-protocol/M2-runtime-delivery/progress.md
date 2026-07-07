# refactor-454-M2 — Progress

## Baseline

- Context: M2 begins from `origin/unit/refactor-454` at `113b4332`, after M1 landed the IM/Gateway protocol boundary, `InboundEnvelope` runtime facts, and workspace local-wins resolver.
- Decision: Run the exact seven-file gate from the派发包 before writing red tests.
- Rationale: Runtime delivery touches live-critical Gateway/IM behavior; a green baseline is required before attributing any later failure to this milestone.
- Evidence:
  - Tests: `source /Users/czj/Repos/nano-multiagent/.venv/bin/activate && pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py` -> 106 passed, 2 warnings.
  - Entry: Existing unit/integration gate includes Gateway websocket API and FK-enforced heartbeat IM delivery paths; no long-running live stack started yet.
  - Frontend State Matrix: N/A.
  - Browser QA: N/A.
  - E2E/Regression: Existing regression suite above is the starting safety net.
  - Visual/Interaction: N/A.
- Rollback: N/A.
- Commits: planning commit pending.
- Next: R1 typed run delivery context and lifecycle.
