# Selected synthetic product audit metrics

## Provenance and scope

Executor collected these necessary derived metrics at `2026-10-27T11:38:23.258Z` after new explicit owner permission for this run's synthetic sessions and selected call IDs. The normal tool permission check succeeded. The previously refused raw snapshot method was not retried. No raw observation, messages, arguments, reason text, provider request IDs or secrets are retained here.

- Validated product/test tree: `1862af639681defdb91651f50cc6e01459e63e0b`; report-only HEAD at collection: `6c535252d434ff4a384c8542d14a48435bab936c`. Product runtime code is unchanged from `dfee3df40116757346ef6a7edcaa5d10734c9a61`.
- Original isolated public RuntimeClient `initialize` / `session.observe`, same profiles and bindings; no private database read. Product-call handler rejects all business calls. Complete observations were processed in memory and discarded; only whitelisted selected-call metrics were printed. Consumer shut down normally, exit0.
- Before initialize, owned Node3657 / DSH3660 / IM95854 / proxy7499 were confirmed absent; own ports53939/56096 closed. No shared4000 or Harness process was stopped or changed.
- CC Agent `review361-cc-sol`, session `5b0058ad-b302-406c-9fc3-0fbd57423ee4`; Codex Agent `review361-codex-sol`, session `e051bfd4-c3b2-4069-8f21-723fcf03310b`.
- Selected18 callIds per session, missing0 each. Each selected call has exactly one retry-bearing approval aggregate and a distinct reviewId: **36 reviews / 62 actual attempts** (31 attempts per strategy). Additional return_to_agent audit rows are final routing, not extra model attempts or new main tool calls.
- Every attempt records reviewer provider `issue361-review-proxy`, model `codexOAuth:gpt-6-luna`. These are actual audit values, not inferred from HTTP counts. Main execution was Sol/high as recorded by independent product acceptance.

## Exact call/review association and attempts

Notation: `category:elapsedMs` in ordinal order; `E/I` = extraUsed / invalidRecoveryUsed; total is actual retry aggregate elapsedMs. All emitted cleanupConfirmed values for failed/cancelled attempts are true; successful attempts do not claim a cleanup flag. Retry delays are500ms then1000ms where another attempt is admitted. The backoff-cancel row records a planned500ms delay but cancellation before the next attempt.

### CC (rules nano)

| Case | Main callId | reviewId | Actual attempts | E/I | Final category / total ms |
|---|---|---|---|---|---|
| Live install | call_c07d33bfae774959a01e3862aec294d3 | fa597389-b8d6-445c-94df-3c6d64b510c0 | allow:2317 | 0/0 | allow /2317 |
| Live A | call_306d3efd5d4944ffb9083f3314b8914e | 7256f247-da85-4e29-8aff-2ed7bfd1f84a | allow:2134 | 0/0 | allow /2134 |
| Live B | call_d7470dd00bf94b408f34f04efdfc7768 | 817c89f0-be00-47dd-b763-c04e6ca8b978 | allow:2770 | 0/0 | allow /2770 |
| 503-live | call_ef8d1bcc0c0f4241af29c794c9b8d04a | d4cbf1d7-4ed1-4731-99c7-6d6cd23a6bcc | service:18 → allow:3139 | 1/0 | allow /3659 |
| 503-exhaust | call_c1dace7d05b2418c98cccff1ad0c2cc3 | 2346d0e7-45fb-4552-ade8-12238052580f | service:13 → service:11 → service:11 | 2/0 | service /1537 |
| auth401 | call_6b7584f3a73d48cf870dcaf01b0edf52 | edcfe415-ce39-4b34-8b7a-40d0d5158f54 | auth:6 | 0/0 | auth /6 |
| Valid deny | call_a59158c1a7d444e1b342e7bf94aaa3df | 83cdf2cb-ffb7-468a-88ab-b0f8a3a8c162 | deny:24 (stages1,2) | 0/0 | deny /24 |
| invalid | call_1b253f789e77425e840ad01845206e32 | 9fd1724d-6fd5-421a-aaab-7ce744eef6d2 | invalid:14 → invalid:11 | 1/1 | invalid /529 |
| invalid-503-live | call_00fd1f2fd17b47bf96b648ab1836e264 | 5e0f3771-f667-4de1-b447-e9dda94ee014 | invalid:15 → service:11 → allow:6053 | 2/1 | allow /7582 |
| 503-invalid-invalid | call_ef23105b00e74967b3f6103e1e177b1c | 8b6db1a5-2330-4bc1-a6e8-3a2c1e9977b1 | service:17 → invalid:7 → invalid:8 | 2/1 | invalid /1534 |
| 429-transport-live | call_2c7b758d7c394756bd40661c86624a94 | 0f094044-c79b-4a73-98b4-eda2f8123c43 | service:19 → transport:13 → allow:2026 | 2/0 | allow /3561 |
| Cancel active | call_2ba05e1b37df4bc1ba324342848e326f | 77622a45-aee3-493e-80f3-a8c9d11c8a32 | cancel:273 | 0/0 | cancel /273 |
| Cancel backoff | call_c1883ae2bb4c4b4285bdfccad16eeb9b | f2062a07-c7fd-424b-87ca-88260752db15 | service:13 (then cancel in delay) | 0/0 | cancel /209 |
| empty | call_14b57971962a49db92feea750235448d | c5167550-3603-48b3-95c5-993c65951a26 | invalid:13 → invalid:12 | 1/1 | invalid /527 |
| timeout-live | call_20194e428b894a5499da01a7d771a17b | b09b4fe4-e118-4910-a85d-50d103feba82 | timeout:30006 → allow:7678 | 1/0 | allow /38185 |
| Install recovery | call_cfce86d2722d4733943c223c8e565af9 | 7f973bba-3620-44be-92a0-05372d0d601f | service:17 → allow:7001 | 1/0 | allow /7519 |
| Install auth | call_34b3749268e04700b24cf8b6e92db2e3 | 04223989-ac65-4fb9-8c9c-bc44fa2bfc13 | auth:25 | 0/0 | auth /28 |
| Install stop | call_9d316acee220493997d0de00287607b0 | dad065ee-4580-4bf3-bde5-879d039ec8af | cancel:297 | 0/0 | cancel /297 |

