# Verification Report: bugfix-567-inbound-attachments

> Validation snapshot: `c5f1d5620 → 30dac3b37`
>
> verification_mode: full, with corrected-delta reconciliation requested before canonical merge

## Summary

| Dimension | Result |
|---|---|
| Completeness | 0/1 milestones can close |
| Correctness | 2 implementation mismatches |
| Coherence | Core snapshot/admission design followed; attachment projection is incomplete |

Two WARNINGs found. Fix before PR.

## Completeness

- M1-fix is the sole milestone. Its snapshot admission, post-admission consumption, ordinary-file classification, single-thread ordering, current/history failure split, and group steer fallback have code and focused-test evidence.
- The M1 exit requirement that both `single_thread` and `global` preserve text and valid images is not complete: global Feishu input uses attachment-index placeholders and loses the image before Inbox admission.
- No prototype/reference contract applies.

## Correctness

| Requirement / Scenario | Implementation evidence | Test evidence | Status |
|---|---|---|---|
| Ordinary files or mixed files/images retain text and valid images in both modes | `session_run_coordinator.py:2384-2445`; `global_run_coordinator.py:559-612` | `test_gateway_image_inbound.py:270-305`; `test_global_gateway_runtime.py:283-377` | implementation mismatch: global test covers Web-shaped attachments only; Feishu placeholder-shaped input loses its valid image |
| Historical unavailable image preserves other input and records an unread failure | `session_run_coordinator.py:2399-2425` | `test_gateway_image_inbound.py:308-342` | implementation mismatch: `inbound_attachments.py:57-70` serializes a failed data-image payload into the model text |
| Current failure or unaccepted input retains group buffer | `session_run_coordinator.py:1782-1827,2354-2459`; `group_context_store.py:138-179` | `test_group_context_admission.py:32-76` | covered |
| Later group context remains pending; rejected steer rebuilds FIFO input | `session_run_coordinator.py:807-852,2451-2459`; `group_context_store.py:163-179` | `test_group_context_admission.py:78-126`; `test_session_run_coordinator_admission.py:693-730` | covered |

## Coherence

| Design decision | Followed? | Code evidence |
|---|---|---|
| Shared classification without file reads | Yes | `inbound_attachments.py:25-70`; both coordinators import it |
| Per-image projection preserves original indexes | Partly | `session_run_coordinator.py:2384-2423,3907-3934` preserves single-thread order; `global_run_coordinator.py:559-602` does not materialize Feishu `attachment_index` parts |
| History failures are isolated from current failures | Partly | `session_run_coordinator.py:2381-2409`; failed data URLs are emitted unbounded as text |
| Consume snapshot only after admission; refresh group FIFO after rejected steer | Yes | `session_run_coordinator.py:833,850-852,1827,2358-2460`; `group_context_store.py:138-179` |

## Issues

### CRITICAL

None.

### WARNING

- `src/personal_assistant/gateway/inbound_attachments.py:57`: omit or redact a `data:` URL payload when projecting an unread attachment. Keep bounded filename/type/source identity and the historical failure reason; add a regression that an oversized/corrupt historical data image cannot place its base64 into model text.
- `src/personal_assistant/gateway/global_run_coordinator.py:559`: resolve/reconstruct Feishu `attachment_index` image placeholders from the classified attachment list before Inbox admission, while retaining the normal-file unread description. Add a global Feishu-shaped mixed image/file regression.

### SUGGESTION

None.

## Corrected Delta Reconciliation

| Delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| `relay-protocol.md` ordinary file/mixed-image scenario | `session_run_coordinator.py:2384-2445`; `global_run_coordinator.py:559-612` | single-thread matrix and Web global integration test | implementation-mismatch |
| `relay-protocol.md` historical unavailable image scenario | `session_run_coordinator.py:2399-2425`; `inbound_attachments.py:57-70` | valid-image history test only | implementation-mismatch |
| `relay-protocol.md` accept-after-consume and later-arrival scenarios | `group_context_store.py:138-179`; `session_run_coordinator.py:833,1827` | `test_group_context_admission.py:32-126` | aligned |

### Uncovered Observable Behavior

- Historical oversized/corrupt `data:image` source projection is not bounded.
- Global Feishu mixed input is not represented by the Web-shaped global integration fixture.

Outcome: implementation-mismatch

## Round 2 — Corrected Delta Reconciliation

> Validation snapshot: `c5f1d5620c6323821a430fc3d53feefeb180fd89 → 800f4dfe3ef818dbbf4db0fd2e1ca322dbdf8089`
>
> verification_mode: corrected-delta; `fix_delta_range`: `30dac3b37..800f4dfe3`

R1 remains above as the full-verification record. This bounded reconciliation covers its two WARNINGs and the associated delta behavior; the snapshot/admission, later-arrival and steer-fallback conclusions are unchanged because this fix delta does not alter those paths.

