# Verification Report: refactor-454

## Summary

Mode: full
Delta range: N/A
Focus issues: N/A
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 15/16 verified |
| Correctness | Covered with caveats |
| Coherence | Has critical deviation |

1 critical issue(s) found. Fix before PR.

## Completeness

- Tasks: M1 protocol-boundary exit criteria are verified by code and tests. M2 is not fully complete: the milestone goal says run context, relay lifecycle, kernel event delivery, background/control replies, and session-event notification must move from `main.py` into `personal_assistant.gateway.runtime_delivery`, but relay lifecycle remains implemented inside `main.py`.
- Spec coverage: Web IM relay/dedup, Gateway/IM reconnect, workspace local-wins, runtime/tool/permission/background delivery, and no-new-entry behavior have automated coverage and/or worker live-critical evidence. Feishu/Lark true-platform journeys are explicitly not verified because this isolated stack has no verified platform credentials.
- Verification commands run in this worktree:
  - `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py` -> 112 passed, 2 warnings.
  - `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/unit/personal_assistant/test_gateway_im_config_sync.py tests/unit/personal_assistant/test_gateway_reconcile_on_connect.py tests/unit/personal_assistant/test_gateway_upstream_reporter.py tests/im_service/integration/test_gateway_websocket_api.py tests/im_service/contract/test_gateway_protocol_contract.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py` -> 75 passed, 2 warnings.
  - `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/contract/test_cli_http_only_contract.py tests/contract/test_core_no_platform_imports.py tests/contract/test_multi_product_architecture.py tests/contract/test_personal_assistant_package_contract.py tests/contract/test_no_legacy_wiring_imports.py tests/contract/test_personal_assistant_main_contract.py` -> 17 passed, 2 warnings.
  - `/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m "not e2e"` -> 3325 passed, 2 skipped, 22 deselected, 16 warnings.

## Correctness

| Requirement / Scenario | 实现位置 | 测试覆盖 | 状态 |
|---|---|---|---|
| Web IM direct/group relay, duplicate relay, delivery receipt | `src/personal_assistant/channels/web_relay_adapter.py:299`, `src/personal_assistant/gateway/runtime_protocol.py:25`, `src/IM/ws/gateway_protocol.py:61`, `src/personal_assistant/main.py:3640` | `test_gateway_web_relay_adapter.py`, `test_gateway_relay_lifecycle.py`, `test_gateway_websocket_api.py` | covered |
| Gateway/IM connection, reconnect, node state | `src/personal_assistant/ws/im_connection.py`, `src/IM/ws/gateway_handler.py`, `src/personal_assistant/main.py:2766` | `test_gateway_im_resilience.py`, `test_gateway_im_resilience_critical_path.py` worker evidence | covered |
| workspace_root local-wins | `src/personal_assistant/gateway/workspace_authority.py:13`, `src/personal_assistant/main.py:351`, `src/personal_assistant/main.py:601` | `test_gateway_im_config_sync.py`, `test_gateway_reconcile_on_connect.py` | covered |
| Runtime state, tool/permission state, background/control/session-event delivery | `src/personal_assistant/gateway/runtime_delivery/observer.py:112`, `src/personal_assistant/gateway/runtime_delivery/background.py:24` | M2 seven-file gate, `test_external_visible_delivery.py`, `test_heartbeat_im_delivery.py`, `test_cron_delivery_chain.py` | covered |
| Feishu private/group/shadow and IM-offline main path | `src/personal_assistant/channels/feishu/adapter.py`, `src/personal_assistant/gateway/runtime_delivery/observer.py:207`, `src/personal_assistant/gateway/runtime_delivery/background.py:97` | unit/integration coverage plus worker caveat; no true Feishu/Lark platform run | warning |
| No new user entry or visible flow change | Diff touches backend Gateway/IM protocol/runtime modules only; frontend files unchanged | `pytest -m "not e2e"` and package contract tests | covered |

The tracked heartbeat active-bubble e2e xfail #126 was not counted as green evidence. It remains a known pre-existing product issue, and M2 progress correctly records it as xfailed rather than passed.

## Coherence

| design 决策 | 遵守? | 代码证据 |
|---|---|---|
| Decision 1: IM/Gateway package-local protocol adapters, no shared business package | Yes | `src/IM/ws/gateway_protocol.py:1`, `src/personal_assistant/gateway/runtime_protocol.py:1` |
| Decision 2: Gateway `runtime_delivery` owns run context, relay lifecycle, kernel event translation | No | `src/personal_assistant/main.py:3640`, `src/personal_assistant/main.py:3770`, `src/personal_assistant/gateway/runtime_delivery/observer.py:149` |
| Decision 3: typed delivery target distinguishes shadow / owner_direct / none, local workspace wins | Partly | `src/personal_assistant/gateway/runtime_delivery/context.py:25`, `src/personal_assistant/gateway/workspace_authority.py:13`; observer still consumes `legacy_contexts` |
| Decision 4: IM `EventBridge` remains runtime event owner | Yes | `src/IM/ws/gateway_handler.py` consumes typed protocol and continues delegating to existing IM services |
| Decision 5: no user-visible protocol/entry change or forced state clearing | Yes, based on tests | Full non-e2e suite passed; no DB schema migration or frontend entry change found |
| Decision 6: protocol contract + regressions + live caveats | Mostly | Contract/unit/integration tests pass; Feishu true-platform remains unverified by design caveat |

Architecture boundaries are intact: selected product/import contract tests passed, and no new `IM` -> `agent` or cross-product imports were introduced.

## Issues

### CRITICAL

- `src/personal_assistant/main.py:3640` still implements `_build_relay_lifecycle_callback()` with accepted/running/completed/failed delivery semantics, context seed/cleanup, Feishu started ack, `node.report`, and `node.delivery_receipt` emission. This violates M2's stated goal and design decision 2 that relay lifecycle belongs in `personal_assistant.gateway.runtime_delivery` and `main.py` should be wiring only. The gap is not just file placement: `runtime_delivery.observer.build_kernel_event_observer()` immediately downgrades `RunDeliveryContextStore` to `legacy_contexts` at `src/personal_assistant/gateway/runtime_delivery/observer.py:149`, so typed `RunDeliveryContext` is not the actual owner read by kernel event delivery.
  - Fix: move `_build_relay_lifecycle_callback()`, `_protocol_conversation_id()`, and external-start ack handling into a new `src/personal_assistant/gateway/runtime_delivery/lifecycle.py` or equivalent. Let lifecycle and observer read/update typed `RunDeliveryContextStore` directly; keep any legacy dict adapter only at explicitly still-dict-shaped heartbeat/cron helper boundaries. Add tests that fail if `main.py` defines relay lifecycle behavior or if observer converts a typed store to `legacy_contexts` at entry.

### WARNING

- Feishu/Lark true-platform journeys required by motivation/design are not verified in this round. M2 progress correctly says no fake inbound was used, but the coverage remains short of the user-visible Feishu private chat, group @Bot, unmentioned group shadow context, IM-offline Feishu main path, and native approval card scenarios in `docs/specs/gateway/spec.md:656`, `docs/specs/gateway/spec.md:769`, `docs/specs/gateway/spec.md:791`, and `docs/specs/gateway/spec.md:844`.
  - Fix: rerun with verified Feishu/Lark channel credentials and record true platform evidence, or explicitly keep these scenarios as unverified release caveats. Do not replace this with synthetic `InboundMessage` tests.

### SUGGESTION

- None.
