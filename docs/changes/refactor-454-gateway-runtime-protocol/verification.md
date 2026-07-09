# Verification Report: refactor-454

> Current status after independent Round 4 (`ed6e0de8` inspected): targeted
> closure passes for the previously open runtime-delivery owner blockers. Earlier
> failing sections are retained as history; see "Round 4 - Independent Targeted
> Closure Verification" at the end.

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

# Round 2 - Targeted Closure Verification

## Verification Report: refactor-454

### Summary

Mode: targeted-closure
Delta range: `2b03986c..30b7d855148712f0b25c727473b09c16ce2aa042`
Focus issues: round-1 relay lifecycle owner CRITICAL; typed-store fresh accepted receipt blocker; observer typed-store boundary; M3 gate/live Web IM direct relay evidence
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | 3/4 focus closures verified |
| Correctness | 3/4 focus closures verified |
| Coherence | 1 critical deviation remains |

1 critical issue found. Fix before PR.

Full verification is not the useful next step while this blocker remains open. After fixing the observer/context boundary, another targeted closure round should be sufficient unless the fix expands beyond `runtime_delivery/{context,lifecycle,observer}.py` and `main.py` wiring.

## Focus Closure Results

| Focus item | Verdict | Evidence |
|---|---|---|
| Round-1 CRITICAL: relay lifecycle owner moved out of `main.py` | closed for lifecycle ownership | `src/personal_assistant/main.py:67` imports `build_relay_lifecycle_callback` from `runtime_delivery.lifecycle`; `src/personal_assistant/main.py:2847` only wires it; `src/personal_assistant/gateway/runtime_delivery/lifecycle.py:21` owns the callback and `lifecycle.py:31` starts accepted/completed/failed/cancelled handling. `main.py` no longer defines `def _build_relay_lifecycle_callback(`. |
| Code-review blocker: typed store fresh accepted path still sends `sent` receipt | closed | `src/personal_assistant/gateway/runtime_delivery/lifecycle.py:37` seeds context, then continues to `lifecycle.py:58` and sends `node.delivery_receipt` with `delivery_status="sent"` at `lifecycle.py:59-64`; there is no early return after `RunDeliveryContextStore.seed_from_lifecycle()`. Regression: `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py:204`. |
| Observer typed-store boundary | still open | `src/personal_assistant/gateway/runtime_delivery/observer.py:18-23` converts `RunDeliveryContextStore` to `legacy_contexts`, `observer.py:156` captures that map at builder entry, and runtime event reads/writes use `context_map` (`observer.py:303`, `observer.py:384-385`, `observer.py:482-489`, `observer.py:658-664`). The typed `RunDeliveryContext` has no backfilled `message_id`/`kernel_message_id` fields (`context.py:57-70`), so kernel event delivery is still owned by the mutable legacy dict view. |
| M3 gate and live Web IM direct relay evidence | sufficient with caveat | I reran the M3 gate in the verifier worktree: 117 passed, 2 warnings. I also reran `ruff check` on touched files: all checks passed. M3 progress records a true worktree-local IM + Gateway direct relay run with completed agent reply, completed relay status/receipt, and relay event rows (`M3-fix-runtime-lifecycle-owner/progress.md:53-60`). Feishu/Lark remains explicitly unverified because no credentialed channel exists and no fake inbound was used (`progress.md:67-69`). |

Commands run in verifier worktree:

```bash
PYTHONPATH=src /Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/contract/test_personal_assistant_main_contract.py
# 117 passed, 2 warnings

/Users/czj/Repos/nano-multiagent/.venv/bin/ruff check src/personal_assistant/main.py src/personal_assistant/gateway/runtime_delivery/lifecycle.py src/personal_assistant/gateway/runtime_delivery/observer.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/contract/test_personal_assistant_main_contract.py
# All checks passed
```

## Issues

### CRITICAL