| R1 issue / delta item | Implementation evidence | Test evidence | Outcome |
|---|---|---|---|
| Historical unavailable `data:image` must record only unread source/failure facts | `inbound_attachments.py:57-72` replaces every `data:` URL with `[内联附件，内容省略]` before JSON text projection; `session_run_coordinator.py:2399-2425` continues to keep a historical failure non-blocking | `test_gateway_image_inbound.py:308-350` runs the public pipeline with a 6,990,658-character oversized inline image and asserts valid text/image retention plus submitted text below 2,000 characters | aligned |
| Global mixed file/image input, including Feishu `attachment_index`, must reach Inbox/model in provider text/image order | `global_run_coordinator.py:558-625` resolves indexed descriptors into Inbox sources once, retains ordered provider text, and adds unread ordinary-file descriptions | `test_global_gateway_runtime.py:283-400` parameterizes Web and Feishu shapes, checks the post-image text and an actual image block in SDK LLM tool content | aligned |
| Group snapshot admission and steer/FIFO consumption behavior | No production change in this delta | R1 evidence retained: `test_group_context_admission.py:32-126`; `test_session_run_coordinator_admission.py:693-730` | aligned |

### Uncovered Observable Behavior

None within this corrected-delta scope. The recorded product-review global mixed-image journey remains separate from this static verifier result.

## Issues

### CRITICAL

None.

### WARNING

None.

### SUGGESTION

None.

Outcome: aligned

## Round 3 — Corrected Delta Reconciliation (final rebase)

> Validation snapshot: Nano `600fe19968f50ec9d820eaf4ab145acf8430934a → 1120f52bf`; LLM_PROXY `016f32eb7c44f58d8429d833f8973c8cc43ba337 → 514cd964bb6289d426ddbdbaa7a93200ad67e988`
>
> verification_mode: corrected-delta; verdict: **pass — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**; `requires_full_verification: false`

This reconciliation covers the final Nano rebase, both previously corrected Nano findings, and the cross-repository provider delta required by the incident and M1 exit criterion. The canonical relay requirements are present unchanged in the final tree (`docs/specs/gateway/relay-protocol.md:87-111`) and match the unit delta. `git diff --check` passes for both frozen ranges.

| Delta item | Implementation evidence | Test / product evidence | Outcome |
|---|---|---|---|
| Ordinary files and mixed valid image/file input retain text, order, and an explicit unread-file description in both modes | `inbound_attachments.py:25-72`; `session_run_coordinator.py:2386-2427,3911-3938`; `global_run_coordinator.py:558-625` classify once, resolve indexed images, and preserve ordered provider parts | Rebased focused Nano suite passed: `72 passed in 5.94s`, including the Web/Feishu real-kernel global fixture that observes an actual SDK tool-content image block | aligned |
| Historical unavailable images are non-blocking, do not expose inline data payloads, and current failures still stop before admission | `inbound_attachments.py:57-72` replaces a `data:` source with a bounded marker; `session_run_coordinator.py:2381-2413` separates current from historical resolution | The same focused suite includes the 6,990,658-character inline-image regression and passed; existing correction evidence records the public-pipeline bound | aligned |
| Group snapshots are consumed only after accepted submit/steer; later arrivals survive and rejected group steer rebuilds FIFO input | `group_context_store.py:138-179`; `session_run_coordinator.py:807-852,1804-1829,2457-2461` | Rebased focused Nano suite includes the admission, later-arrival, and steer-fallback seams and passed | aligned |
| Nested Anthropic `tool_result` base64/URL images reach Codex while ordinary Chat and text-only tool outputs retain their prior shapes | LLM_PROXY `messages.py:405-409` enables preservation only for `codex_oauth`; `proxy_converters.py` maps sources and emits ordered `input_text`/`input_image` content inside the corresponding `function_call_output.output`. Local Codex `models.rs`, `view_image.rs`, `client.rs`, and its request test confirm API-key/OAuth share this Responses shape | `pytest -q tests/test_proxy_converters.py tests/test_messages_routes.py`: `28 passed`; full proxy suite: `133 passed, 24 skipped`. A saved real-request replay through `:4010` returned HTTP 200 and identified the red rectangle; the raw upstream request kept the image in the function output with no synthetic user image. Product Round 7 records the final full journey | aligned |
| Rebase against refactor-568 tool-event projection / terminal cleanup | Final-versus-pre-rebase attachment diff contains only refactor-568's two `delivery_context_store.suppress(... terminal_cleanup=...)` call changes in `session_run_coordinator.py`; it has no attachment, snapshot, resolver, Inbox, or provider-payload interaction | refactor-568's archived final verifier closes its terminal cleanup gate; the rebase-specific 72-test attachment suite passed | aligned |

### Uncovered Observable Behavior

None within this corrected-delta scope. Product Round 6 directly exercises the final rebase snapshot `1120f52bf` with Proxy `514cd964`, observes the image and unread-file behavior, and records all four raw requests at `127.0.0.1:4010`.

