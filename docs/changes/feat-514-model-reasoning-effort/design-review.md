# Design Review: feat-514-model-reasoning-effort

## Round 1

### Metadata

- reviewer: `/root/feat514_design_reviewer`
- review_mode: `full`
- mode_rationale: Gate 2 Round 1 for a Full change unit; the review covers the complete design package, current contracts and code paths, delta specs, and the deployed model-routing wiring.
- started_at: `2026-08-07T13:45:00+08:00`
- completed_at: `2026-08-07T14:38:39+08:00`
- duration: `00:53:39`

### Verdict

**Issues Found — 2 CRITICAL / 1 WARNING.** The unit has a sound product boundary (PA owns catalog and runtime resolution; IM remains a descriptor consumer), and the prototype agrees with the intended selection states. It cannot enter implementation yet: the selected value does not have a correct provider-protocol translation on the actual Anthropic route, and the proposed IM/Gateway write path cannot uphold the required “not saved on stale/invalid capability” state transition.

### Coverage

| Review surface | Evidence read | Result |
| --- | --- | --- |
| Unit inputs | `spec.md`, `design.md`, `prototype.html`, and all three `specs/` deltas | Complete; requirements, clarifications, non-goals, decisions, data flow, risks, runbook, and M1 are ledgered below. |
| Current contracts | `SPEC.md`; `docs/specs/{kernel/model-runtime,gateway/agent-capabilities,im/agents-nodes}.md`; `docs/development/change-workflow.md`; `CONTRIBUTING.md` | Delta anchors and package ownership are valid; two proposed execution paths do not close their stated contracts. |
| Runtime implementation | PA config/session/reporter/sync/composition; SDK runtime/kernel; Agent loop; Anthropic and OpenAI-compatible providers | Verified the current end-to-end normal/background runtime paths and request merge point. |
| IM implementation | Agent/domain models, config service, repository, agent/node API routes, API client and create/detail pages | Verified today’s durable-write-then-async-sync flow and UI success transition. |
| Deployment wiring | `docs/operations/{prod-fleet,gateway}.md`, `config/e2e/gateway.yaml`, local deployed PA/LLM proxy configuration and request converter | Verified that the relevant shipped/e2e PA models use the Anthropic provider path; production rollout details are not actionable enough. |
| External protocol source | [DeepSeek Thinking Mode documentation](https://api-docs.deepseek.com/guides/thinking_mode) | Confirms that DeepSeek’s Anthropic-compatible request uses `output_config.effort`, while its OpenAI-compatible request uses `reasoning_effort`. |

### Verification ledger

#### Current-state assertions

| ID | Assertion / design basis | Evidence and review result |
| --- | --- | --- |
| C1 | Gateway model configuration currently has static provider request extras but no reasoning capability descriptor. | `src/personal_assistant/config/local_store.py:29-64,997-1064` parses only model name, `extra_request_body`, and context window. **Verified.** |
| C2 | The session runtime currently carries model/prompt/skills/tools/features, not a per-request model extra. | `src/agent/sdk/runtime.py:17-102`; `src/personal_assistant/gateway/session_composition.py:38-65`. **Verified.** |
| C3 | Provider code merges the model’s static extra body with a request extra body. | `src/agent/platform/llm/providers/anthropic/client.py:66-73` merges static first and dynamic second; its mapper emits the result at `mapper.py:80-89`. **Verified, but this does not establish the protocol shape required by [R1-C1].** |
| C4 | Reporter capabilities flow from PA to IM and IM has no vendor-specific model policy. | `src/personal_assistant/reporter/upstream_reporter.py:23-62,143-195`; IM capabilities route at `src/IM/api/routes/agents.py:348-396`. **Verified.** |
| C5 | PA may use `agent.sdk`; IM must not import `agent`. | `SPEC.md:53-64,85,117-124,148-161`; the inspected code follows this direction. **Verified.** |
| C6 | Existing-agent configuration changes are applied before a subsequent safe submission rather than interrupting an in-flight run. | `src/personal_assistant/gateway/session_run_coordinator.py:1195-1252` projects/reconfigures before `sync_submit`; kernel runtime reconfiguration is at `src/agent/sdk/kernel.py:1152-1194`. **Verified.** |
| C7 | Static `extra_request_body` is a model property and must remain separate from a user-selected value. | Static construction is in `src/personal_assistant/config/local_store.py:1029-1064`; merge ordering is in the Anthropic client above. **Verified.** |
| C8 | Normal, heartbeat, and cron delivery reuse the projected session runtime path. | `src/personal_assistant/gateway/kernel_client.py:74-84,129-219`; session binding uses the same projection at `session_binder.py:416-480`. **Verified.** |
| C9 | Runtime identity/persistence is fingerprinted and reconstructed on create/read/fork/reconfigure. | `src/agent/sdk/runtime.py:61-102`; `src/agent/sdk/kernel.py:980-1194`. **Verified.** |
| C10 | The current Web IM create/detail pages use native model selectors and server-result mutation states. | `src/IM/frontend/src/features/agents/agent-create-page.tsx:401-421,481-491,725-754`; `agent-detail-page.tsx:1303-1348,1482-1842`. **Verified; prototype is compatible with this surface.** |
| C11 | The fleet uses separately configured MacBook Air and Mac mini Gateways with their own model upstream path. | `docs/operations/prod-fleet.md:8-29`; e2e model configuration uses provider `anthropic` at `config/e2e/gateway.yaml:41-54`. **Verified; the design does not turn this fact into a deployable capability matrix, see [R1-W1].** |

#### Design decisions and data flow

| Decision | Evidence / outcome |
| --- | --- |
| D1 — config schema and universal `reasoning_effort` request body | The schema keeps a useful separation between `selectable`, `fixed`, and absent. Its assertion that the selected value can universally become top-level `{"reasoning_effort": ...}` is false for the current Anthropic provider route; see [R1-C1]. |
| D2 — PA-owned `ModelReasoningCatalog` | Correct ownership. A validated immutable catalog serving config, reporter, sync, and runtime is a deeper reusable interface than duplicating interpretation in IM. Its proposed `capability_for` / `resolve` / `validate` responsibilities are sufficient once the write transaction is defined. |
| D3 — `SessionRuntimeConfig.model_request_extra_body` | Carrying a resolved generic request-extra through the existing SDK runtime is compatible with current normal/background reuse and static-extra merging. It still needs a provider-protocol conversion at the final adapter, not merely `payload.update`; see [R1-C1]. |
| D4 — profile persistence and runtime projection | Carrying `reasoning_effort` in the profile, clearing it for fixed/none, and resolving legacy records to the configured default fit R2/R3. The stated “Gateway final validation” has no acknowledged pre-persistence flow from IM; see [R1-C2]. |
| D5 — Gateway descriptor and stale validation | Returning one descriptor per model preserves IM’s provider-agnostic boundary. The design names “pre-persist live capability validation” but does not specify a callable, success-acknowledged operation for today’s synchronous IM PATCH/create flows; see [R1-C2]. |
| D6 — Web IM interaction | Fixed is a read-only explanatory state; selectable is a selector; absent asks for a model first. The prototype implements that distinction without pretending a fixed model has a selectable value. **Consistent with the spec.** |
| End-to-end data flow | Reporter → capability fetch → IM draft → Gateway validation → persistence → profile sync → runtime projection is the right conceptual sequence. The actual current mutation order is IM persistence → asynchronous sync, so the diagram is not yet an implementable state machine; see [R1-C2]. |

#### Requirements, clarifications, and non-goals

| Source item | Design coverage | Evidence / result |
| --- | --- | --- |
| R1 / S1 selectable model exposes supported choices and default | D1/D2/D5/D6 specify descriptor, default resolution and selector. | **Blocked by [R1-C1]:** selected/default value is not encoded correctly on the shipped Anthropic path. |
| R1 / S2 no model cannot save an isolated effort | D6 hides/replaces the selector until a model is selected; D4 rejects unsupported persisted effort. | **Covered.** |
| R1 / S3 stale catalog before save has no saved success and asks to refresh/reselect | D5 calls for a `409` stale response and D6 retains a draft. | **Blocked by [R1-C2]:** no specified pre-write/acknowledged validation transaction exists for current IM PATCH/create. |
| R2 / S4 fixed model shows stable read-only explanation | D1/D5 descriptor has `fixed`; D6 prototype gives explanatory, non-selectable state. | **Covered.** |
| R2 / S5 switch to fixed removes unsupported value | D2 resolution and D4 profile normalization/clear behaviour specify this. | **Covered, contingent on the same successful write path in [R1-C2].** |
| R3 / S6 create group saves choice and first chat uses it | D4/D5 and M1 put the profile through create/config sync/runtime projection. | **Blocked by [R1-C1] for the outbound request and [R1-C2] for truthful create success.** |
| R3 / S7 existing group applies on next reply without history loss | D3/D4 rely on existing durable safe reconfiguration; C6 proves the non-interrupting boundary. | **Covered at runtime, contingent on the two critical fixes.** |
| R3 / S8 failed save retains draft and shows error rather than unsaved success | D6 has draft/error UI states. | **Blocked by [R1-C2]:** the current service reports success before a Gateway-side final validation can fail. |
| R4 / S9 configuration changes update the frontend without a frontend build | D2/D5 have live catalog/reporting rather than a frontend list. | **Covered.** |
| R4 / S10 a new model may exist only on one node | D2’s catalog is per Gateway/node and D5 reports the node capability. | **Covered; rollout inventory remains incomplete under [R1-W1].** |
| Clarification Q1 fixed wording | D6 and prototype say the model always thinks and the model decides, without a disabled fake selector. | **Covered.** |
| Clarification Q2 next new reply / preserve history | D3/D4 use durable runtime reconfiguration before submission; no in-flight mutation is proposed. | **Covered.** |
| Clarification Q3 per-node catalog, unified field, retain static extras, Gateway reports / IM does not infer vendor | D1-D5 preserve all four boundaries. | **Covered in ownership; protocol rendering is incomplete under [R1-C1].** |
| Non-goal: per-message override | The field lives in profile/runtime, and D6 puts it in create/edit rather than composer. | **Respected.** |
| Non-goal: expose upstream parameter details | IM consumes a descriptor and presentation labels only. | **Respected.** |
| Non-goal: fabricated values | D2 validates values from deployer config and D5 reports them live. | **Respected.** |
| Non-goal: alter tool approval behaviour | D3 expressly limits dynamic extra body to ordinary model calls; tool approval stays on its own route. | **Respected; M1 needs a regression test to prove it.** |

#### Delta specifications

| Delta contract | Evidence / result |
| --- | --- |
| `specs/kernel/model-runtime.md` — new `model_request_extra_body` consumer contract | Correctly states create/read/fork/identity/reconfigure continuity and limits the future consumer to normal provider calls. It needs the provider adapter contract implied by [R1-C1], but does not force the wrong cross-package owner. |
| `specs/gateway/agent-capabilities.md` — selected model used on a new reply | The modification correctly extends the current selected-model contract to resolved reasoning effort and preserves its existing runtime scenarios. **Blocked only by the two critical implementation-design gaps.** |
| `specs/gateway/agent-capabilities.md` — model capability configuration | Correctly puts live per-model capability reporting and stale/fixed rejection at Gateway. It needs an explicit pre-write callable/ack path under [R1-C2]. |
| `specs/im/agents-nodes.md` — configuration profile | Correctly keeps the choice in IM profile data and requires a live capability check/no false saved state. That observable guarantee is not yet mapped to current mutation ownership; [R1-C2]. |
| `specs/im/agents-nodes.md` — model capability descriptor/UI | Correctly keeps UI declarative and supports selectable/fixed/none presentation. **Covered.** |

#### Milestone plan

| Milestone | Evidence / result |
| --- | --- |
| M1 — single vertical slice | The listed PA → SDK/core → Gateway/IM → frontend → docs sequence is an appropriate unsplit vertical delivery and contains focused tests. It omits the provider mapper adapter file/test required by [R1-C1], and it names production updates without an exact per-node capability inventory or executable rollout verification required by [R1-W1]. |

### Overall design check

The design does not contain template placeholders, speculative compatibility layers, or an IM vendor policy leak. Its selector/fixed/no-model states match the prototype and the current forms. The principal missing work is not UI detail: it is the two boundary contracts at which a user-visible saved selection becomes either a provider wire value or a truthful distributed mutation result.

### Architecture attack

| Angle | Attack and evidence | Result / long-term cost |
| --- | --- | --- |
| Ownership | The PA catalog is the correct owner because it already owns configuration, reporter capability construction, profile sync, and runtime projection. IM should receive only descriptors, consistent with `SPEC.md:53-64,117-124`. Provider request syntax, however, belongs in `agent.platform` mapper code, not in IM or an arbitrary PA dictionary. | **[R1-C1].** Leaving protocol syntax in a universal catalog/runtime value makes every new provider a silent product regression or forces vendor knowledge back into higher layers. |
| Should this exist? / deletion test | A single validated catalog survives deletion of duplicated checks in config load, reporter, sync, and UI; it earns its abstraction. A separate persistent “reasoning service” or IM capability cache is unnecessary and is correctly absent. | No issue. Keep the catalog small and immutable as proposed. |
| Deep interface vs shallow pass-through | `capability_for` / `resolve` / `validate` provide a useful domain interface. A raw `model_request_extra_body` is a legitimate transport seam only if the provider adapter owns conversion from the normalized domain choice. Today D3 ends in generic `payload.update`. | **[R1-C1].** The present seam is shallow at the protocol boundary, obscuring an essential adapter responsibility. |
| Root cause vs local patch | The requirement is a truthful save transition against a live, node-specific catalog. Adding a check after IM’s durable write, or relying on asynchronous config sync, patches the symptom while preserving a successful stale save. Current IM writes first (`config_service.py:203-219`) and Gateway sync later (`agent_config_sync.py:134-156`). | **[R1-C2].** Without an acknowledged pre-write/apply operation, failures leave split durable state, stale UI success, and old runtime behaviour. |

### Issues

#### [R1-C1] CRITICAL — Universal request body conflicts with the actual Anthropic provider protocol

**Where:** D1 “user selection converts to `{"reasoning_effort": level}`”, D3 transport, data flow, and M1 scope.

**Evidence:** The actual PA/e2e model entries use `provider: anthropic` (`config/e2e/gateway.yaml:41-54`). `src/agent/platform/llm/providers/anthropic/mapper.py:80-89` generically merges `LLMGenerateRequest.extra_body` into the Anthropic payload; it does not translate `reasoning_effort`. The production LLM proxy’s Anthropic-to-Codex conversion reads `output_config.effort` (`/Users/czj/Repos/LLM_PROXY/src/handlers/messages.py:361-368`), and direct DeepSeek’s documented Anthropic-compatible request uses `output_config.effort`, whereas only its OpenAI-compatible request uses top-level `reasoning_effort` ([official documentation](https://api-docs.deepseek.com/guides/thinking_mode)).

**Required design correction:** Define a normalized resolved domain value and the final provider-adapter rendering. For example, PA/SDK may carry the normalized effort while `AnthropicMapper` renders `output_config.effort` and the OpenAI-compatible mapper renders top-level `reasoning_effort`; choose and document the exact merge/override semantics with static `extra_request_body`. Add the necessary platform mapper file(s) and packet-level tests to M1. Prove both the direct DeepSeek route and the Anthropic-to-Codex proxy route, plus ordinary/background call origins, produce the intended provider body without changing tool-approval calls.

**If not fixed:** Web IM can show and persist a choice/default that the deployed models ignore or reject. That violates R1/S1, R3/S6, and the central product promise while appearing successful to the user.

#### [R1-C2] CRITICAL — No implementable acknowledged write protocol for live capability validation

**Where:** D4 profile persistence, D5 live validation/stale `409`, data-flow step “Gateway validation → persistence”, and M1 Gateway/IM work.

**Evidence:** Today `ConfigService.update_profile` persists the IM profile and then triggers config sync (`src/IM/application/config_service.py:169-219`); the API PATCH returns through `src/IM/api/routes/agents.py:399-445`. Gateway’s `IMAgentConfigSync` subsequently reads the mirror and persists its local config (`src/personal_assistant/gateway/agent_config_sync.py:134-160,523-621`), with no synchronous validation acknowledgement back to IM. The detail form treats a successful PATCH as saved (`src/IM/frontend/src/features/agents/agent-detail-page.tsx:1303-1348`). D5 says validation must be live and pre-persist, but does not define an RPC/API, ownership of the durable write, or race/error state that achieves it.

**Required design correction:** Pin one complete mutation protocol before M1. At minimum, specify the synchronous Gateway capability-validation operation IM calls before writing and the expected error mapping; if Gateway’s “final validation” is to be authoritative, specify how its successful durable apply is acknowledged before IM exposes saved state (or how an explicitly defined compensating state/rollback maintains the profile/runtime invariant). Cover the same protocol for node-agent create, existing-agent update, catalog refresh between open/save, and a concurrent capability change. Update the sequence diagram, API contract/deltas as necessary, M1 files, and end-to-end tests.

**If not fixed:** A stale or invalid choice can be durably saved in IM and reported as successful while Gateway rejects it and continues using the old runtime setting. This directly fails R1/S3 and R3/S8 and creates divergent cross-channel configuration state.

#### [R1-W1] WARNING — Production configuration delivery is not specific or executable enough

**Where:** D1 example schema, M1 production-config scope, and “runbook / rollback”.

**Evidence:** The requirement explicitly promises deployer-controlled per-model capabilities and configuration updates on both nodes. The two production nodes have distinct config/upstream paths (`docs/operations/prod-fleet.md:8-29`), while the design gives illustrative identifiers rather than an exact node/model/mode/default/levels inventory. Its e2e commands are concrete, but the production phase merely says to stop Gateways, edit config, restart, and verify health/node/capabilities; it does not identify target config records or the operational commands/skill entrypoint that make that safe.

**Required design correction:** Add a non-secret release matrix with the exact configured model identifier per node, capability mode (`selectable` / `fixed` / absent), allowed/default level, and upstream route. Add the concrete production rollout and verification procedure (or an explicit `prod-fleet-deploy` skill invocation plus the required health, node, and capability observations), including rollback of the same fields.

**If not fixed:** M1 can pass local/e2e tests yet leave an operator unable to determine which strengths are promised on each live node, or deploy a mismatched capability catalog and falsely advertise unsupported control.

### Recommendations

- [R1-R1] After resolving [R1-C1], keep one narrow request-capture test at the provider payload boundary rather than treating a populated `LLMGenerateRequest.extra_body` as proof of provider behaviour.
- [R1-R2] Give stale capability conflicts a stable, user-safe error code in the Gateway/IM contract so create and edit forms can preserve drafts without matching free-form error text.

### Author Resolutions

| Issue | Resolution | Evidence |
|---|---|---|
| R1-C1 | Accepted. The configuration remains only `default + levels`, but the resolved value is now provider-neutral `reasoning_effort` in SDK runtime/request DTOs. Provider mappers own final rendering: Anthropic writes `output_config.effort`; OpenAI-compatible writes top-level `reasoning_effort`; dynamic value overrides only the same effort key after static body merge. | `design.md` 决策 1/2/3、运行时数据流、runbook、M1 scope；`specs/kernel/model-runtime.md` |
| R1-C2 | Accepted. Existing-agent save is now an acknowledged `agent.config.apply` Gateway RPC before IM CAS persistence, with a per-agent serialized path and explicit old-profile compensation if CAS loses. Create remains Gateway create ACK before IM profile creation. Legacy asynchronous `config.sync` is no longer a UI save success condition. | `design.md` 决策 5、IM 写入与 ACK、M1 scope；IM/Gateway delta specs |
| R1-W1 | Accepted. Added a non-secret matrix directly grounded in the two live Gateway model catalogs, including deliberate absence for unverified `codex_oauth:gpt-5.5`, and concrete target-Gateway-only release and verification sequence. | `design.md` 生产能力矩阵与发布边界、Runbook、M1 exit criteria |

## Round 2

### Metadata

- reviewer: `/root/feat514_design_reviewer`
- review_mode: `full`
- mode_reason: `delta` was initially plausible, but the revised clarification/spec, provider-neutral SDK request contract, Gateway↔IM acknowledged mutation protocol, and production delivery boundary together change shared cross-package interfaces and the durable data flow. Per the reviewer rule this Round is upgraded to `full`.
- started_at: `2026-08-07T14:39:00+08:00`
- completed_at: `2026-08-07T14:55:46+08:00`
- duration: `00:16:46`

### Verdict

**Issues Found — 2 CRITICAL / 1 WARNING.** R1-C1 is closed: the design now keeps a normalized domain value through SDK/runtime and renders it at the provider boundary. R1-C2 is closed for deterministic catalog rejection and IM CAS loss. The revised acknowledged-write design still leaves an unknown-outcome window after Gateway persistence, and its OpenAI-compatible static-body claim has no production path in the current client. Those are implementation-blocking interfaces, not test-detail omissions.

### Coverage

| Surface | This-round evidence | Result |
| --- | --- | --- |
| Complete unit input | Re-read current `spec.md`, all 353 lines of `design.md`, `prototype.html`, three delta specs, and R1 plus Author Resolutions | Full inventory below; no template residue or conflict between prototype and declared four UI states. |
| Runtime/provider wiring | SDK runtime/kernel, Agent loop, model registry/factory, Anthropic and OpenAI-compatible clients/mappers | Provider-neutral field is correctly owned below PA; OpenAI static-extra path is absent, see [R2-C2]. |
| Gateway/IM mutation wiring | IM WS control/runtime, PA IM connection/config sync, ConfigService, agent/node routes and repositories | Existing RPCs have a timeout-as-unknown result after a remote side effect; revised D5 has no recovery contract, see [R2-C1]. |
| Current and live deployment evidence | `docs/operations/{gateway,prod-fleet}.md`, local and Mac mini non-secret model-name inventories | Matrix exactly covers the observed Mini subset and MacBook-only entries; deployment procedure remains partly non-executable, see [R2-W1]. |
| External protocol sources | [DeepSeek Anthropic API](https://api-docs.deepseek.com/guides/anthropic_api), [Kimi Code model configuration](https://www.kimi.com/code/docs/en/kimi-code/models.html), local LLM proxy converter/README | Confirms Anthropic-compatible effort rendering for the deployed DeepSeek/Kimi/Codex-proxy routes and the declared DeepSeek/K3 levels. |

### Verification ledger

#### Current-state assertions

| ID | Rechecked assertion | Evidence / result |
| --- | --- | --- |
| C1 | Node LLM catalog owns static model request extras but no selectable reasoning descriptor. | `src/personal_assistant/config/local_store.py:29-36,1035-1062` and SDK catalog initialization at `src/agent/sdk/kernel.py:337-391`. **Verified.** |
| C2 | Complete session runtime currently owns model/prompt/skills/tools/features and has one durable identity/reconfigure chain. | `src/agent/sdk/runtime.py:17-102`, `src/agent/sdk/kernel.py:980-1194`, and `src/personal_assistant/gateway/session_composition.py:38-65`. **Verified.** |
| C3 | Static model extras reach the Anthropic adapter before mapping. | `src/agent/platform/llm/providers/anthropic/client.py:62-73` resolves metadata and merges extras. **Verified.** The corresponding OpenAI-compatible premise is false; see [R2-C2]. |
| C4 | Reporter projects the model catalog to IM while IM consumes descriptor-shaped candidates. | `src/personal_assistant/reporter/upstream_reporter.py:23-62,143-195`; `src/IM/api/routes/agents.py:348-396`. **Verified.** |
| C5 | Package ownership remains PA → `agent.sdk`, while IM does not import `agent`. | `SPEC.md:53-64,85,117-124,148-161`. **Verified; D2/D3 preserve it.** |
| C6 | Current runtime changes are projected before a later admission and do not interrupt an active run. | `src/personal_assistant/gateway/session_run_coordinator.py:1195-1252`; `src/personal_assistant/gateway/kernel_client.py:129-219`. **Verified.** |
| C7 | Normal/heartbeat/cron reuse the projected runtime. | `src/personal_assistant/gateway/kernel_client.py:74-84,129-219`; `session_binder.py:416-480`. **Verified.** |
| C8 | Current IM update persists first and asynchronously sends `config.sync`. | `src/IM/application/config_service.py:169-219`; `src/IM/api/routes/agents.py:399-445`. **Verified; D5 intentionally replaces this UI mutation path.** |
| C9 | Current control RPC waiters return `None` on an unsent frame or timeout and then delete their waiter. | `src/IM/ws/gateway/control.py:94-120,122-148`. **Verified; this makes an ACK timeout an unknown remote outcome, not a rejected apply.** |
| C10 | Gateway currently performs create’s local side effect before sending the correlated result frame. | `src/personal_assistant/ws/im_connection.py:1034-1051`. **Verified; the same ordering is proposed for apply and is relevant to [R2-C1].** |
| C11 | Native create/detail form structure and the prototype’s selectable/fixed/default/stale states align. | `src/IM/frontend/src/features/agents/agent-create-page.tsx:401-421,481-491,725-754`; `agent-detail-page.tsx:1303-1348,1482-1842`; `prototype.html:71-99`. **Verified.** |

#### Decisions and data flow

| Decision / flow | Review result and evidence |
| --- | --- |
| D1 — minimal configured levels/default/fixed | **Covered.** It keeps provider JSON out of config. Direct DeepSeek’s Anthropic contract uses `output_config.effort`; Kimi K3 documents `low`/`high`/`max` effort support, matching the matrix. |
| D2 — PA `ModelReasoningCatalog` | **Covered.** One immutable catalog serves capability, validation, and projection without leaking vendor rules into IM or SDK. |
| D3 — provider-neutral `reasoning_effort` in SDK runtime/request | **Partially covered.** Its ownership, complete-runtime round trip, Anthropic nested merge, tool-approval isolation and packet-level intent close R1-C1. The OpenAI-compatible static merge claim has no real client path; [R2-C2]. |
| D4 — profile persistence/legacy behavior | **Covered.** Null legacy values resolve only at runtime/UI default; fixed/absent pairs clear values, and Gateway validation remains the API-bypass guard. |
| D5 — apply ACK → IM CAS → compensation | **Partially covered.** It precisely handles catalog rejection and a known CAS conflict, closing R1-C2’s stated ordering gap. It has no state machine for lost ACK, IM crash, or compensation-result loss after Gateway persistence; [R2-C1]. |
| D6 — dependent configuration group | **Covered.** Selector/default/fixed/absent/stale behavior maps directly to spec and does not invent a model-specific UI branch. |
| Runtime data flow | **Covered except [R2-C2].** `AgentWorkspaceConfig → catalog → SessionRuntimeConfig → AgentLoop → LLMGenerateRequest → mapper` follows current production admission ownership. |
| IM write/ACK data flow | **Covered for known success/rejection/CAS failure; incomplete for uncertain completion, [R2-C1].** |

#### Requirements, clarifications, and non-goals

| Source item | Design coverage / conclusion |
| --- | --- |
| R1 selectable selector + recommended default | D1/D2/D5/D6 and capability delta specify the declared levels/default. **Covered subject to [R2-C2] for an OpenAI-compatible static model route.** |
| R1 no explicit model means no isolated effort save | D4 clears stored effort and D6 blocks isolated edit. **Covered.** |
| R1 stale catalog means no success and refresh/reselect | D5 maps a current-catalog rejection to 409; D6 retains the draft. **Covered for an explicit rejection; an ACK timeout remains inconsistent under [R2-C1].** |
| R2 fixed informational state | D1 fixed descriptor and D6/prototype use a read-only explanation, not a disabled select. **Covered.** |
| R2 selectable → fixed clears invalid effort | D2 validation and D4 normalization make fixed accept only `None`. **Covered.** |
| R3 create persists model+effort and first reply uses it | Create validates before Gateway local persistence; D3/D4 project the chosen pair into first runtime. **Covered for acknowledged success; unknown create result must be included in [R2-C1] recovery.** |
| R3 existing conversation switches only on a next run | D3 runtime identity and current coordinator evidence preserve active run/history. **Covered.** |
| R3 save failure retains draft and does not claim success | D5/D6 specify rejected/409 and 503 presentation. **Not fully covered: a 503 after applied local config leaves the UI draft/old profile but Gateway uses the candidate; [R2-C1].** |
| R4 config changes/new node-only model do not require frontend release | D1/D2/D5 capability descriptor remains per Gateway/node; frontend only reads descriptor. **Covered.** |
| Q1 commercial fixed presentation | D6/prototype exact wording and no fake selector. **Covered.** |
| Q2 grouped next-run semantics | D3/D4 reuse existing durable reconfigure. **Covered.** |
| Q3 deployer catalog, normalized field, retain static extras, Gateway protocol owner | D1-D5 obey the ownership split. **Static-extra retention on OpenAI-compatible client remains unclosed, [R2-C2].** |
| Non-goals: per-message override / upstream JSON / fabricated values / tool-approval behavior | Field is profile/runtime-bound; IM sees only descriptors; catalog is config-driven; D3 sets `None` for independent approval calls. **Respected.** |

#### Delta specifications

| Delta item | Review result |
| --- | --- |
| Kernel ADDED complete-runtime `reasoning_effort` | Correct consumer-facing level and create/read/fork/reconfigure/normal-call scenarios. The provider-adapter THEN is right; its OpenAI static-extra precondition needs [R2-C2]. |
| Gateway MODIFIED selected model on each new reply | Preserves all existing new-run/history/in-flight/default/background scenarios and adds effort as part of the complete runtime. **Covered.** |
| Gateway ADDED capability + apply ACK | Correctly makes catalog validation observable and rejects fixed/stale values without a local write. Missing uncertain-outcome recovery is [R2-C1]. |
| IM MODIFIED profile update | Correctly anchors the existing optimistic-lock requirement and adds ACK-before-profile/CAS compensation scenarios. It needs an unknown-operation outcome rather than treating timeout as an ordinary failed save; [R2-C1]. |
| IM MODIFIED live capabilities | Correctly keeps capability descriptors live, safe and node-scoped, with selectable/fixed/absent UI semantics. **Covered.** |

#### Milestone

| Milestone | Review result |
| --- | --- |
| M1 single vertical slice | The one M is justified: config, profile, ACK, runtime, provider wire, and two pages cannot be separately user-valuable. Scope now includes both mappers and the desired tests, but must add the OpenAI-compatible client/static-origin path ([R2-C2]) and the durable/idempotent recovery surface for apply/create ([R2-C1]). Production matrix is verified against non-secret model-name inventories; runbook residual is [R2-W1]. |

### Overall design check

The human-readable architecture narrative, sequence diagram, six decisions, prototype contract, risks and one vertical M now tell one coherent product story. Delta requirements remain correctly anchored to the canonical consumer contracts. The two remaining criticals are both missing failure-boundary decisions: one between model metadata and the OpenAI-compatible mapper, one between a Gateway side effect and a possibly lost acknowledgement.

### Architecture attack

| Angle | Attack / evidence | Result / long-term cost |
| --- | --- | --- |
| Ownership | PA owns catalog/profile projection; SDK owns normalized future-request transport; provider clients/mappers own protocol rendering; IM owns browser/profile CAS. This respects `SPEC.md` boundaries. The OpenAI client is the current metadata-to-request owner, but D3 places all static merge in its mapper. | **[R2-C2].** Treating a mapper as metadata owner makes static behavior depend on test setup rather than the registered model, and future provider support will duplicate the same blind spot. |
| Should this exist? | The catalog and one correlated apply operation earn their existence: they remove duplicated model interpretation and replace a false-saved async path. A separate capability cache/service is still correctly absent. | No new abstraction issue. An idempotency/outcome record in [R2-C1] is justified by a remote durable side effect, not speculative retry machinery. |
| Deep vs shallow/reuse | D2’s three semantic operations are deep and compact. Reusing existing correlated WS request IDs is reasonable, but a bare correlation ID is a shallow transport detail: it does not state whether a timed-out durable operation happened. | **[R2-C1].** A worker may pass the CAS test while leaving a permanent split profile/runtime after a routine reconnect. |
| Root cause vs patch | D5 addresses the original wrong write order directly. Compensating only an observed CAS failure is a partial patch because the real distributed boundary also fails after apply/before ACK or during IM crash. The matrix fixes R1-W1’s inventory root cause, but “start/check lifecycle” remains prose. | **[R2-C1]** and **[R2-W1]** as stated below. |

### Historical issue closure

| Historical item | Author resolution | This-round verification | Status |
| --- | --- | --- |
| R1-C1 | Normalize `reasoning_effort`; render it in Anthropic/OpenAI-compatible adapters. | D1/D3, kernel delta and M1 now name the real adapter boundary. DeepSeek documents Anthropic `output_config.effort`; Kimi K3 documents the selected three levels; local proxy converts Anthropic `output_config.effort` for Codex. | **Closed.** |
| R1-C2 | Gateway apply ACK before IM CAS plus compensation on CAS loss. | D5 and IM/Gateway deltas define Gateway-first validation, profile CAS, stable 409/503 mapping, and known-CAS compensation. | **Closed for the original deterministic stale/CAS paths; [R2-C1] is a newly discovered uncertain-outcome path.** |
| R1-W1 | Add node/model matrix and production procedure. | Matrix matches the locally inspected MacBook and Mac mini non-secret model inventories; it preserves absent unverified entries and static flags. | **Partially closed; carried forward narrowly as [R2-W1] because start and availability commands are still not copyable.** |

### Issues

#### [R2-C1] CRITICAL — ACK protocol has no recovery for a durable apply with an unknown result

**Where:** D5, “IM 写入与 ACK”, Gateway/IM apply delta scenarios, and M1 RPC scope.

**Evidence:** D5 applies/publishes Gateway local config before it returns an ACK (`design.md:181-192`). Existing correlated control calls return `None` after a five-second timeout and remove their waiter (`src/IM/ws/gateway/control.py:122-148`); Gateway creation already performs its local side effect before it emits the correlated response frame (`src/personal_assistant/ws/im_connection.py:1034-1051`). D5 defines compensation only after a known IM CAS failure. It maps timeout to 503 but does not define whether IM queries/retries an idempotent operation, compensates, or records a recoverable pending state. A dropped reply or IM crash in that interval therefore leaves Gateway on candidate C while IM/profile/UI remain at old A and report save failure.

**Required design correction:** Define the outcome contract for both `agent.config.apply` and the create path: an operation identity with Gateway idempotency/status recovery (and any necessary precondition), the IM state after send/timeout/reconnect/crash, and exactly when compensation is attempted or deferred. Add its success/rejected/unknown/recovered observations to Gateway and IM deltas, the sequence diagram, risks, M1 scope, and end-to-end tests. The terminal state must never be “HTTP failed / old profile displayed / candidate runtime silently active.”

**If not fixed:** A normal WebSocket timeout produces the precise false state the feature was designed to remove: the user keeps an unsaved draft or sees old settings, while the next reply uses a new unacknowledged model/effort. Retrying can then overwrite an unknown state, and worker tests limited to CAS loss will miss it.

#### [R2-C2] CRITICAL — OpenAI-compatible static `extra_request_body` has no actual merge path

**Where:** D3’s “OpenAI-compatible mapper after static body merge”, Q3 static-extra promise, Runbook packet assertion, and M1 provider scope.

**Evidence:** Normal agent turns build `LLMGenerateRequest` with model/messages/tools only (`src/agent/core/agent/loop.py:370-381`). The Anthropic client resolves the model registry and merges its static extra body before mapping (`src/agent/platform/llm/providers/anthropic/client.py:62-73`). In contrast, `OpenAICompatClient.generate` only fills a missing model and immediately calls its mapper (`src/agent/platform/llm/providers/openai_compat/client.py:53-60`); `OpenAICompatMapper` can merge only a caller-provided `request.extra_body` (`mapper.py:42-44`). It never receives the registered model’s `extra_request_body`. M1 lists `openai_compat/mapper.py`, but not the client/shared pre-mapper merge point.

**Required design correction:** Choose and document the one provider-client-level static-extra merge seam for OpenAI-compatible calls (parallel to Anthropic, or a shared helper), then have the mapper render dynamic `reasoning_effort` after that merge. Add the actual client/shared file to M1. Require a normal AgentLoop/model-registry test with a configured OpenAI-compatible model carrying static extras; a manually constructed `LLMGenerateRequest.extra_body` is insufficient proof.

**If not fixed:** The documented OpenAI-compatible path will drop configured static protocol flags, and the claimed dynamic-over-static effort precedence can pass a mapper unit test while failing in a real configured runtime. This violates Q3’s retention of static `extra_request_body` and leaves future/provider-specific models with an invisible regression.

#### [R2-W1] WARNING — Production procedure still omits copyable start and availability checks

**Where:** “生产能力矩阵与发布边界” and production section of the reviewer runbook.

**Evidence:** The matrix and stop command are now concrete (`design.md:293-309`), but step 3 only says to start with the same config and step 4 names lifecycle/log/node observations without commands (`design.md:310-313`). The reviewer runbook repeats “restart and confirm health/node identity/capability” without the concrete commands (`design.md:340-343`). The current supported lifecycle commands are explicitly documented in `docs/operations/gateway.md:62-98`, including start/restart for a target config and the required `.gateway-state.json`, log, IM-node and real-message observations.

**Required design correction:** Keep the non-secret matrix, then replace the remaining prose with the target-config start/restart command for each host and an executable observation sequence (state file/log, IM node status/capability, and one message). An explicit reference to the exact `prod-fleet-deploy` local-action entry is also acceptable if it carries those commands.

**If not fixed:** An implementer can make the correct configuration edit but leave one Gateway stopped or call a broad fleet action, while the documented release still appears complete. This is a recoverable delivery risk, not a change to the architecture.

### Recommendations

- [R2-R1] Preserve R1-R1’s packet-level proof, but make the static-extra origin test provider-client based as required by [R2-C2].
- [R2-R2] Keep one stable machine-readable rejected/unknown error code in the apply result so both create and edit forms can retain their draft without matching prose.

### Author Resolutions

| Issue | Resolution | Evidence |
|---|---|---|
| R2-C1 | Accepted. Gateway create/apply now use a stable `operation_id` and candidate fingerprint, with durable non-secret receipt/status recovery. IM durably records a pending operation before send; dropped results, reconnect and restart recover through retry/status rather than interpreting timeout as failure. The only unknown UI/API state is `503 config_apply_pending`, which preserves the draft, disables repeated save, and never renders the old profile as confirmed. CAS compensation is itself a recoverable operation. | `design.md` 决策 5、IM 可恢复写入与 ACK、风险、原型契约、Runbook、M1；IM/Gateway delta specs；`prototype.html` confirmation state |
| R2-C2 | Accepted. Static registered model request body is explicitly merged in the provider-client path for both Anthropic and OpenAI-compatible before either mapper renders dynamic effort. A shared client-level helper is allowed, and the M1 scope/test requires a normal AgentLoop → registered OpenAI-compatible model proof rather than a manually populated DTO test. | `design.md` 决策 3、Runbook、M1；M1 scope names `request_body.py` and both clients/mappers |
| R2-W1 | Accepted. The release section now has host-specific stop/start commands, state/log/capability observations, a local `:8011` guard, real Web IM verification, and an exact rollback sequence while keeping tokens and secrets out of output. | `design.md` 生产能力矩阵与发布边界 |

## Round 3

### Metadata

- reviewer: `/root/feat514_design_reviewer`
- review_mode: `full`
- mode_reason: `R2` introduces an IM-persisted pending operation, Gateway durable receipt/status protocol, restart recovery, and compensation. Those are new shared durable interfaces and a changed cross-process mutation boundary, so the same-reviewer follow-up rule requires a full review rather than a delta-only pass.
- started_at: `2026-08-07T15:06:39+08:00`
- completed_at: `2026-08-07T15:09:12+08:00`
- duration: `00:02:33`

### Verdict

**Issues Found — 1 CRITICAL / 0 WARNING.** R2-C2 is closed: static registered request-body data now has an explicit provider-client merge seam for both adapter families, and the M1 proof starts from an actual registered model. R2-W1 is closed: the release matrix and host-specific stop/start, listener, state/log, capability, and real-message checks are executable without disclosing credentials. R2-C1's durable-operation approach is necessary and proportionate, but its receipt is still written *after* Gateway changes durable configuration and publishes it. A Gateway crash in that interval makes the operation unrecoverable exactly where the new protocol promises recovery, so Gate 2 remains blocked.

### Coverage

| Surface | This-round evidence | Result |
| --- | --- | --- |
| Complete unit input | Re-read `spec.md`, all 421 lines of `design.md`, `prototype.html`, all three delta specs, R1/R2 findings, and the R2 Author Resolutions. | Full inventory; the confirmation prototype, deltas, data flow, risks, runbook, and M1 all reflect the new operation contract. |
| Gateway durable-write boundary | Current `AgentConfigSync`, `RuntimeConfigOwner`, Gateway control RPC flow, and the revised D5/operation delta. | Local config persists before in-process publication, while D5 puts the separate receipt after both; [R3-C1]. |
| Provider request boundary | Model registry, Anthropic/OpenAI-compatible clients and mappers, D3, runbook, and M1 scope. | The requested shared/client-level low-priority static merge plus high-priority request body and mapper-level dynamic effort precedence is explicit. **R2-C2 closed.** |
| IM pending/recovery/compensation | Revised D5, IM/Gateway deltas, confirmation prototype, and M1 test exit criteria. | Correctly covers lost result frames, IM restart, reconnect, applied/rejected/unreachable states, CAS compensation, and UI truthfulness, subject only to Gateway's pre-receipt crash window in [R3-C1]. |
| Production delivery | Matrix plus `docs/operations/{gateway,prod-fleet}.md` lifecycle contract and revised release/runbook commands. | Both host paths are concrete, scoped, and include rollback observations. **R2-W1 closed.** |

### Verification ledger

#### Current-state assertions

| ID | Rechecked assertion | Evidence / result |
| --- | --- | --- |
| C1 | Current Gateway config persistence is a distinct durable YAML write before the in-memory/live publication. | `src/personal_assistant/gateway/agent_config_sync.py:584-626` and `src/personal_assistant/config/local_store.py:357-370`. **Verified.** This is the recovery boundary relevant to [R3-C1]. |
| C2 | Correlated control requests can lose their response after a remote side effect. | `src/IM/ws/gateway/control.py:94-148` and `src/personal_assistant/ws/im_connection.py:1034-1051`. **Verified.** A timeout is not evidence of rejection. |
| C3 | The registered model is where static `extra_request_body` originates, and today Anthropic but not OpenAI-compatible resolves it before mapping. | `src/agent/core/llm/model_registry.py`, `src/agent/platform/llm/providers/anthropic/client.py:62-73`, and `src/agent/platform/llm/providers/openai_compat/client.py:53-60`. **Verified.** D3 now places the missing merge at the correct client/shared seam. |
| C4 | Runtime configuration remains a complete, future-run identity that does not interrupt an active run. | `src/agent/sdk/runtime.py:17-102`, `src/agent/sdk/kernel.py:980-1194`, and `src/personal_assistant/gateway/session_run_coordinator.py:1195-1252`. **Verified; D3 remains aligned.** |
| C5 | Product boundaries remain PA -> `agent.sdk`, with IM independent of `agent`. | `SPEC.md:53-64,85,117-124,148-161`. **Verified; the revised owner split preserves it.** |
| C6 | Production topology has mini as the only IM `:8011` host and separate Gateway lifecycle/config ownership per host. | `docs/operations/prod-fleet.md:1-50` and `docs/operations/gateway.md:62-98`. **Verified; the revised commands preserve that scope.** |

#### Decisions and data flow

| Decision / flow | Review result and evidence |
| --- | --- |
| D1 — configured levels/default/fixed | **Covered.** It remains deployer-configured and does not expose provider JSON. |
| D2 — PA `ModelReasoningCatalog` | **Covered.** One catalog still owns validation, projection, and effective-value resolution. |
| D3 — normalized runtime field and static-body merge | **Covered.** The two clients merge registered static body at low priority, then request body at high priority; both mappers render the dynamic effort last. The runbook/M1 require registered-model, packet-level proof. **R2-C2 closed.** |
| D4 — profile persistence and legacy behavior | **Covered.** Nullable profile/config values, fixed/absent clearing, and Gateway-side validation retain the intended ownership. |
| D5 — pending operation, receipt/status, CAS, compensation | **Partially covered.** IM's pending state, status recovery, 503 presentation, and compensation state are well specified. Gateway records the terminal receipt only after local persist and publish (`design.md:186-192`), leaving [R3-C1]. |
| D6 — dependent UI group | **Covered.** The fifth confirmation state preserves the draft and disables repeated saves without inventing another model-specific form branch. |
| IM write/recovery flow | **Covered after a terminal receipt exists.** Applied/rejected/unknown results have a single user-safe interpretation; the pre-receipt outcome has none. |

#### Requirements, clarifications, and non-goals

| Source item | Design coverage / conclusion |
| --- | --- |
| R1 selectable levels/default; no isolated model-default effort; stale catalog | D1/D2/D4/D6 and Gateway apply validation meet the selector, default, and explicit 409 semantics. **Covered.** |
| R2 fixed display and selectable-to-fixed clearing | Fixed is informational rather than a fake disabled selector; invalid saved effort becomes `None`. **Covered.** |
| R3 create first turn; existing next turn; failure retains understandable draft | D3/D4 preserve complete-runtime/new-run behavior; D5/D6 preserve the pending draft and never show old profile as saved. The claim is incomplete only if Gateway crashes after applying but before recording the receipt; [R3-C1]. |
| R4 node-configured capability / no frontend release | Capability remains node-scoped and descriptor-only. **Covered.** |
| Q1 commercial fixed treatment; Q2 grouped next-run semantics | Prototype/D6 and complete-runtime projection respectively. **Covered.** |
| Q3 deployer catalog, provider-neutral value, retain static extras, Gateway ownership | D1-D5 plus the shared provider-client seam satisfy all four ownership points. **Covered.** |
| Non-goals: per-message override, upstream JSON in UI, invented values, tool-approval change | D3 confines the value to normal runtime requests and explicitly leaves approval calls at `None`; IM receives only safe descriptors. **Respected.** |

#### Delta specifications

| Delta item | Review result |
| --- | --- |
| Kernel complete runtime | `reasoning_effort` is correctly future-normal-request state through create/read/fork/reconfigure, without hook/approval leakage. **Covered.** |
| Gateway capability and operation recovery | The added receipt/status scenarios cover terminal applied/rejected replay, but say the receipt may be written before or after success without defining recovery for an after-side-effect crash. **[R3-C1].** |
| IM profile update and create recovery | The pending-operation, 409/503, and create-result scenarios correctly consume a terminal Gateway result. **Covered conditional on [R3-C1].** |
| IM live capabilities | Safe selectable/fixed/absent descriptors and model-dependent form semantics remain complete. **Covered.** |

#### Milestone

| Milestone | Review result |
| --- | --- |
| M1 single vertical slice | The coupled vertical scope remains justified and now names the static merge helper, both clients, operation repository, receipt store, and recovery/UI tests. It must add crash/restart injection at every receipt/config/publish boundary and a deterministic recovery assertion for create and apply; [R3-C1]. |

### Overall design check

The design now has a coherent, appropriately narrow answer to the user-visible truth problem: IM records intent, Gateway owns capability validation and durable application, IM commits profile only after a recoverable terminal result, and the UI has an honest confirmation state. This is not over-designed: a short operation record and receipt are warranted by a cross-process configuration mutation with an existing lossy response channel. It must, however, order or reconcile those records so that every possible post-side-effect state has a durable interpretation. Without that, the most important promise—retrying the same operation does not silently apply or publish again—remains conditional on the Gateway surviving its own success path.

### Architecture attack

| Angle | Attack / evidence | Result / long-term cost |
| --- | --- | --- |
| Ownership | IM owns desired-profile intent/CAS; Gateway owns local config, publication, and operation outcome; provider clients own static-body merge; mappers own protocol syntax. | Good boundaries. A receipt must be owned by the same Gateway durability boundary as the config mutation, not treated as an after-the-fact notification; [R3-C1]. |
| Should this exist? | Operation ids, one pending operation, and a small receipt store directly replace the false-success/failure ambiguity. A general distributed-workflow framework is correctly absent. | The mechanism is justified, but its initial durable intent/reconciliation is essential rather than optional retry machinery; [R3-C1]. |
| Deep vs shallow/reuse | D3 now reuses the actual provider-client metadata seam and avoids mapper-only assumptions. D5 adds a focused operation contract instead of overloading a transient WS correlation id. | Provider change is deep and reusable. Receipt-after-publish is shallow because it observes success rather than making that mutation recoverable; [R3-C1]. |
| Root cause vs patch | Pending 503, draft retention, and compensation solve the IM-side symptoms. The root fault also includes a Gateway process death between local config/publish and receipt persistence. | Until that exact boundary is closed, a restart can restore or re-run a change without a terminal operation result; [R3-C1]. |

### Historical issue closure

| Historical item | Author resolution | This-round verification | Status |
| --- | --- | --- |
| R1-C1 | Normalized runtime value and adapter rendering. | D3 and M1 retain actual adapter-boundary proof. | **Closed.** |
| R1-C2 | Gateway-first acknowledged write plus CAS compensation. | Superseded by the more complete durable-operation protocol; deterministic ordering remains correct. | **Closed; the remaining crash-state flaw is [R3-C1].** |
| R1-W1 | Add concrete release matrix/procedure. | Exact host-specific stop/start, local listener guard, state/log/capability, Web IM and real-message observations now appear in the design. | **Closed.** |
| R2-C1 | Durable operation id, IM pending state, Gateway receipt/status, recovery, and compensation. | The new state machine closes lost-ACK, reconnect, IM-restart, and known-CAS paths, but not a Gateway crash before receipt persistence. | **Not closed; superseded by [R3-C1].** |
| R2-C2 | Client-level static-extra merge for both providers with registered-model test. | D3, Runbook, and M1 name the common helper and both clients/mappers. | **Closed.** |
| R2-W1 | Host-specific release commands and verification. | Design now gives exact commands and verification/rollback sequence. | **Closed.** |

### Issues

#### [R3-C1] CRITICAL — Gateway records the operation only after the mutation it must recover

**Where:** D5 paragraphs 186-192 and 194-211; Gateway operation-recovery delta requirement/scenarios; risks; and M1 receipt-status/retry tests.

**Evidence:** The revised D5 directs Gateway to validate, persist local config, publish it, and *then* persist the canonical operation receipt (`design.md:186-192`). In the real owner path, the YAML config is durably saved before publication (`src/personal_assistant/gateway/agent_config_sync.py:584-626`; `src/personal_assistant/config/local_store.py:357-370`). The new `config_apply_receipts.py` is explicitly a separate M1 store. If Gateway crashes after local persist or publish but before that separate receipt reaches disk, IM has a pending operation but `operation.status` has no terminal result. Retrying the same id has no specified way to distinguish “not started” from “candidate already durable/published”; for create it may also lose the workspace-creation outcome. This contradicts D5's same-operation no-repeat claim and the delta's promised recovery of an unknown result.

**Required design correction:** Make Gateway durably establish the operation before any mutable create/apply side effect, and define the recovery transition for every durable phase. A compact receipt/intent record containing operation id, fingerprint, candidate and sufficient create identity may begin as `pending`; retry/status must reconcile it against the local-config owner and live publication, then persist exactly one terminal applied/rejected result. Alternatively, place the operation phase and config mutation in one Gateway durability boundary. In either form, define how create recovers an allocated workspace/canonical payload and how apply recovers after (a) intent write, (b) local config write, and (c) publication but before the terminal receipt. Add injected crash/restart tests for those cuts; a test that only drops the response frame after the receipt is insufficient.

**If not fixed:** A routine Gateway process death can leave the profile/API in `config_apply_pending` forever even though the candidate is durable or active, or make a retry publish/create it again. The UI remains truthful but cannot complete the save; worse, a later retry can reintroduce the exact split configuration and unintended duplicate workspace/publication that the operation protocol was introduced to prevent.

### Recommendations

- [R3-R1] Retain the narrow five-state UI test, and add a visible recovery assertion that a page reload after Gateway restart transitions from confirmation to the same saved/rejected result rather than merely removing the disabled button.

### Author Resolutions

| Issue | Resolution | Evidence |
|---|---|---|
| R3-C1 | Accepted. Gateway receipt becomes write-ahead: it first durably records `prepared` intent with candidate, expected-previous fingerprint and deterministic create identity, before any workspace/config/catalog mutation. Recovery/status serializes a candidate-vs-expected comparison inside `RuntimeConfigOwner.persist`: candidate means finish live convergence/terminal receipt, expected means apply once, a third value becomes rejected conflict. Workspace setup is explicitly idempotent. The design now requires crash/restart injection after intent, config persistence and publication, including page refresh convergence. | `design.md` 决策 5、可恢复数据流、风险、Runbook、M1；Gateway delta operation requirement/scenario |

## Round 4

### Metadata

- reviewer: `/root/feat514_design_reviewer`
- review_mode: `full`
- mode_reason: R3 changes D5 from an after-the-fact receipt to a write-ahead intent with expected-previous reconciliation, deterministic workspace identity, and new crash states. That changes the Gateway's durable creation boundary, recovery sequence, and shared IM/Gateway contract, so the follow-up rule requires a full review.
- started_at: `2026-08-07T15:13:51+08:00`
- completed_at: `2026-08-07T15:17:03+08:00`
- duration: `00:03:12`

### Verdict

**Issues Found — 1 CRITICAL / 0 WARNING. Gate 2 remains blocked.** The write-ahead `prepared` intent, candidate/expected-previous comparison, immutable create identity, terminal receipt, IM pending projection, and three operation-recovery tests are the necessary small design for a lossy cross-process mutation; they close R3-C1's original post-publication receipt hole. However, D5 now puts local-config persistence before workspace initialization, while its own recovery scenario assumes the reverse and current config startup requires the serialized workspace path to already exist. A crash in that gap can prevent Gateway from starting and therefore leave the prepared operation permanently unresolvable. This is a state-ordering contradiction, not a reason to add a broader workflow framework.

### Coverage

| Surface | This-round evidence | Result |
| --- | --- | --- |
| Complete unit input | Re-read `spec.md`, all 446 lines of `design.md`, `prototype.html`, all three delta specs, all prior rounds, and R3 Author Resolutions. | Full inventory; the revised operation protocol is propagated through D5, data flow, risk, runbook, M1, and Gateway delta. |
| Production create/config path | Gateway composition, WebSocket handler, `IMAgentConfigSync`, config serialization/loading, workspace authority, and live catalog. | The production create handler is wired directly and initializes workspace before config persistence. D5 reverses that necessary order; [R4-C1]. |
| Prepared/recovery protocol | D5, IM/Gateway deltas, control timeout semantics, operation rows/receipt scope, and all stated crash cuts. | Write-ahead intent and candidate/expected reconciliation are sound after a valid Gateway restart. The config-before-workspace cut cannot reach that recovery; [R4-C1]. |
| Runtime/provider wiring | Model registry, both provider clients/mappers, runtime/kernel/coordinator chain, D1-D4, runbook, and M1 scope. | The prior normalized-value and client-level static-extra corrections remain precise. **R1-C1/R2-C2 remain closed.** |
| UI, IM truthfulness, and delivery | Prototype, IM delta, D6, production matrix/release commands, and operations docs. | Pending confirmation, 409/503 behavior, responsive form states, and host-scoped rollout remain coherent. **R2-W1 remains closed.** |

### Verification ledger

#### Current-state assertions

| ID | Rechecked assertion | Evidence / result |
| --- | --- | --- |
| C1 | Gateway's node model directory owns static model request extras, and only Gateway/SDK adapt model requests. | `src/personal_assistant/config/local_store.py:1035-1084`, `src/agent/core/llm/model_registry.py`, and `SPEC.md:53-64,85,117-124`. **Verified.** D1-D3 preserve ownership. |
| C2 | Complete runtime remains the durable next-run boundary, while active runs retain their starting snapshot. | `src/agent/sdk/runtime.py:17-102`, `src/agent/sdk/kernel.py:980-1194`, and `src/personal_assistant/gateway/session_run_coordinator.py:1195-1252`. **Verified.** |
| C3 | Static model extras originate at the registered model; Anthropic currently resolves them before mapping whereas OpenAI-compatible needs the newly planned client/shared seam. | `src/agent/platform/llm/providers/anthropic/client.py:62-73` and `src/agent/platform/llm/providers/openai_compat/client.py:53-60`. **Verified; D3/M1 now cover both real paths.** |
| C4 | Gateway creation reaches the production `IMAgentConfigSync.handle_agent_create` handler. | `src/personal_assistant/gateway/composition.py:371-382,624-626` and `src/personal_assistant/ws/im_connection.py:1034-1051`. **Verified.** |
| C5 | Existing dynamic creation initializes the deterministic workspace before it forms/persists the Agent config. | `src/personal_assistant/gateway/agent_config_sync.py:162-235`; `ensure_workspace_defaults` creates only missing directories/default files (`src/personal_assistant/config/local_store.py:108-146`). **Verified.** |
| C6 | Every persisted Agent serializes an explicit `workspace_root`, and startup rejects a missing explicit path before it can seed defaults. | `src/personal_assistant/config/local_store.py:800-806,1087-1118`. **Verified; this makes D5's reversed order an actual restart failure, [R4-C1].** |
| C7 | Config persistence is serialized and durable before live publication; the existing convergence helper avoids a repeat publish only when the live snapshot already equals the candidate. | `src/personal_assistant/config/local_store.py:357-370`, `src/personal_assistant/gateway/agent_config_sync.py:584-626`, and `src/personal_assistant/gateway/agent_catalog.py:70-93`. **Verified.** |
| C8 | Gateway control callers can time out after a remote side effect and discard their waiter. | `src/IM/ws/gateway/control.py:94-148`. **Verified; prepared/status recovery remains required.** |
| C9 | Current create/detail pages use the same native model selection language, and the prototype's five confirmation states remain compatible with it. | `src/IM/frontend/src/features/agents/agent-create-page.tsx:401-421,725-754`, `agent-detail-page.tsx:1303-1348,1482-1842`, and `prototype.html:40-105`. **Verified.** |
| C10 | Mini is the only production IM `:8011` host; Gateways have independent target-config lifecycle. | `docs/operations/prod-fleet.md:1-50` and `docs/operations/gateway.md:62-98`. **Verified.** |

#### Decisions and data flow

| Decision / flow | Review result and evidence |
| --- | --- |
| D1 — deployer-declared default/levels/fixed | **Covered.** It keeps provider JSON out of user-facing configuration. |
| D2 — PA-owned `ModelReasoningCatalog` | **Covered.** One immutable catalog still provides capability projection, validation, and resolution. |
| D3 — provider-neutral runtime field and client static merge | **Covered.** Registered static body merges before both mappers, dynamic effort wins only its own protocol field, and approval traffic remains unchanged. |
| D4 — profile persistence/legacy resolution | **Covered.** Nullable values, fixed/absent clearing, and Gateway validation remain compatible with legacy profiles. |
| D5 — write-ahead operation and recovery | **Partially covered.** Intent-before-side-effect, expected/candidate conflict semantics, status replay, pending UI, and compensation are correct. The declared local-config -> workspace order conflicts with its restart invariant and recovery table; [R4-C1]. |
| D6 — dependent configuration group | **Covered.** Model-dependent states, stale draft, and confirmation presentation still satisfy the product contract without provider branching. |
| IM durable-pending -> Gateway -> profile CAS flow | **Covered once Gateway can recover.** Applied/rejected/unreachable outcomes remain truthful; config-before-workspace crash cannot produce one. |

#### Requirements, clarifications, and non-goals

| Source item | Design coverage / conclusion |
| --- | --- |
| R1 selectable levels/default, platform-default restriction, and stale catalog | D1/D2/D4/D6 plus Gateway validation provide declared choices, no isolated effort save, and a draft-preserving conflict. **Covered.** |
| R2 fixed treatment and selected-to-fixed clearing | Fixed remains a clear informational state and stored selectable effort is cleared. **Covered.** |
| R3 create first turn, existing next turn, and understandable failure state | D3/D4 preserve complete-runtime timing; D5/D6 make loss-of-result confirmation truthful. Create cannot recover after D5's config-before-workspace crash; [R4-C1]. |
| R4 node-driven capabilities without frontend release | Per-node descriptors continue to drive the form. **Covered.** |
| Q1 commercial fixed state / Q2 grouped next-run behavior / Q3 deployer catalog and static extras | D1-D6, prototype, provider seam, and operations matrix cover each committed intent. **Covered.** |
| Non-goals: message override, leaked upstream JSON, invented levels, approval-model behavior | The choice is profile/runtime-bound, descriptor-only in IM, config-declared, and omitted from approval calls. **Respected.** |

#### Delta specifications

| Delta item | Review result |
| --- | --- |
| Kernel ADDED complete runtime | Create/read/fork/reconfigure and normal-request-only semantics remain exact. **Covered.** |
| Gateway MODIFIED next-run configuration | Model/effort grouping, active-run preservation, default and background-run behavior remain preserved. **Covered.** |
| Gateway ADDED capability and operation recovery | The write-ahead requirement is correctly anchored, but its crash scenario says workspace occurs before config while D5 orders it after; [R4-C1]. |
| IM MODIFIED profile update/recovery | Pending profile, optimistic CAS, compensation, and create-result recovery are correct conditional on a recoverable Gateway result. **Covered conditional on [R4-C1].** |
| IM MODIFIED live capabilities | Safe selectable/fixed/absent descriptors and form behavior remain complete. **Covered.** |

#### Milestone

| Milestone | Review result |
| --- | --- |
| M1 single vertical slice | One M remains justified: configuration, Gateway mutation, profile, runtime, provider request, and two product surfaces only prove value together. It names all necessary production owners and direct tests, but must make the workspace-before-config transition and its restart assertions unambiguous; [R4-C1]. |

### Overall design check

The revised architecture now correctly treats a Gateway mutation as an operation rather than as a transport reply. Its added state is narrowly scoped: one durable intent, one candidate/expected reconciliation, one terminal receipt, and IM's existing-style pending presentation. The remaining defect is a single unsafe ordering in the create path. It is especially important because no amount of status retry can repair a Gateway process that cannot parse its own just-written configuration. Reordering the existing idempotent workspace initialization after `prepared` but before local-config persistence closes that gap without adding an outbox, distributed transaction, or a second authority.

### Architecture attack

| Angle | Attack / evidence | Result / long-term cost |
| --- | --- | --- |
| Ownership | Gateway rightly owns workspace identity, local config, live catalog, and operation terminal result; IM owns request intent and profile CAS. | Correct placement. Workspace creation must remain within Gateway's write-ahead recovery sequence before the config that names it; [R4-C1]. |
| Should this exist? | Delete-test the new operation layer: a transient WS correlation id cannot survive the existing timeout/restart boundary, so prepared/terminal records are justified. A generic job system is not. | Minimal design is appropriate; only the transition order needs correction. |
| Deep vs shallow/reuse | `ensure_workspace_defaults` is already idempotent and `_publish_agent_config` already has candidate-equality convergence behavior. | Reusing those two concrete seams makes recovery deep and compact. Reversing their established creation order makes a shallow state-table claim that breaks real startup; [R4-C1]. |
| Root cause vs patch | R3 correctly moved durable knowledge ahead of the remote side effect. The root create invariant is also “a serialized workspace path exists before the next config load.” | Ignore that invariant and an expected crash becomes manual config repair/permanent pending rather than an automatic retry; [R4-C1]. |

### Historical issue closure

| Historical item | Author resolution | This-round verification | Status |
| --- | --- | --- |
| R1-C1 | Normalize the runtime value and render it in provider adapters. | D3/M1 continue to use actual provider-boundary proof. | **Closed.** |
| R1-C2 | Gateway-first acknowledged configuration plus compensation. | The durable-operation design subsumes deterministic ordering and CAS recovery. | **Closed; its recovery follow-up remains below.** |
| R1-W1 | Production matrix and executable rollout. | Matrix and exact host-scoped commands remain present. | **Closed.** |
| R2-C1 | Recover dropped ACK/reconnect/restart through durable operation state. | The prepared intent and status protocol close the original lost-result problem. | **Closed in substance; its create-sequence follow-up is [R4-C1].** |
| R2-C2 | Client-level static registered-body merge for both provider families. | D3, Runbook, and M1 retain the shared-client seam and registered-model proof. | **Closed.** |
| R2-W1 | Copyable production start/availability checks. | The target Gateway commands and observations are executable. | **Closed.** |
| R3-C1 | Write-ahead intent plus candidate/expected recovery across crash cuts. | Intent is now before all mutations and has adequate identity/reconciliation data. D5 still reverses workspace/config relative to the recovery scenario and real startup. | **Not closed; superseded by [R4-C1].** |

### Issues

#### [R4-C1] CRITICAL — D5 persists an explicit workspace path before it can exist, so a crash can prevent recovery from starting

**Where:** D5's local-config -> workspace sequence and recovery claims (`design.md:193-205`), the Gateway operation crash scenario (`specs/gateway/agent-capabilities.md:81-87`), and the prepared/config-persisted/published crash tests in the reviewer runbook and M1 (`design.md:423-431,446`).

**Evidence:** D5 says Gateway first CAS-persists the candidate local config and only *subsequently* calls idempotent `ensure_workspace_defaults` (`design.md:193-197`), but its own delta describes the workspace boundary as occurring before local config (`specs/gateway/agent-capabilities.md:81-86`). In the real create path, the production handler derives the workspace, calls `ensure_workspace_defaults`, then persists/publishes the `AgentWorkspaceConfig` (`src/personal_assistant/gateway/agent_config_sync.py:162-235`). Persistence serializes `workspace_root` for every agent (`src/personal_assistant/config/local_store.py:800-806`). On restart the local-config parser rejects an explicit `workspace_root` that does not exist *before* it invokes `ensure_workspace_defaults` (`src/personal_assistant/config/local_store.py:1105-1118`). Thus, after the D5 config write but before workspace setup, the next Gateway startup can fail while reading its own config; `operation.status` never runs, so IM remains `config_apply_pending`. The candidate branch's stated “live convergence + terminal receipt” also skips the missing workspace.

**Required design correction:** Make one order normative everywhere: `prepared` intent with deterministic workspace identity -> idempotent workspace/default-file initialization -> serialized expected-previous local-config CAS -> conditional live-catalog convergence -> terminal applied receipt/ACK. In recovery, an expected-previous state reruns the idempotent workspace step before applying once; a candidate state may skip it only because the preceding order guarantees it already exists, then use the existing catalog equality guard so a recovered operation does not republish. Align D5, the text data flow, Gateway delta, risk paragraph, runbook, and M1 around these distinct cuts: prepared/no workspace, workspace initialized/no config, config persisted/not live, and live/not terminal. The crash tests must restart from the serialized config, assert successful Gateway startup, and then assert the same terminal result—not merely exercise an in-memory status helper.

**If not fixed:** A crash at the new boundary can make the Gateway reject its own configuration at next boot, leaving the user's save permanently pending until manual filesystem repair. It also leaves two valid-looking but incompatible worker interpretations of the crash sequence, so one implementation can accidentally skip workspace seeding while another creates it before config; either defeats the promised automatic create recovery and Gate 2's no-false-state guarantee.

### Recommendations

- No non-blocking recommendations; [R4-C1] is the sole implementation-blocking correction.

### Author Resolutions

| Issue | Resolution | Evidence |
|---|---|---|
| R4-C1 | Accepted. The state transition is now strictly `prepared → idempotent workspace defaults → expected-previous config CAS → live publication → terminal receipt`. This honors the current startup invariant that every serialized `workspace_root` already exists. Recovery and tests now include the workspace-initialized/config-not-yet-persisted cut and assert Gateway starts before status recovery. | `design.md` 决策 5、可恢复数据流、风险、Runbook、M1；Gateway delta requirement/crash scenario |

## Round 5

### Metadata

- reviewer: `/root/feat514_design_reviewer`
- review_mode: `full`
- mode_reason: The R4 correction changes the durable create/apply transition and all four restart cuts. It affects Gateway startup validity, status recovery, the cross-process outcome contract, and M1 acceptance, so the follow-up rule requires a full review.
- started_at: `2026-08-07T15:21:40+08:00`
- completed_at: `2026-08-07T15:22:54+08:00`
- duration: `00:01:14`

### Verdict

**Approved — 0 CRITICAL / 0 WARNING. Gate 2 may pass.** R4-C1 is closed. The final operation order is consistently `prepared -> workspace defaults -> expected-previous config CAS -> conditional live publication -> terminal receipt`; it conforms to the real Gateway startup invariant. The expected branch repeats only the idempotent pre-config step; the candidate branch can safely do only equality convergence and terminalization. The delta, risk, runbook, M1, and restart assertions all make the same four cuts observable. This remains a necessary, small reliability boundary rather than an overbuilt workflow system.

### Coverage

| Surface | This-round evidence | Result |
| --- | --- | --- |
| Complete unit input | Re-read `spec.md`, all 451 lines of `design.md`, `prototype.html`, all delta specs, R1-R4, and R4 Author Resolutions. | Full inventory; no new scope, non-goal, or product-contract drift. |
| D5 sequence and restart state machine | D5, text data flow, risk, Gateway delta operation requirement/scenario, runbook, and M1. | All state the same prepared -> workspace -> config -> publication -> terminal sequence and name prepared/workspace/config/published restart cuts. **R4-C1 closed.** |
| Gateway production path | Composition, WS create handler, `IMAgentConfigSync`, config serializer/parser, workspace helper, `RuntimeConfigOwner`, and live catalog. | The corrected design follows actual workspace-before-serialized-config startup safety and reuses its idempotent/convergence seams. |
| Runtime/provider, IM, UI, and production delivery | D1-D4/D6, all deltas, prototype, operations docs, matrix and runbook. | Prior adapter, truthfulness, UX, and delivery conclusions remain valid; no regression from R4 correction. |

### Verification ledger

#### Current-state assertions

| ID | Rechecked assertion | Evidence / result |
| --- | --- | --- |
| C1 | Gateway model entries own static request extras; PA/Gateway, not IM, adapt model requests. | `src/personal_assistant/config/local_store.py:1035-1084`, `src/agent/core/llm/model_registry.py`, `SPEC.md:53-64,85,117-124`. **Verified.** |
| C2 | Complete runtime is the durable next-run boundary and active runs retain their original snapshot. | `src/agent/sdk/runtime.py:17-102`, `src/agent/sdk/kernel.py:980-1194`, `src/personal_assistant/gateway/session_run_coordinator.py:1195-1252`. **Verified.** |
| C3 | Registered static request body reaches Anthropic at its client and needs the same client/shared seam for OpenAI-compatible. | `src/agent/platform/llm/providers/anthropic/client.py:62-73`, `openai_compat/client.py:53-60`. **Verified; D3/M1 retain the corrected seam.** |
| C4 | Production Gateway creation is handled by `IMAgentConfigSync.handle_agent_create`. | `src/personal_assistant/gateway/composition.py:371-382,624-626`, `src/personal_assistant/ws/im_connection.py:1034-1051`. **Verified.** |
| C5 | Existing creation seeds the workspace before persisting its Agent config, and the seed is idempotent. | `src/personal_assistant/gateway/agent_config_sync.py:162-235`; `src/personal_assistant/config/local_store.py:108-146`. **Verified.** |
| C6 | Serialized agent config always contains `workspace_root`; a missing explicit root prevents startup parsing before defaults can be seeded. | `src/personal_assistant/config/local_store.py:800-806,1087-1118`. **Verified; corrected D5 protects this invariant.** |
| C7 | Config persistence is serialized before live catalog publication, and the existing convergence helper suppresses same-candidate republish. | `src/personal_assistant/config/local_store.py:357-370`; `src/personal_assistant/gateway/agent_config_sync.py:584-626`; `agent_catalog.py:70-93`. **Verified.** |
| C8 | Correlated Gateway requests may lose a response after a remote side effect. | `src/IM/ws/gateway/control.py:94-148`. **Verified; prepared/status remains justified.** |
| C9 | Create/detail use native model selects and the prototype's five states are compatible. | `src/IM/frontend/src/features/agents/agent-create-page.tsx:401-421,725-754`; `agent-detail-page.tsx:1303-1348,1482-1842`; `prototype.html:40-105`. **Verified.** |
| C10 | Mini remains the only IM `:8011` host and Gateways retain independent lifecycle/config ownership. | `docs/operations/prod-fleet.md:1-50`, `docs/operations/gateway.md:62-98`. **Verified.** |

#### Decisions and data flow

| Decision / flow | Review result |
| --- | --- |
| D1 — deployer-declared levels/default/fixed | **Covered.** Provider protocol stays out of the form and profile. |
| D2 — PA `ModelReasoningCatalog` | **Covered.** One immutable owner supplies validation, resolution, and capability projection. |
| D3 — normalized runtime field and provider-client static merge | **Covered.** Both client families retain configured static body while their mappers render selected effort; approval calls remain unaffected. |
| D4 — persisted profile/legacy behavior | **Covered.** Nullable legacy values resolve at runtime without silently rewriting a choice. |
| D5 — write-ahead operation/recovery | **Covered.** Prepared state precedes all side effects; expected and candidate branches are mutually exclusive, restart-safe, and terminate in applied/rejected/known-pending. |
| D6 — dependent UI group | **Covered.** Selector, fixed, absent, stale, and confirmation states preserve the specified user truth. |
| IM pending -> Gateway -> IM CAS flow | **Covered.** Status recovery after each Gateway restart cut returns the same terminal result before profile success is shown. |

#### Requirements, clarifications, and non-goals

| Source item | Design coverage / conclusion |
| --- | --- |
| R1 selectable/default, no isolated default-model effort, stale catalog | Config schema, catalog validation, dependent form, and 409 draft retention. **Covered.** |
| R2 fixed presentation and clearing selectable value | Informational fixed state plus persisted `None`. **Covered.** |
| R3 create first turn, existing next turn, understandable save failure | Complete runtime preserves next-run semantics; durable operation preserves truthful create/edit recovery. **Covered.** |
| R4 node-scoped configuration without frontend release | Safe, node-projected descriptors drive the form. **Covered.** |
| Q1/Q2/Q3 | Commercial fixed presentation, grouped next-run behavior, deployer catalog/provider adaptation/static-extra retention all have a direct decision and test projection. **Covered.** |
| Non-goals | No message override, upstream JSON exposure, invented level, or tool-approval behavior change. **Respected.** |

#### Delta specifications

| Delta item | Review result |
| --- | --- |
| Kernel ADDED complete runtime | Provider-neutral future normal-request behavior is observable to SDK consumers. **Covered.** |
| Gateway MODIFIED next-run behavior | Model/effort pairing, history, active-run, default, heartbeat, and cron behavior are preserved. **Covered.** |
| Gateway ADDED capability/operation recovery | Prepared intent, workspace-before-config invariant, expected/candidate reconciliation, restartability, and no-repeat outcomes are explicit. **Covered.** |
| IM MODIFIED profile update/recovery | Gateway-terminal result precedes profile write; lost ACK/restart, CAS conflict, and pending 503 paths are covered. **Covered.** |
| IM MODIFIED live capabilities | Safe selectable/fixed/absent descriptors and form behavior are covered. **Covered.** |

#### Milestone

| Milestone | Review result |
| --- | --- |
| M1 single vertical slice | The combined configuration/profile/Gateway/runtime/provider/UI delivery remains the correct vertical slice. Its worker lane now explicitly tests all four crash-restart cuts, successful Gateway restart, no repeated workspace/config/publication, and the user-visible terminal result. **Covered.** |

### Overall design check

The design is now internally coherent from configured capability through provider request and from Web IM save through durable Gateway recovery. The operation record is the minimum durable fact needed to distinguish a lost response from a failed change; workspace initialization uses the existing idempotent authority before the existing config parser's hard invariant; candidate recovery reuses equality convergence rather than replaying writes. There is no additional abstraction, background service, or cross-package dependency beyond what the user-visible reliability contract requires.

### Architecture attack

| Angle | Attack / evidence | Result / long-term cost |
| --- | --- | --- |
| Ownership | Gateway owns workspace, config, catalog, and receipt; IM owns pending intent/profile CAS; SDK owns normalized request transport. | **Pass.** Dependency direction and durable owners remain natural. |
| Should this exist? | Removing prepared/status returns to lossy WS correlation and false save state; replacing it with a general workflow engine adds no value. | **Pass.** The focused operation record is justified and minimal. |
| Deep vs shallow/reuse | Corrected D5 reuses `ensure_workspace_defaults`, `RuntimeConfigOwner.persist`, and current catalog equality convergence. | **Pass.** One semantic operation hides the necessary restart complexity rather than exposing a new transport abstraction. |
| Root cause vs patch | The correction handles the real parser/startup invariant at the exact crash boundary rather than merely masking it in UI/IM. | **Pass.** Restart recovery no longer depends on manual filesystem repair. |

### Historical issue closure

| Historical item | Author resolution | This-round verification | Status |
| --- | --- | --- |
| R1-C1 | Normalize effort and render at provider boundary. | D3/M1 retain real provider packet proof. | **Closed.** |
| R1-C2 | Gateway acknowledgment before profile persistence and CAS compensation. | D5's terminal-receipt protocol subsumes deterministic ordering and loss recovery. | **Closed.** |
| R1-W1 | Concrete production matrix and rollout. | Matrix and host-specific commands remain executable. | **Closed.** |
| R2-C1 | Recover unknown Gateway outcome. | Prepared/status/IM pending recover lost ACK, reconnect, and IM restart. | **Closed.** |
| R2-C2 | Client-level static body merge. | D3, Runbook, and M1 name and prove both provider client paths. | **Closed.** |
| R2-W1 | Executable host-specific delivery. | Start, listener, state/log, capability, and real-message checks remain present. | **Closed.** |
| R3-C1 | Write-ahead intent with expected/candidate recovery. | Intent precedes every side effect and the terminal path is durable. | **Closed.** |
| R4-C1 | Workspace before serialized config plus restartable cuts. | D5/data flow/delta/risk/runbook/M1 consistently implement and test the required order and branches. | **Closed.** |

### Issues

- None.

### Recommendations

- No non-blocking recommendations.