- `src/personal_assistant/gateway/runtime_delivery/observer.py:156` still makes the observer operate on `RunDeliveryContextStore.legacy_contexts` for every kernel event path, not only heartbeat/cron compatibility boundaries. This is not just a string-test naming issue: `_run_context_map()` returns the mutable legacy dict at `observer.py:18-23`, the observer reads from that dict at `observer.py:303`, and IM ack/runtime backfills write only that dict at `observer.py:384-385`, `observer.py:482-489`, and `observer.py:658-664`. Meanwhile `RunDeliveryContext` remains a frozen typed seed object without `message_id`, resolved `conversation_id`, or `kernel_message_id` fields (`src/personal_assistant/gateway/runtime_delivery/context.py:57-70`). That means the typed context is not the actual runtime event state owner required by the M3 exit criterion in `M3-fix-runtime-lifecycle-owner/tasks.md:14`; the production observer still depends on the same legacy map shape that round 1 called out.
  - Impact: user behavior may still pass today, but the architecture goal remains unclosed: runtime delivery facts can diverge between typed context and the mutable legacy view, and future changes can read stale typed state while observer delivery, external mirrors, permission cards, and bubble rolling mutate a separate dict. This keeps the exact hidden coupling the refactor was meant to remove. The current regression in `tests/contract/test_personal_assistant_main_contract.py:25-35` only forbids one source string and does not prove typed-store ownership semantics.
  - Fix: make `RunDeliveryContextStore` expose typed update/read APIs used by `build_kernel_event_observer()` and `roll_bubble()` directly, including ack backfill for `message_id`, resolved `conversation_id`, `kernel_message_id`, rolling state, external current text/markers, and permission/external reply metadata. Keep `legacy_contexts` only at explicit still-dict-shaped heartbeat/cron callers such as `src/personal_assistant/main.py:2616` and `src/personal_assistant/main.py:3032`, or wrap them with a narrow adapter that is not the observer's primary state surface. Replace the string-only contract with a behavioral test that seeds a `RunDeliveryContextStore`, drives a `turn_start` ack through the observer, and asserts the typed store is the state owner/backfill target.

### WARNING

- Feishu/Lark true-platform acceptance remains unverified in M3. The live Web IM direct relay evidence is credible for the Web relay lifecycle closeout, but it cannot close Feishu private/group/shadow/IM-offline platform scenarios from `docs/specs/gateway/spec.md`; M3 progress correctly records the missing credentialed channel and does not fake inbound.
  - Fix: keep this as a release caveat until a credentialed Feishu/Lark environment can run the true platform journeys.

### SUGGESTION

- None.

# Round 3 - Main-Session Targeted Closure Verification

## Verification Report: refactor-454

### Summary

Mode: targeted-closure
Delta range: `1d1cec26..601ea5fb803b7030570af0ff7594b41d980d4a2a`
Focus issues: round-2 observer typed-store boundary; production heartbeat/cron typed-store wiring
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | focus closures verified |
| Correctness | focus closures verified |
| Coherence | no critical deviation found in focus scope |

No critical issue found in the R4 focus scope. This round was performed in the main session after the R4 fix; it is not an independent verifier-agent report.

## Focus Closure Results

| Focus item | Verdict | Evidence |
|---|---|---|
| Observer typed-store boundary | closed | `runtime_delivery/observer.py` now resolves `RunDeliveryContextStore` through `_runtime_context_view(...).runtime_view(run_id)` instead of converting the store to `legacy_contexts` at builder entry. `RunDeliveryContext` owns runtime fields including `conversation_id`, `message_id`, `kernel_message_id`, rolling state, and external markers; `RunDeliveryRuntimeView.__setitem__()` writes through `RunDeliveryContextStore.set_runtime_value()`, which syncs the legacy projection after typed mutation. |
| Relay lifecycle owner remains outside `main.py` | closed | `main.py` imports `build_relay_lifecycle_callback` from `personal_assistant.gateway.runtime_delivery.lifecycle`; contract coverage asserts `main.py` does not define `def _build_relay_lifecycle_callback(`. |
| Production heartbeat/cron stream wiring | closed | `_stream_run_to_completion()` accepts `RunDeliveryContextStore`, seeds owner-direct runs through `RunDeliveryContextStore.seed_owner_direct_run()`, and pops a typed snapshot before discard. `build_runtime()` passes `run_delivery_contexts` to both heartbeat runner and cron stream path; regression coverage forbids `run_context_store=run_delivery_contexts.legacy_contexts` in that production wiring. |
| User-visible behavior preservation | covered in automated scope | M4/M3 gate and full non-e2e regression passed after the fix. No frontend entrypoint, DB schema migration, or user command/protocol entry change was introduced by R4. |

## Commands

```bash
pytest tests/unit/personal_assistant/test_heartbeat_im_delivery.py::test_stream_run_to_completion_seeds_typed_store_seen_by_observer tests/unit/personal_assistant/test_gateway_relay_lifecycle.py::test_build_runtime_wires_typed_delivery_context_store
# before fix: expected red, 2 failed
# after fix: 2 passed, 2 warnings

ruff check src/personal_assistant/main.py src/personal_assistant/gateway/runtime_delivery/context.py src/personal_assistant/gateway/runtime_delivery/observer.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_gateway_relay_lifecycle.py
# All checks passed

pytest tests/unit/personal_assistant/test_gateway_relay_lifecycle.py tests/unit/personal_assistant/test_external_visible_delivery.py tests/unit/personal_assistant/test_gateway_im_resilience.py tests/unit/personal_assistant/test_heartbeat_im_delivery.py tests/unit/personal_assistant/test_cron_delivery_chain.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py tests/contract/test_personal_assistant_main_contract.py
# 121 passed, 2 warnings

pytest -m "not e2e"
# 3332 passed, 2 skipped, 22 deselected, 16 warnings
```