## Issues

### CRITICAL

None.

### WARNING

None.

### SUGGESTION

None.

Outcome: aligned

## Round 4 — Corrected Delta Reconciliation (provider contract correction)

> Validation snapshot: Nano documentation `51f10e4e30d042bec8d5a582c836176f49df8f26`; LLM_PROXY `016f32eb7c44f58d8429d833f8973c8cc43ba337 → dc39109c48567980a5bf55ba4904075bd1ee23ef`
>
> verification_mode: corrected-delta; verdict: **pass — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**; `requires_full_verification: false`

This delta corrects the provider representation, not Nano's attachment, admission, storage, or canonical relay behavior. The incident/M1 condition remains that valid nested tool-result images reach the model; the native Codex representation retains that image under its original tool call instead of manufacturing a user message.

| Delta item | Implementation evidence | Test / contract evidence | Outcome |
|---|---|---|---|
| Nested Anthropic base64/URL tool-result images remain ordered in the original function-call output | `proxy_converters.py:85-110,208-235,674-678` maps image sources to `input_image` and passes the full structured output to the matching `call_id` | `test_proxy_converters.py:100-280` covers base64, URL, direct structured content, and JSON-wrapped content; focused suite: `28 passed` | aligned |
| No synthetic following user image is emitted; ordinary OpenAI Chat still uses string tool content | `proxy_converters.py:674-678` appends only the function output; `messages.py:405-409` enables preservation only for `codex_oauth` | `test_messages_routes.py:55-92` asserts bearer string output, Codex array output, and exactly two input items | aligned |
| Native Codex Responses contract accepts image content inside tool output for both request identities | Local Codex `ViewImageOutput::to_response_item` creates `ContentItems(InputImage)` and `ResponsesApiRequest` receives formatted input before auth routing | Local Codex `resume_replays_image_tool_outputs_with_detail` asserts outbound `function_call_output.output` equals an `input_image` array; full proxy suite: `133 passed, 24 skipped`; saved real-request replay returned HTTP 200 and recognized the red rectangle with no following user image | aligned |

### Uncovered Observable Behavior

None within this corrected-delta scope. The provider correction is directly exercised by the saved real request and Product Round 7: the matching raw requests retain `[input_text, input_image]` in `function_call_output.output`, contain no synthetic user image, route through `:4010`, and yield the expected recognition result.

The Round 3 follow-up-user-image conclusion is superseded by this native request-contract evidence. It is retained as historical review context only.

## Issues

### CRITICAL

None.

### WARNING

None.

### SUGGESTION

None.

Outcome: aligned

## Round 5 — Corrected Delta Reconciliation (provider protocol-boundary closure)

> Validation snapshot: Nano documentation `ccb07178f6f80ce6309eddb9d1b5db43a1367868`; LLM_PROXY `dc39109c48567980a5bf55ba4904075bd1ee23ef → c18d7c2b6ff2a76bfb28bbf212604f1f4d127024`
>
> verification_mode: corrected-delta; verdict: **pass — 0 CRITICAL / 0 WARNING / 0 SUGGESTION**; `requires_full_verification: false`

This closure does not change Nano attachment, snapshot-admission, unread-file, or canonical relay semantics. It makes the already corrected provider representation depend on an explicit provider-to-upstream-protocol contract throughout the `/v1/messages` bridge.

| Corrected-delta item | Implementation evidence | Test / product evidence | Outcome |
|---|---|---|---|
| P1: payload/URL/model-suffix selection no longer depends on an openai-compatible profile's auth type | `upstream_config.py:54-69` rejects `auth.type=codex_oauth` outside `provider=codex_oauth`; `resolve_upstream_protocol` and `build_upstream_url` map provider plus ingress to the wire protocol | Protocol and invalid-mixed-profile coverage passed in the focused `45`-test set | aligned |
| P2: response parsing uses the same protocol as request construction | `messages.py` passes one resolved `upstream_protocol` to the adapter, non-stream handler, and streaming handler; `messages_stream.py` selects the Responses collector/parser on `PROTOCOL_OPENAI_RESPONSES` | Focused response/converter set: `51 passed`; full proxy suite: `143 passed, 24 skipped` | aligned |
| Chat and Responses retain their distinct tool-result contracts | Chat adapter uses text-only tool messages; Responses adapter retains nested base64/URL images as ordered content in the original `function_call_output.output` with no synthetic user image | Saved real-request replay returned HTTP 200, recognized the red rectangle, and recorded `[input_text, input_image]` in the function output with zero user images | aligned |

### Uncovered Observable Behavior

None within this corrected-delta scope. The saved request replay directly verifies the provider boundary that had blocked M1, while the prior full product journey establishes the inbound attachment and unread-file behavior. This refactor changes the ownership of the provider protocol decision, not those Nano behaviors.

## Issues

### CRITICAL

None.

### WARNING

None.

### SUGGESTION

None.

Outcome: aligned
