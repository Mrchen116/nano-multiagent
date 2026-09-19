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