### Codex (rules codex)

| Case | Main callId | reviewId | Actual attempts | E/I | Final category / total ms |
|---|---|---|---|---|---|
| Live install | call_a9e52380dba34327937db5329bd691e1 | 9f1463d0-5601-4e39-822a-ec974ddf53c9 | allow:7098 | 0/0 | allow /7098 |
| Live A | call_3d73c157577a4589b28d0c68f6172699 | f391c44c-b7c3-42c6-bd53-f222c61f7513 | allow:4156 | 0/0 | allow /4156 |
| Live B | call_b20ac99bf67b46739747bbcdd434febd | 22349a92-04fa-4423-bb4b-b0429b267603 | allow:8219 | 0/0 | allow /8219 |
| 503-live | call_3fb24e22fdd04e9c8b90c370cf51e039 | 179fe7c6-b0cd-4b61-b7c7-1beffaa5a346 | service:64 → allow:2746 | 1/0 | allow /3313 |
| 503-exhaust | call_aacd322b8cf44469bf666979b8f220b3 | cf2b90d9-61fd-46dc-bc14-1e8f9a9f1618 | service:65 → service:96 → service:100 | 2/0 | service /1765 |
| auth401 | call_32682a338c714dbba2dc0e07dfa75b70 | 663dd8e1-60fb-43f3-bede-388b232065d8 | auth:94 | 0/0 | auth /94 |
| Valid deny | call_a2ddd41af06f4bdda397b2b9d6dff573 | 238d9d99-ea74-4906-a365-f8c1cf44e308 | deny:79 | 0/0 | deny /79 |
| invalid | call_9eb608cd44d6481996969b3009cd6e53 | 7932510d-4fba-4ce3-b1c0-36dd87a0fcec | invalid:60 → invalid:63 | 1/1 | invalid /623 |
| invalid-503-live | call_e3730b177fb64c0cb51bec27af595253 | 4564625f-cfd3-4b71-a4cb-8b4eb2cefd95 | invalid:97 → service:95 → allow:3279 | 2/1 | allow /4976 |
| 503-invalid-invalid | call_1d7eaeb8df36400ba88cb17b551c5740 | 6498504e-a6d3-4502-8d64-e878734af40a | service:48 → invalid:93 → invalid:82 | 2/1 | invalid /1728 |
| 429-transport-live | call_7f5f780b1b0b475ca7314ff118a9ec0f | c5ca2138-103d-4768-ae33-046aa08a9f2f | service:92 → transport:104 → allow:4269 | 2/0 | allow /5970 |
| Cancel active | call_14d56fd1f0184ffe9a46f0b6c5cc3512 | 292a82cc-ea60-43be-984a-03af1e4c07c5 | cancel:361 | 0/0 | cancel /361 |
| Cancel backoff | call_95ba898d0f9449929843f8100c82e1a8 | d2fbc167-8c97-4a91-93af-7279c0bc5b9f | service:109 (then cancel in delay) | 0/0 | cancel /219 |
| empty | call_fa53053012cf474cb782d6358faf3fda | 5f8695dc-c832-4cd7-9944-624b78973b26 | invalid:80 → invalid:94 | 1/1 | invalid /676 |
| timeout-live | call_dea834e48ffc42659ed19a4f58e3e6aa | 9eaa1211-8e8e-47cb-a373-33a94b5797ef | timeout:90042 → allow:2703 | 1/0 | allow /93246 |
| Install recovery | call_7d1047d76a104a178894e522f72c217c | d162f3b1-0758-431a-a391-01d05ea0dd1c | service:55 → allow:3166 | 1/0 | allow /3722 |
| Install auth | call_6f97cf451a1e48e2a48a228c98456146 | 36e28dee-f52b-4bec-8949-8c9554afda59 | auth:60 | 0/0 | auth /60 |
| Install stop | call_4a39e773c7964a1b86e458e0b2fa9db6 | 5a60fca0-49e0-4b94-a6d6-288fdca44535 | cancel:221 | 0/0 | cancel /221 |