## Caveats

- Feishu/Lark true-platform journeys remain unverified because this worktree does not have a credentialed Feishu/Lark channel. Existing unit/integration coverage and Web IM live evidence are retained, but they are not a substitute for true-platform Feishu/Lark acceptance.

# Round 4 - Independent Targeted Closure Verification

## Verification Report: refactor-454

### Summary

Mode: targeted-closure
Delta range: `1d1cec26..ed6e0de83f1b17700179137598c87d17ff112113`
Focus issues:
- Round-2 CRITICAL: observer typed-store boundary still open because observer consumed `RunDeliveryContextStore.legacy_contexts` rather than typed runtime state.
- Production heartbeat/cron wiring gap found after M4: `build_runtime()` passed `run_delivery_contexts.legacy_contexts` into heartbeat/cron `_stream_run_to_completion()` while observer was built with `RunDeliveryContextStore`.
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | focus closures verified |
| Correctness | focus closures verified |
| Coherence | no critical or warning found in targeted scope |

All targeted closure checks passed. Ready for PR from verifier scope.

## Scope and Method

- Code/docs/tests were read only. No product acceptance journey was run in this verifier pass.
- `1d1cec26..601ea5fb` changes only the focused runtime delivery code/tests/docs; `601ea5fb..ed6e0de8` changes only this report file.
- Existing recorded evidence in `M4-typed-observer-state-owner/progress.md` was inspected but not re-executed here.

## Focus Closure Results

| Focus item | Verdict | Evidence |
|---|---|---|
| Observer typed-store boundary | closed | `src/personal_assistant/gateway/runtime_delivery/observer.py:18` resolves a typed store through `RunDeliveryContextStore.runtime_view(run_id)` instead of taking `legacy_contexts` at builder entry. `RunDeliveryRuntimeView.__setitem__()` writes through `RunDeliveryContextStore.set_runtime_value()` at `src/personal_assistant/gateway/runtime_delivery/context.py:151`, and that method mutates typed fields plus refreshes the legacy projection at `context.py:228`. Observer ack/backfill paths now write through the runtime view at `observer.py:382`, `observer.py:481`, `observer.py:656`, and `roll_bubble()` at `observer.py:67`/`observer.py:104`. Behavioral regressions assert typed shadow ack, owner-direct lazy ack, and roll-bubble backfill at `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py:279`, `:315`, and `:361`. |
| Production heartbeat/cron typed-store wiring | closed | `build_runtime()` creates one `RunDeliveryContextStore` at `src/personal_assistant/main.py:2649`, passes that same typed store to heartbeat at `main.py:2660`, to relay lifecycle/observer at `main.py:2892` and `main.py:2899`, and to cron stream delivery at `main.py:3074`. `_stream_run_to_completion()` now accepts `RunDeliveryContextStore` at `main.py:1194`, seeds owner-direct runs via `_seed_owner_direct_stream_context()` at `main.py:1234`, which calls `RunDeliveryContextStore.seed_owner_direct_run()` at `main.py:1285` / `context.py:280`, then returns the discard-before snapshot through `_pop_stream_context()` at `main.py:1302`. Regression coverage verifies the typed stream path at `tests/unit/personal_assistant/test_heartbeat_im_delivery.py:414` and forbids production `.legacy_contexts` wiring at `tests/unit/personal_assistant/test_gateway_relay_lifecycle.py:397`. |
| Legacy compatibility boundary | closed for target | Remaining production `legacy_contexts` references are confined to the compatibility projection inside `RunDeliveryContextStore` (`context.py:173`, `context.py:176`, `context.py:397`). The focused source search found no remaining `run_context_store=run_delivery_contexts.legacy_contexts` production wiring and no observer entry downgrade. |
| Need for full verification | not required | The fix delta is limited to `src/personal_assistant/main.py`, `src/personal_assistant/gateway/runtime_delivery/context.py`, and focused tests/docs. It does not introduce new Gateway/IM frame shapes, persistence changes, frontend changes, new cross-package imports, or new product entrypoints. The delta directly closes the targeted state-owner split; existing M4 progress records the focused red/green tests, M4/M3 gate, and full non-e2e regression. |

## Issues

### CRITICAL

- None.

### WARNING

- None in targeted closure scope.

### SUGGESTION

- None.

## Caveats

- Feishu/Lark true-platform journeys remain a reviewer/acceptance caveat from earlier rounds. This verifier pass did not run product acceptance journeys and did not treat synthetic inbound as a substitute for true platform evidence.

# Round 5 - Main-Session Code-Review Compatibility Closure

## Verification Report: refactor-454

### Summary

