# feat-447-M13 — Progress

## R1 — Feishu native permission approval

- Context: Feishu-triggered runs already render tool permission cards inside the internal IM shadow conversation, but the original Feishu conversation has no approval surface. Users staying in Feishu see the agent stop without an actionable approval card.
- Decision: Add Feishu interactive-card approval as a second UI surface over the existing kernel permission broker. Gateway emits the same `permission_request` payload to IM and to the triggering Feishu adapter; Feishu card clicks call the same `kernel.submit_permission_decision` path and rely on its boolean first-wins result.
- Rationale: The permission state machine must remain inside the existing kernel broker. Feishu owns only card rendering, pending card validation, and best-effort card status updates. Runtime code does not use `lark-cli`; reviewer live validation still uses `lark-cli im +messages-send --as user` to create real inbound Feishu messages.
- Implementation:
  - Packaged Feishu channel code under `src/personal_assistant/channels/feishu/`, with old `feishu_adapter.py` / `feishu_client.py` kept as compatibility exports.
  - Added `FeishuClient.send_interactive_message()`, `update_interactive_message()`, and card action event parsing.
  - Added `FeishuPermissionApprovalSurface` for card construction, pending approval state, owner/chat/option/TTL validation, duplicate click handling, and resolved-card update.
  - Wired `_build_kernel_event_observer()` to mirror `permission_request` / `permission_resolved` to the external channel context when `trigger_source=feishu`.
  - Reused `_build_permission_response_handler()` for both IM and Feishu decisions; it now returns the kernel boolean accepted/already-resolved result.
- Evidence:
  - Tests: `pytest -q tests/unit/test_feishu_adapter.py tests/unit/test_feishu_adapter_permission_approval.py tests/unit/test_feishu_client.py tests/unit/test_feishu_client_interactive.py tests/unit/personal_assistant/test_permission_pipeline.py` -> 47 passed.
  - Tests: `pytest -q tests/unit/test_feishu_*.py` -> 99 passed.
  - Tests: `pytest -q tests/unit/personal_assistant/test_permission_response_handler.py tests/unit/test_permission_decision_loop.py tests/unit/test_feishu_adapter_permission_approval.py tests/unit/personal_assistant/test_permission_pipeline.py` -> 29 passed.
  - Tests: `pytest -q tests/unit/personal_assistant/test_permission_response_handler.py tests/unit/test_permission_decision_loop.py tests/unit/personal_assistant/test_permission_pipeline.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` -> 44 passed.
  - Tests: `pytest -m "not e2e"` -> 3286 passed, 1 skipped, 22 deselected.
  - Static: `python -m ruff check src/personal_assistant/channels/feishu src/personal_assistant/channels/feishu_adapter.py src/personal_assistant/channels/feishu_client.py src/personal_assistant/main.py tests/unit/test_feishu_adapter.py tests/unit/test_feishu_adapter_permission_approval.py tests/unit/test_feishu_client.py tests/unit/test_feishu_client_interactive.py tests/unit/personal_assistant/test_permission_pipeline.py tests/unit/personal_assistant/test_gateway_feishu_bot_open_id.py` -> passed.
  - Static: Feishu client/adapter approval test files remain under the 400-line contract limit.
  - Static: `git diff --check` -> passed.
- Entry: Unit tests cover the Gateway observer entry point and Feishu adapter card-action entry point. True Feishu/Lark live validation remains for reviewer: send a real Feishu message to the configured bot, trigger a tool permission request, verify Feishu and IM show the same `request_id`, click Feishu card, then verify the run continues.
- Rollback: Revert this milestone to restore IM-only approval. Runtime impact would be Feishu users needing to switch to internal IM for tool approval.
- Next: Run reviewer live validation with the worktree Gateway and the gateway config app id/bot identity.