## Routing, timing and usage interpretation

- Final allow rows have source `classifier_allow`, decision `allow`; effective deny has `classifier_block` / `deny`; technical exhaustion/auth/invalid has `classifier_unavailable` / `no_verdict`, followed by a distinct same-call `return_to_agent` / `deny` row. Cancellation has `classifier_cancel` / `cancel`, no extra attempt. This is audit evidence; independent Work/plugin-list results establish actual business effects.
- SERVER gives service; RATE_LIMIT also gives service; connection drop gives TRANSPORT/transport; AUTH gives auth. Timeout is independently categorized, not misreported as invalid.
- CC timeout attempt starts1793099713422, ends1793099743428; next starts1793099743929. Codex timeout starts1793099816700, ends1793099906742; next starts1793099907243. Thus actual gaps are501ms, with fresh succeeding attempts. The first CC timeout is its30s stage limit, not an exhausted90s budget. The separate native fake-clock evidence establishes complete subsequent budgets; this table does not claim each real subsequent attempt consumed90s.
- **Backoff correction:** the proxy injected Retry-After10s, but no providerRetryAfterMs was surfaced in these actual error audits; recorded delayAfterMs is500ms, not10s. CC attempt start1793099548804/end1793099548817, cancellation audit time1793099549013 (196ms after the failed attempt, before the planned1793099549317 retry boundary); aggregate total209ms. Codex attempt start1793099612520/end1793099612629, cancellation audit time1793099612739 (110ms after the failed attempt, before the planned1793099613129 retry boundary); aggregate total219ms. Both stops occurred during the actual500ms backoff, with zero next attempt. The12s post-stop observation remains valid; it must not be described as proof the actual delay was10s. Hint-cap behavior is separately covered by deterministic/native tests.
- CC successful records use stage1; its valid-deny record has stages1 and2 **inside one attempt**. Codex child records carry request1; live/R3 generally delta, valid deny rebuild, backoff-cancel/empty/timeout use full where recorded. These are stage/request/context facts, not additional complete attempts.
- All failed-attempt aggregate usage is absent/unknown, not a fabricated zero. Cancel/timeout child usage is also absent/unknown. For injected HTTP errors the SDK emits child0/0; report these as SDK-provided zero fields, **not measured real-model token usage**. Injected invalid/empty/deny responses carry fixture child1/1; these are explicitly synthetic, not live usage. CC deny aggregate usage is absent although its two synthetic children have1/1.
- Codex successful aggregate representation did not expose inputTokens under the selected scalar key; its per-request child inputTokens are available below. Do not fill the absent aggregate field with a guessed zero or mislabel per-request usage as a separate billing total.

Live successful child usage (`inputTokens / outputTokens`, cacheReadTokens where supplied; absence of a cache field is unknown/not reported, not zero):

| Case | CC live child | Codex live child |
|---|---|---|
| Live install | 38172 /11 | 1210 /70; cacheRead38400 |
| Live A | 38459 /11 | 1311 /60; cacheRead39424 |
| Live B | 38546 /11 | 815 /58; cacheRead40576 |
| 503-live | 40084 /11 | 43995 /62 |
| invalid-503-live | 45768 /138 | 14791 /61 |
| 429-transport-live | 48103 /11 | 18571 /56 |
| timeout-live | 52092 /103 | 12790 /57 |
| Install recovery | 1685 /11; cacheRead57088 | 35695 /73 |

## Acceptance handoff

These are executor-collected actual public-consumer metrics, not an independent reviewer rerun. The original product reviewer must correlate them with its independently observed Work, stop and installation-list outcomes and issue the updated verdict. Earlier fail/inconclusive reports remain historical evidence. The independent static reviewer must then close V-R1-1 if warranted. No final sync, archive or Ready PR is implied by this capture alone.