Mode: code-review-fix-closure
Delta range: `6e0bf9e1..HEAD`
Focus issues:
- Gateway-side `WebRelayAdapter` rejected canonical IM relay frames when `conversation_id` appeared only at top level.
- IM-side `node.streaming_delta` parser rejected unrelated optional structured fields before dispatching by `kind`.
- IM-side `node.report` parser rejected legacy non-structured optional `detail` / partially invalid `usage` before the previous persistence-layer downgrade path could ack the report.
requires_full_verification: false

| 维度 | 结果 |
|---|---|
| Completeness | code-review compatibility issues closed |
| Correctness | red/green regressions and broader suites passed |
| Coherence | no new protocol entrypoint or user-visible field required |

No critical issue found in this code-review closure scope.

## Focus Closure Results

| Focus item | Verdict | Evidence |
|---|---|---|
| Relay payload top-level `conversation_id` | closed | `src/IM/ws/gateway_protocol.py` already accepts `payload.conversation_id` before `message.conversation_id`; `src/personal_assistant/channels/web_relay_adapter.py` now follows the same fallback. Regression: `tests/unit/personal_assistant/test_gateway_web_relay_adapter.py::test_web_relay_adapter_accepts_top_level_conversation_id`. |
| `node.streaming_delta` unrelated optional structured fields | closed | `parse_streaming_delta_event()` keeps required text fields strict but treats unrelated malformed optional mappings as absent, preserving per-`kind` validation in `GatewayHandler`. Regression: `tests/im_service/contract/test_gateway_protocol_contract.py::test_streaming_delta_parser_ignores_unrelated_bad_structured_fields`. |
| `node.report` legacy optional payload compatibility | closed | `parse_node_report_event()` still requires `node_id`, `run_id`, and `status`, but ignores non-structured optional `detail` and invalid optional `usage` instead of returning `bad_payload` before handler ack/persistence downgrade. Regression: `tests/im_service/contract/test_gateway_protocol_contract.py::test_node_report_parser_ignores_legacy_unstructured_detail_and_usage`. |
| Replayed downstream `relay.message` frame | closed as verifier-owned regression | Product users cannot force IM to resend one server-to-client WS frame through public HTTP/WS APIs, so this is not a black-box acceptance journey. Regression coverage now includes `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py::test_im_connection_dedupes_replayed_relay_message_frame`, plus existing adapter/store dedup tests. |
| Code-review candidate A (`RuntimeProtocolFacts` metadata leak) | refuted | Session metadata is built through the explicit whitelist in `web_relay_adapter._build_session_metadata()` and the persistence boundary in `session_keys.py`, not by serializing all inbound message metadata. No code change was needed for this candidate. |

## Commands

```bash
/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_web_relay_adapter.py::test_web_relay_adapter_accepts_top_level_conversation_id tests/im_service/contract/test_gateway_protocol_contract.py::test_streaming_delta_parser_ignores_unrelated_bad_structured_fields tests/im_service/contract/test_gateway_protocol_contract.py::test_node_report_parser_ignores_legacy_unstructured_detail_and_usage
# before fix: expected red, 3 failed
# after fix: 3 passed

/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/im_service/contract/test_gateway_protocol_contract.py tests/im_service/unit/test_gateway_handler.py tests/im_service/integration/test_gateway_websocket_api.py
# 69 passed

/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest tests/unit/personal_assistant/test_gateway_im_connection_behavior.py::test_im_connection_dedupes_replayed_relay_message_frame tests/unit/personal_assistant/test_gateway_web_relay_adapter.py::test_web_relay_adapter_uses_dedup_store_on_accept tests/unit/personal_assistant/test_gateway_web_relay_adapter.py::test_web_relay_adapter_without_store_uses_in_memory_dedup tests/unit/personal_assistant/test_gateway_relay_dedup.py
# 8 passed

/Users/czj/Repos/nano-multiagent/.venv/bin/python -m ruff check src/IM/ws/gateway_protocol.py src/personal_assistant/channels/web_relay_adapter.py tests/unit/personal_assistant/test_gateway_web_relay_adapter.py tests/im_service/contract/test_gateway_protocol_contract.py
# All checks passed

/Users/czj/Repos/nano-multiagent/.venv/bin/python -m pytest -m "not e2e"
# 3335 passed, 2 skipped, 22 deselected, 16 warnings
```

## Caveats

- Feishu/Lark true-platform journeys remain unverified because this worktree does not have a credentialed Feishu/Lark channel. This code-review closure does not change the product acceptance verdict in `acceptance.md`.
- Same-relay-frame redelivery is now explicitly owned by verifier/regression coverage because no public product journey can force one IM server-to-client frame to be re-sent. It remains outside product-review pass/fail unless a future dedicated resend/debug harness is added.
