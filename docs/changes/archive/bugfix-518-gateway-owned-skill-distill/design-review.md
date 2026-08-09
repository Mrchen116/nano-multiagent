# Design Review: bugfix-518-gateway-owned-skill-distill

## Round 1

### Metadata

| Field | Value |
|---|---|
| Reviewer target | `bugfix-518-gateway-owned-skill-distill@design-v1` |
| Review mode | full |
| Trigger | First independent design review before implementation |
| Started | 2026-08-09T01:23:18+08:00 |
| Finished | 2026-08-09T01:29:20+08:00 |
| Duration | 6m 02s |

### Verdict

**REVISE.** The ownership correction is sound: identity crosses IM→Gateway, while
the Gateway resolves its own durable binding and reads its own JSONL. The proposed
`GatewayDistillationSources` also has an appropriately deep responsibility.

However, three missing contracts prevent M1 from being implementable without a
worker inventing product semantics: the typed action does not have a closed
IM→relay→Gateway wire/validation path, the proposal no longer says how the
distiller is activated, and the Web IM delta loses two retained behaviours from
the requirement it modifies. One delivery-lifecycle decision also needs recording
so a source failure reliably becomes the promised normal chat failure.

### History closure

This is the first review round. `design.md` has no earlier review changelog or
prior issue IDs to close, so no historical item is carried forward.

### Issues

- **R1-C1 — `distillation_request` has no closed typed producer, authoritative validation, and Gateway consumer contract.**

  **Evidence.** D1/D2 require the browser to send the one-shot identity request,
  IM to validate it, persist it in the one relay task, and Gateway to validate it
  again ([design.md](design.md#L78-L92)). Today the browser's `createMessage`
  request has only content and attachments
  (`src/IM/frontend/src/features/chat/chat-api.ts:57-80`); the server DTO has no
  action field and the route only validates the destination conversation before
  relaying (`src/IM/api/routes/messages.py:70-86`, `392-451`). The leaf
  `RelayService.enqueue_message_relay()` can persist `extra_metadata`, but the
  public all-relay path used by the route cannot accept or pass it
  (`src/IM/application/relay_service.py:43-115`, `223-300`;
  `src/IM/application/web_im_service.py:567-604`). On the other side, Web Relay
  parses arbitrary opaque metadata and forwards it unchanged, and the inbound
  pipeline selects the relay's `agent_id` without recognizing a distillation
  request (`src/personal_assistant/channels/web_relay_adapter.py:213-230`,
  `342-404`; `src/personal_assistant/gateway/inbound_pipeline.py:104-190`).

  **Why this blocks.** There is no defined authoritative boundary at which source
  owner, idle state, `source_agent_id`, same-node membership, selected execution
  Agent, target conversation participant, scope, empty/duplicate sources, and
  `payload.agent_id == execution_agent_id` are checked. A worker could either
  silently drop the special request, route it through generic group fan-out, or
  trust caller-supplied source identities. Retrying the same idempotency key could
  likewise return a task whose payload was constructed before the special data
  was attached. That breaks data locality and the incident's "ordinary message,
  one Gateway" contract.

  **Required revision.** Add one precise request/relay/inbound contract:

  1. Define the typed browser send field and its lifecycle in the new execution
     conversation (created after the dialog; consumed by exactly its first send;
     never serialized into message history). Define the exact `sources` cardinality
     and duplicate policy.
  2. Name the IM application operation that authoritatively loads the source and
     execution conversation/profile rows in owner scope, recomputes the only
     target node, verifies the direct execution conversation and capability, and
     rejects malformed/stale/cross-node input *before* a relay task is created.
     `target_node_id` supplied by the browser must not select this action's route.
  3. State that this direct execution message uses the single-target enqueue path
     with `distillation_request` persisted in its canonical relay payload; a retry
     reuses that frozen payload and never creates a second relay. Ordinary and
     group messages retain their present all-relay semantics.
  4. Define the Gateway typed parser/guard before materialization: validate the
     object shape and scope, require the relay target Agent to equal
     `execution_agent_id`, and only then call `GatewayDistillationSources`.
     Malformed metadata is an actionable failed delivery, not a best-effort normal
     prompt.

  Update the test strategy without multiplying tests: extend the existing relay
  protocol/API seam with one durable, identity-only direct-send → canonical relay
  payload → typed Gateway-inbound test (and its rejection cases). Keep the new
  source-module unit test for local materialization. A permanent browser or
  two-process duplicate of this wire test is not needed; the two-root run remains
  acceptance evidence, consistent with
  [testing.md](../../development/testing.md#L7-L20) and
  [testing.md](../../development/testing.md#L60-L82).

- **R1-C2 — D4 removes path injection but does not specify how this run activates `conversation-skill-distiller`.**

  **Evidence.** The current flow works because the frontend builds a complete
  `/skill:conversation-skill-distiller` command with path arguments
  (`src/IM/frontend/src/features/chat/chat-workspace-page.tsx:195-213`). The new
  prototype instead shows only natural-language intent in the composer
  ([prototype.html](prototype.html#L101-L107)), and D4 describes visible intent
  plus transcript context in `kernel_input_parts` but no command or activation
  mechanism ([design.md](design.md#L101-L107)). `kernel_input_parts` currently
  emits only ordinary text/image parts
  (`src/personal_assistant/gateway/session_run_coordinator.py:1125-1167`,
  `1714-1741`). The Kernel invokes `skill_view` only when a complete text part
  matches the `/skill:` command parser
  (`src/agent/core/agent/skill_commands.py:15-39`;
  `src/agent/core/agent/runtime.py:405-420`, `520-538`). Updating the builtin
  SKILL.md alone therefore cannot make a plain ordinary prompt load its
  instructions.

  **Why this blocks.** A valid same-Gateway request may reach the model without
  the distiller's evidence and `skill_manage(create)` rules. The model can answer
  conversationally instead of performing the requested generation, even though
  the UI successfully passed readiness checks.

  **Required revision.** Choose and document one activation mechanism. The
  minimal reuse is for the Gateway, after all source checks succeed, to create
  ordered input parts whose first text part is exactly
  `/skill:conversation-skill-distiller`, followed by a bounded, explicitly marked
  Gateway-provided data context containing target scope, visible user intent and
  the materialized transcripts. Document that this internal command/context is
  not returned to Web IM history or reply context; the revised builtin consumes
  only the marked context and treats transcripts as data. If a different SDK-level
  activation seam is chosen, name its public contract and equivalent capability
  check instead. Add an outcome-level Gateway test proving that a valid request
  activates the distiller and receives the supplied context, rather than merely
  asserting a private list of input parts.

- **R1-C3 — The `web-chat-ux` MODIFIED delta drops retained scenarios from the requirement it replaces.**

  **Evidence.** The current requirement says that an execution Agent without
  `conversation-skill-distiller` blocks the operation and does not create/navigate
  to a new conversation (`docs/specs/im/web-chat-ux.md:298-302`), and that normal
  sidebar browsing does not show running-state labels (`docs/specs/im/web-chat-ux.md:304-306`).
  The delta replaces that same requirement but retains neither scenario
  (`specs/im/web-chat-ux.md:5-35`). The omission conflicts with the incident's
  required capability feedback ([incident.md](incident.md#L44-L48)) and with the
  design flowchart's `skill/tool` precondition ([design.md](design.md#L151-L164)).

  **Why this blocks.** A `MODIFIED` requirement is the future complete contract,
  not a list of only new examples. Without the scenarios, M1 may regress the
  ordinary conversation list or create an empty execution conversation for an
  Agent that cannot execute the distiller; neither outcome has a current-spec
  guard after merge.

  **Required revision.** Retain both scenarios in the delta, updating the
  capability wording to the final contract (distiller and any required `skill_view`
  capability) and preserving the no-navigation/no-draft result. Also explicitly
  retain that running/cross-node labels appear only in distill selection mode, not
  normal sidebar browsing. Add the corresponding existing frontend journey
  assertions while rewriting the old path-draft assertions; do not create a
  separate test file for them.

- **R1-W1 — Source-materialization failure is not placed on the existing delivery lifecycle.**

  **Evidence.** D3 promises an understandable ordinary failure with no model or
  skill run ([design.md](design.md#L94-L99)), and the Gateway delta makes that a
  user-visible result (`specs/gateway/relay-protocol.md:24-27`). But the present
  inbound pipeline only dispatches normal inbound runs
  (`src/personal_assistant/gateway/inbound_pipeline.py:183-190`), while the
  coordinator's message part seam currently only reports attachment resolution
  failures (`src/personal_assistant/gateway/session_run_coordinator.py:1125-1167`).
  Delivery receipts advance or fail through the established lifecycle, not merely
  by returning an exception (`src/personal_assistant/gateway/runtime_delivery/lifecycle.py:56-63`,
  `101-136`). The design names `GatewayDistillationSources` but does not say which
  coordinator/lifecycle boundary calls it or emits the failure reply and failed
  receipt.

  **Why this matters.** If a worker materializes in the adapter/pipeline, a bad
  source can be deduped without a normal chat failure or leave the IM delivery
  state at an inappropriate accepted/sent state. If it is placed after model
  admission, it violates the all-or-nothing/no-run promise.

  **Required revision.** Specify a coordinator before-submit hook: it recognizes
  the validated action, materializes all sources before acceptance/model submit,
  and maps `GatewayDistillationSources`' typed failure through the existing
  outbound reply plus failed-delivery-receipt path. Record that no execution
  binding/session is created for this failed action and add one Gateway outcome
  test for the visible failure/receipt state. This is a lifecycle wiring test, not
  another browser or process E2E test.

### Recommendations

1. Revise D2/D4 and the interface/data-flow section together. The resulting
   sequence should have exactly four named boundaries: typed browser action → IM
   authoritative validator/single relay task → Gateway typed guard/materializer
   → coordinator activation and delivery lifecycle.
2. Amend the Web IM delta before implementation rather than relying on the
   prototype or M1 exit criteria to preserve existing scenarios.
3. Retain the tasks document's overall restraint: its affected-test disposition
   table is concrete, its new deep-module test has a semantic owner, and its
   two-root browser run is correctly designated temporary acceptance evidence.
   Add only the missing cross-package wire/lifecycle outcomes required above.

### Full coverage inventory

`Pass` means the item is sufficiently specified and grounded. `Blocked` means it
is covered by one of the issues above. `Retain` means an existing behavior is in
scope but is absent from the future delta and therefore must be restored.

| Inventory | Atoms reviewed | Evidence and disposition |
|---|---|---|
| Current-state assertions | CS1 IM workspace scan/path projection; CS2 frontend eligibility/path draft; CS3 durable opaque relay; CS4 Gateway binding plus input-parts seam; CS5 builtin consumes paths (`design.md:11-22`) | **Pass.** Code confirms CS1 at `src/IM/infra/repositories/conversations.py:615-712`, CS2 at `chat-workspace-page.tsx:195-213, 980-995`, CS3 at `relay_service.py:43-115`, CS4 at `session_binder.py:664-685` and `session_keys.py:1664-1669`, and CS5's current slash activation path. CS3/CS4 are feasible reuse, with C1/C2 defining the missing integration. |
| Constraints and non-goals | Architecture isolation; one Gateway/no sync; current sidebar/dialog/chat result; reuse existing idempotency; no new recovery; no workspace-root or feat-515 recovery change (`design.md:24-33, 43-50`; `incident.md:13-18, 30-34`) | **Pass.** The scope correctly separates the #515 creation-recovery concern and avoids cross-Gateway RPC/recovery. C1 must make reuse of the existing relay key concrete, not add a recovery subsystem. |
| Incident: reproduction/RCA | A separate IM cannot read the Gateway workspace; path scanning is the faulty ownership boundary (`incident.md:20-40`) | **Pass.** The current repository scans `agent_profiles.workspace_root` and returns `Path.resolve()` (`conversations.py:683-712`), matching the diagnosis. |
| Incident: desired direction 1–3 | IM selection/routing only; Gateway local durable binding/JSONL/skill; same-Gateway combinations only (`incident.md:42-46`) | **Blocked by R1-C1.** The target ownership is correct, but the identity request is not yet carried and revalidated through the named seams. |
| Incident: desired direction 4 | Clear feedback for unavailable/running/missing/capability/offline cases; no false “no transcript” (`incident.md:47`) | **Blocked by R1-C1 and R1-W1.** UI preconditions and runtime rejection/failure lifecycle must be separately named. |
| Incident: desired direction 5 | Isolated IM/Gateway file systems prove complete trip and no path in API/browser/prompt (`incident.md:48`) | **Blocked by R1-C1/C2.** M1's temporary two-root acceptance is correct; add the lean permanent wire and activation outcomes specified above. |
| D1 | Node projection, UI exclusion, IM recheck, Gateway recheck, no split/fallback (`design.md:78-84`) | **Blocked by R1-C1.** Need exact authoritative validator and the relay-target/execution-Agent equality guard. |
| D2 | One-shot identity metadata, no path/history, original idempotency key only (`design.md:86-92`, `116-128`) | **Blocked by R1-C1.** The schema is a useful start but does not define the DTO, route, one-target enqueue, replay payload, or typed ingress validation. |
| D3 | Exact binding, local JSONL, all-or-nothing no-run/no-write (`design.md:94-99`) | **Blocked by R1-W1.** The deep module and exact binding are viable; the caller and user-visible failed-delivery route remain unspecified. |
| D4 | Visible intent plus bounded internal transcript context; builtin no longer reads paths (`design.md:101-107`) | **Blocked by R1-C2.** The proposal needs a concrete skill activation mechanism before its context can have the intended effect. |
| D5 | Agent/global are local to the execution Gateway; no sync (`design.md:109-112`) | **Pass.** It is consistent with the stated single-Gateway boundary and existing local builtin installation model. |
| Gateway delta requirement and scenarios G1–G4 | Local materialization/normal result; no paths; all-or-nothing failure; cross-Gateway rejection (`specs/gateway/relay-protocol.md:5-31`) | **Blocked by R1-C1, R1-C2, R1-W1.** The observable outcomes are the right contract; the design must define the missing wiring that makes them achievable. |
| IM relay delta requirement and scenarios I1–I3 | Validated opaque action metadata; identity reaches one relay; replay stays one task; receipts progress (`specs/im/gateway-relay.md:5-27`) | **Blocked by R1-C1.** Retain the existing replay/receipt requirement and specify the canonical payload/validation needed for its new action. |
| Web IM delta scenarios W1–W4 | Same-node selection; same-node executor/scope; no path on submit; normal chat result (`specs/im/web-chat-ux.md:5-35`) | **Blocked by R1-C1; Retain via R1-C3.** The new scenarios fit the product, but the modified requirement must also retain capability failure and normal-mode label behaviour. |
| Prototype/UX contract | Sidebar selection, dialog, ordinary composer/result; desktop and 390px must-match (`design.md:166-187`; `prototype.html:83-118`) | **Blocked by R1-C2/C3.** The visual path cleanly omits paths and communicates node scope. Its plain composer confirms the need to state internal skill activation; it does not substitute for retained non-selection mode behaviour. |
| Risks and rollback | Binding/profile changes, prompt-as-instruction, ACK interruption, scoped revert (`design.md:196-204`) | **Blocked by R1-C1/C2/W1.** The listed risks are appropriate once typed ingress, actual activation, and failed lifecycle are decided. No additional recovery design is warranted. |
| M1 reviewer exits | Same-node UI; two-root success/no-path; all failure classes give feedback/no partial (`design.md:221-228`) | **Blocked by R1-C1/C2/W1.** The vertical M1 is correctly indivisible, but its exit criteria need the same closed wire and lifecycle semantics. |
| M1 worker exits and test strategy | Browser prototype check; lowest API/frontend/Gateway tests; old-test dispositions; temporary two-root evidence (`design.md:221-228`; `tasks.md:19-46`) | **Blocked narrowly by R1-C1/C2/W1.** The test plan otherwise follows `docs/development/testing.md:7-20, 60-82`: it identifies real seams, gives existing tests a disposition, avoids test files named for the milestone, and keeps true-stack proof out of the permanent suite. Extend existing wire/lifecycle coverage rather than introducing a broad test matrix. |

### Architecture attack

| Angle | Assessment |
|---|---|
| Ownership | The main correction is right: IM should not use `workspace_root` as a remote file-system capability, and Gateway owns binding→local JSONL resolution. C1 is required so the owner can be enforced rather than asserted only in prose. |
| Necessity | Reusing relay idempotency and Web Relay dedupe is the narrow fix; no new transcript RPC, sync fabric, or #515 recovery path is justified. The missing typed action/guard is necessary semantics, not a new subsystem. |
| Deep vs. shallow | `GatewayDistillationSources` can hide the binding lookup, JSONL addressing/parsing and all-or-nothing result behind one source-pair interface. The external request must stay shallow and identity-only. C2 must define the one small activation adaptation at the coordinator seam rather than making the frontend rebuild a privileged prompt. |
| Root cause | Removing IM's recursive JSONL scan and public absolute-path projection directly removes the cross-machine failure. Any solution that falls back to IM scanning or sends a path/transcript through relay would reintroduce the root cause; no such fallback should be added. |

### Conclusion

Return this unit to `change-design-author` for a focused v2. Once C1–C3 and W1
are resolved in the design, delta specs, tasks, and prototype contract, it can
return for R2. No production implementation should start from the present v1.

## Round 2

### Metadata

| Field | Value |
|---|---|
| Reviewer target | `bugfix-518-gateway-owned-skill-distill@design-v2` |
| Review mode | delta |
| Mode reason | v2 changes the R1 data-flow/activation/lifecycle contracts without changing the incident scope or M1 boundary. This round rechecks every changed atom, all R1 closures, their relay/API/Gateway/spec downstream effects, and the affected ownership, depth, and root-cause attacks. |
| Started | 2026-08-09T01:29:21+08:00 |
| Finished | 2026-08-09T01:43:57+08:00 |
| Duration | 14m 36s |

### Verdict

**REVISE — 2 CRITICAL / 1 WARNING.** v2 closes the essential shape of the
identity-only direct relay, explicit skill activation, retained Web IM states,
and source-materialization lifecycle. Two newly precise details still conflict
with the real ownership boundaries or put private implementation into a public
Gateway contract.

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | D2 adds a typed one-shot DTO, named IM operation, single-target frozen relay, and D6 Gateway guard; Four concrete boundaries record the sequence. | The DTO shape, one-shot lifecycle, owner/node/direct-conversation validation, no-path payload and target-agent guard are now unambiguous (`design.md:92-123, 149-184`). However the operation is also required to validate *runtime* capability, for which it has no stated authoritative data source; see R2-C1. | **partially closed; superseded by R2-C1** |
| R1-C2 | D4 fixes the first `kernel_input_parts` text to the complete distiller command and puts marked context second. | The current Kernel finds the first complete command in multipart input (`src/agent/core/agent/runtime.py:91-97`) and performs `skill_view` before the model loop (`src/agent/core/agent/runtime.py:411-420, 520-538`). D4's ordering therefore activates the intended builtin without a browser-visible command. | **closed** |
| R1-C3 | The Web IM delta restores capability failure/no navigation and normal-sidebar scenarios. | Both retained scenarios are present at `specs/im/web-chat-ux.md:24-28, 43-46`; the original selection, executor/scope, submit and result scenarios remain represented. | **closed** |
| R1-W1 | D6 specifies typed guard, coordinator before-submit materialization, and a normal reply plus failed receipt without creating a session/binding. | This is now a concrete lifecycle decision (`design.md:149-159`). Existing delivery lifecycle accepts `failed` receipts (`src/personal_assistant/gateway/runtime_delivery/lifecycle.py:112-136`), and an outbound reply can use the existing conversation reply-context seam without a Kernel session (`src/personal_assistant/gateway/session_keys.py:1672-1682`). The malformed-action branch still needs the routing clarification in R2-C1. | **closed for source-materialization failure** |

### Issues

- **[R2-C1][CRITICAL] [D2, D6, Four concrete boundaries] “IM authoritatively validates runtime capability” has no compatible authority path, while the final Gateway guard does not validate it.**

  D2 says `WebIMService.create_distillation_message` verifies that the execution
  Agent's *runtime* capability includes the distiller, `skill_view`, and
  `skill_manage` (`design.md:112-117`). That service currently owns only
  conversation/message/relay repositories (`src/IM/application/web_im_service.py:47-71`). The real capability source is an asynchronous IM→Gateway control RPC
  (`src/IM/api/routes/agents.py:409-435`;
  `src/IM/ws/gateway/control.py:280-311`), and its existing request even takes a
  workspace root from IM. Meanwhile D6's final Gateway guard checks only schema,
  scope, relay target and Gateway membership (`design.md:151-155`), not the three
  required capabilities. This conflicts with v2's claim that the identity relay
  is the only cross-process request (`design.md:78-80, 92`) and leaves a direct
  HTTP caller/stale UI without a specified final readiness check.

  If left unresolved, a worker must either introduce an undocumented capability
  RPC/dependency into `WebIMService` (and reintroduce an IM-held workspace value
  into this flow), or trust a stale browser/mirror value. Either choice can create
  a normal message whose internal slash command cannot load or cannot write the
  distiller, contrary to the required no-empty-conversation/precondition journey.

  Revise the authority split explicitly: IM's operation should authoritatively
  validate only IM-owned owner/source/node/idle/direct-conversation facts. The
  existing browser capability check remains a preflight that prevents creating a
  visible empty execution conversation. After resolving the target Agent,
  Gateway's typed guard (or the coordinator's immediate preflight) must make the
  final local runtime skill/tool check before materialization and, on failure,
  call one named no-session rejection path that emits the actionable normal reply
  and failed receipt. This keeps the special action's only new cross-process data
  flow identity-only, gives direct/stale callers deterministic feedback, and
  tells workers exactly where the final authority lives.

- **[R2-C2][CRITICAL] [gateway relay-protocol delta, Scenario “同 Gateway 来源被本机读取并产生普通聊天结果”] The delta puts hidden implementation mechanics into a public Gateway contract.**

  `docs/specs/gateway/relay-protocol.md` defines external consumers as IM,
  terminal users, and operators. Yet its new Scenario THEN requires the internal
  literal `/skill:conversation-skill-distiller` and an internal context ordering
  (`specs/gateway/relay-protocol.md:12-18`). Those are D4 implementation choices,
  not something IM or a terminal user can observe. The design already contains
  the necessary exact activation decision at `design.md:132-142`.

  If retained, the merged canonical protocol spec will make a private Kernel
  adaptation an externally promised protocol detail. That misdirects cross-package
  tests toward hidden input parts and prevents a later safe Gateway-only activation
  refactor even when the IM-observable relay/result contract remains intact.

  Move the exact command/context ordering entirely to D4 and its Gateway tests.
  In the Gateway delta, retain only observable protocol behaviour: with valid
  local identities the Gateway runs the distiller using locally prepared source
  data, produces the existing normal chat/tool result, and does not expose paths
  or transcript bytes across the relay. No internal command, class, or input-part
  assertion belongs in that Scenario.

- **[R2-W1][WARNING] [IM gateway-relay delta] The new failed-receipt outcome is not represented in the IM consumer contract.**

  D6 and the Gateway delta require a source failure to send a failed delivery
  receipt (`design.md:157-159`; `specs/gateway/relay-protocol.md:25-29`). The IM
  relay delta's modified requirement and retained receipt Scenario still only
  describe `sent → completed` (`specs/im/gateway-relay.md:7-12, 30-32`), although
  the actual relay service already applies `failed` and publishes a failed
  delivery state (`src/IM/application/relay_service.py:647-672`;
  `src/IM/ws/gateway/relay.py:539-603`).

  Without the scenario, the final canonical IM contract does not say what its
  consumer observes for this newly required source-failure path, and a future
  change can preserve success receipts while regressing the failed state. Add one
  IM-side Scenario for Gateway's failed receipt: the source user message becomes
  `failed` and its event/user stream exposes the existing actionable failure
  state. Extend the same relay/API seam test; do not add a browser or E2E duplicate.

### Recommendations

- **[R2-R1]** Resolve R2-C1 by making Gateway the final capability authority and
  naming the no-session rejection callback; then align D2, D6, the four-boundary
  table, M1's capability-failure exit, and the Gateway guard/lifecycle test.
- **[R2-R2]** Keep D4's exact activation seam in design, but remove it from the
  Gateway external delta as required by R2-C2.
- **[R2-R3]** Add the single failed-receipt Scenario to the existing IM relay
  delta and its existing seam test. The rest of `tasks.md` remains appropriately
  restrained: one API/relay wire test, existing frontend journey coverage, a
  semantically owned source-module test, and temporary two-root browser evidence;
  no permanent test expansion is warranted.

### Coverage

| Changed/rechecked atom | Evidence and result |
|---|---|
| Current-state assertion: the inbound pipeline is the typed-action guard seam (`design.md:23-28`) | **Pass with R2-C1 boundary correction.** Real inbound traffic reaches `InboundPipeline.handle_inbound()` through the adapter/dispatcher (`src/personal_assistant/channels/web_relay_adapter.py:213-230`; `src/personal_assistant/gateway/inbound_dispatcher.py:138-157`). It is the correct place to recognize the action after routing, but it must delegate no-session failure into the coordinator/lifecycle rather than throw through the dispatcher. |
| D2 and relay metadata/four-boundary contract | **Blocked by R2-C1.** The one-shot DTO, direct-only route, fingerprinted frozen payload, no path, and Gateway target equality are now explicit and fit the current leaf relay API (`src/IM/application/relay_service.py:43-115`). Runtime capability authority is the only unresolved part. |
| D4 activation | **Pass.** The fixed command first/context second ordering is compatible with multipart command discovery and rewrite (`runtime.py:75-97, 411-420`). The internal context is excluded from reply context by existing `kernel_input_parts` stripping (`src/personal_assistant/gateway/session_keys.py:1646-1661`). |
| D6 lifecycle | **Pass for materialization; blocked only insofar as R2-C1 must route invalid/capability rejection.** The decision correctly puts local I/O before binding/model admission and specifies a typed source result. Existing coordinator lifecycle emits failed delivery receipts (`session_run_coordinator.py:976-1006`; `runtime_delivery/lifecycle.py:112-136`). |
| Web IM modified delta | **Pass.** It preserves the original six behavioural areas while changing the obsolete path-prefill contract: selection, executor/scope, capability block, identity submit, result display, and ordinary-sidebar appearance (`specs/im/web-chat-ux.md:11-46`). |
| IM relay modified delta | **Warning R2-W1.** Replay and stream scenarios are preserved; the new failed-receipt consumer outcome needs one scenario. |
| Gateway added delta | **Blocked by R2-C2.** Local-only materialization, all-or-nothing failure, path exclusion and cross-Gateway rejection are correct consumer outcomes. The hidden slash/context details must remain design-only. |
| M1 and tests | **Pass except for the three targeted changes above.** M1 remains one necessary vertical journey (`design.md:279-286`). The test plan gives each stable risk its lowest seam and marks two-root real-stack evidence temporary (`tasks.md:22-52`), consistent with `docs/development/testing.md:7-20, 60-82`. |

### Affected architecture attack

| Angle | Finding |
|---|---|
| Ownership | Gateway owns both local transcript access and its live skill/tool availability. R2-C1 prevents IM from acquiring an undocumented remote-runtime authority or carrying workspace data merely to make that check. |
| Necessity | The v2 one-shot action, source deep module, explicit command and lifecycle hook are necessary to remove the broken path hand-off; no recovery queue, transcript RPC, or new broad test layer is needed. |
| Depth | `GatewayDistillationSources` remains a good deep module because callers provide source pairs and receive prepared input/failure. The Gateway delta must not leak D4's private input-part mechanism as an external shallow protocol (R2-C2). |
| Root cause | v2 continues to eliminate IM JSONL scanning and path propagation. Resolving R2-C1 without the existing workspace-root capability RPC preserves that correction rather than reintroducing a different IM→Gateway path dependency. |

### Conclusion

Return to `change-design-author` for a small v3 resolving R2-C1/R2-C2 and the
IM failed-receipt scenario. R1-C2/R1-C3/R1-W1 otherwise remain closed, and the
M1/test shape should be retained rather than expanded.

## Round 3

### Metadata

| Field | Value |
|---|---|
| Reviewer target | `bugfix-518-gateway-owned-skill-distill@design-v3` |
| Review mode | closure |
| Mode reason | v3 is limited to the three R2 resolutions: capability authority/failure route, external-delta wording, and the IM failed-receipt Scenario. It does not change the incident scope, architectural boundary, M1, or test topology. |
| Started | 2026-08-09T01:44:00+08:00 |
| Finished | 2026-08-09T01:47:04+08:00 |
| Duration | 3m 04s |

### Verdict

**APPROVE — 0 CRITICAL / 0 WARNING.**

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R2-C1 | D2 makes browser capability reading a non-authoritative preflight; D6 makes the local execution runtime the final capability authority and names `fail_distillation_before_submit()` for malformed/capability/source failure. | IM now validates only facts it owns (`design.md:113-119`). Gateway checks the three runtime requirements before source I/O/session creation and routes all pre-submit failures through the named normal-reply/failed-receipt path (`design.md:151-164, 182-189`). This matches the existing ability to reply to an IM conversation without a Kernel binding (`src/personal_assistant/gateway/session_keys.py:1672-1682`) and to emit a failed receipt (`src/personal_assistant/gateway/runtime_delivery/lifecycle.py:112-136`). | **closed** |
| R2-C2 | The Gateway delta removes the hidden literal slash command and input-part ordering; D4 remains the sole owner of the private activation decision. | The external requirement now specifies only local materialization, local execution, non-disclosure, and ordinary result relay (`specs/gateway/relay-protocol.md:12-18`). Exact command/context ordering remains correctly contained in D4 (`design.md:134-144`). | **closed** |
| R2-W1 | The IM relay delta adds an observable failed-receipt Scenario. | `specs/im/gateway-relay.md:34-37` requires a pre-run source/runtime failure receipt to mark the originating user message `failed` and expose the actionable state through existing read/event streams. This matches the current receipt persistence behaviour (`src/IM/application/relay_service.py:647-672`; `src/IM/ws/gateway/relay.py:539-603`). | **closed** |

### Issues

None.

### Recommendations

- **[R3-R1]** Hand the approved v3 to `change-orchestrator`. Retain the existing
  focused test plan: exercise the final Gateway capability/no-session failure in
  the coordinator lifecycle seam and the failed receipt in the existing IM relay
  seam; do not add a duplicate browser or permanent two-Gateway E2E test.

### Conclusion

R2-C1, R2-C2, and R2-W1 are closed without reopening any R1 closure or expanding
the unit. The design is ready for implementation.

## Round 4

### Metadata

| Field | Value |
|---|---|
| Reviewer target | `bugfix-518-gateway-owned-skill-distill@design-v4` |
| Review mode | delta |
| Mode reason | v4 makes one bounded, user-visible UX correction: preserve the existing visible distiller-command prefill while removing its path payload. The identity relay, Gateway authority, activation mechanism, failure lifecycle, delta ownership, M1, and test topology remain unchanged. |
| Started | 2026-08-09T01:52:00+08:00 |
| Finished | 2026-08-09T01:55:59+08:00 |
| Duration | 3m 59s |

### Verdict

**APPROVE — 0 CRITICAL / 0 WARNING.**

### 历史问题与本轮 delta 闭环

| Item | v4 change | Verification | Status |
|---|---|---|---|
| R2-C1 / R3 approval: Gateway remains final authority | D2 restores only a visible command/intention prefill; D4 explicitly treats it as non-authoritative and still replaces default parts after local materialization. | The browser sends the same identity-only one-shot DTO and no path (`design.md:94-128, 182-193`). The Gateway alone supplies the fixed internal activation command and local source context, and does not trust the visible command for data or activation (`design.md:137-148`). | **retained closed** |
| R2-C2 / R3 approval: public Gateway delta stays consumer-observable | No private command/context detail was reintroduced into the Gateway delta. | `specs/gateway/relay-protocol.md:12-18` remains limited to local materialization, non-disclosure and normal result relay. | **retained closed** |
| UX regression reported by user | The Web IM delta and task explicitly retain `/skill:conversation-skill-distiller` in the editable composer while forbidding all path forms. | The user-visible scenario requires the prefill and separately forbids `source_jsonl_paths`, workspace root and JSONL absolute paths (`specs/im/web-chat-ux.md:30-36`); `tasks.md:13-14, 49-50` keeps the existing frontend journey as the single seam that tests both facts. | **closed** |

### Issues

None.

### Recommendations

- **[R4-R1]** In the existing frontend journey test, assert the visible slash
  prefill and the absence of every path field in the same draft/send flow. Keep
  the existing Gateway activation test independent: it verifies that the local
  typed action, rather than editable visible text, determines execution.

### Coverage

| Changed atom | Result |
|---|---|
| D2 visible composer contract | **Pass.** The prefill restores the familiar user journey but is restricted to readable names/range and cannot contain local file identity (`design.md:94-101, 113-114`). |
| D4 trust/activation boundary | **Pass.** Internal first command plus Gateway-provided context remain the only Kernel input authority; visible text is retained only as user intent (`design.md:137-148`). |
| IM Web Chat delta | **Pass.** The scenario is user-observable and preserves both the visible command and the no-path contract (`specs/im/web-chat-ux.md:30-36`). |
| Task/test scope | **Pass.** The existing frontend integration journey absorbs the UX assertion; no new test file or E2E layer is introduced (`tasks.md:33-40, 49-53`). |

### Conclusion

The v4 UX correction restores the intended visible command without reintroducing
path transport, transcript exposure, or browser authority over Gateway execution.
R3's approval remains valid; the design is ready for implementation.

## Round 5

### Metadata

| Field | Value |
|---|---|
| Reviewer target | `bugfix-518-gateway-owned-skill-distill@design-v5` |
| Review mode | full |
| Mode reason | v5 deliberately replaces v1–v4's identity-only relay, hidden local activation and delivery-lifecycle design with a Gateway-produced, current-format visible prompt followed by ordinary relay. That changes the trust boundary, path exposure, protocol and acceptance target, so the earlier delta approvals cannot be carried forward. |
| Started | 2026-08-09T01:56:00+08:00 |
| Finished | 2026-08-09T02:12:31+08:00 |
| Duration | 16m 31s |

### Verdict

**REVISE — 3 CRITICAL / 2 WARNING.** The intended minimal shape is good: IM no
longer scans a remote filesystem, one selected Gateway builds the existing prompt,
and ordinary chat/builtin execution are retained. The current v5 documents three
contradictory or unproved conditions, however: it has not formally accepted the
new path-exposure contract; it cannot guarantee that the returned paths are sent
back to their issuing Gateway; and it drops an existing capability failure before
the new chat is created. These are contract corrections, not a return to the
withdrawn metadata/recovery/transcript subsystem.

### Historical issues and v5 supersession

| Earlier item | v5 disposition | Review result |
|---|---|---|
| R1-C1 / R2-C1 / R3 approval: typed identity-only relay and Gateway-final runtime guard | v5 explicitly withdraws that action and instead adds a prompt control RPC followed by ordinary relay. | **Superseded, not retained closed.** Its no-path and pre-submit guarantees cannot be cited for v5. R5-C1/C3 record the corresponding v5 contracts that must now be made explicit. |
| R1-C2 / R2-C2 / R3 approval: hidden internal command/context activation | v5 explicitly withdraws internal injection and returns the existing visible command plus paths as the ordinary draft. | **Superseded.** This is consistent with the user's chosen minimal architecture; do not restore hidden input parts. |
| R1-C3 / R4 approval: familiar visible slash prefill | v5 preserves and expands it to the complete current prompt. | **Retained, subject to R5-C1.** The familiar prompt is correct only after the incident/current-contract change says paths are deliberately visible again. |
| R1-W1 / R2-W1: special delivery failure and receipt lifecycle | v5 moves all prompt failure before a user message/direct conversation exists and uses ordinary chat only after a prompt succeeds. | **Superseded.** No special receipt/recovery design should be restored. |

### Issues

- **[R5-C1][CRITICAL] [Incident Q2, repair direction, D3, delta specs] v5 deliberately exposes absolute JSONL paths but the unit's authoritative incident still forbids exactly that.**

  `incident.md:15-18, 42-48` says IM must not expose Gateway-local absolute paths
  to the browser or ordinary chat, and makes absence from the IM API, browser and
  Agent prompt an acceptance proof. v5 D3 instead says paths may appear in all
  three (`design.md:65-70`), while both new deltas require a prefill containing
  `source_jsonl_paths` (`specs/im/web-chat-ux.md:17-22`,
  `specs/gateway/relay-protocol.md:12-16`). This is an intentional product
  decision, but it is undocumented as a supersession; the same unit currently has
  mutually exclusive acceptance criteria.

  **Required revision.** Amend the incident's Q2/repair direction with a dated
  v5 clarification: the product now accepts the *current-format* prompt carrying
  Gateway-produced local paths through IM/browser/ordinary relay, solely for a
  same-Gateway execution; IM still must never scan, read, parse, generate or use
  them to select a source. Replace the obsolete no-path acceptance claim with
  proof of that ownership boundary. This is not a request to reintroduce the old
  metadata or transcript subsystem.

- **[R5-C2][CRITICAL] [D1–D3, M1] “IM has guaranteed the ordinary message returns to the issuing Gateway” is false under the current ordinary-relay seam.**

  D3 relies on that guarantee to justify forwarding the paths
  (`design.md:67-70`). But a normal `createMessage` resolves its target at send
  time from the current profile node (`src/IM/api/routes/messages.py:413-459`;
  `src/IM/application/relay_service.py:302-332`), and a direct conversation only
  freezes `config_agent_id`/profile version, not node id
  (`src/IM/infra/repositories/conversations.py:122-163, 826-865`). A Gateway
  registration may rebind an existing agent profile's `node_id`
  (`src/IM/infra/gateway_persistence.py:143-205`). Thus the D2 equality check can
  succeed and Gateway A can return A-local paths, yet a later ordinary send can be
  routed to Gateway B. The promise in the sequence diagram and Gateway delta
  (“same Gateway receives ordinary relay”) is therefore not an implementation
  consequence of v5's stated flow.

  **Required revision.** Name the smallest authoritative binding that preserves
  the selected node from prompt generation through the first ordinary send (or
  state and enforce a real immutability invariant that makes such a rebind
  impossible). It must remain IM-owned and opaque to the browser; do not add a
  second relay/action protocol. Add one focused outcome covering a changed/stale
  execution-node assignment: the prompt is never delivered to a different node
  with its old paths. The author may choose the storage/route detail, but cannot
  retain D3's guarantee without one.

- **[R5-C3][CRITICAL] [D2/D4, Web IM delta] v5 drops the existing distiller/`skill_view` readiness gate and does not make its Gateway replacement explicit.**

  The current journey reads live agent configuration/capabilities and keeps the
  dialog open before creating a direct chat when the distiller or `skill_view` is
  unavailable (`chat-workspace-page.tsx:936-976`); the current canonical Web IM
  spec also requires the missing-distiller no-navigation outcome
  (`docs/specs/im/web-chat-ux.md:298-302`). The incident continues to require a
  clear unavailable skill/tool failure (`incident.md:47`). v5 D2 validates only
  owner/idle/node, its Gateway delta resolves only bindings/paths, and the v5
  Web-IM delta has no capability-failure scenario. A current-format draft could
  therefore create a chat and only later fail to activate/read/write the skill,
  contrary to D4's “failure before chat” claim.

  **Required revision.** Retain the existing browser readiness check as the fast
  UI preflight and specify a final local Gateway readiness check in the same
  prompt RPC before it returns a prompt. It should report an actionable error and
  leave the dialog/no-conversation state intact; it must not add a new execution
  path or lifecycle. Add this one error outcome to the Web IM/Gateway deltas and
  extend the existing frontend/control seam tests rather than creating a new test
  suite.

- **[R5-W1][WARNING] [D2, gateway relay-protocol delta] The new control RPC is named but not a complete correlated protocol contract.**

  v5 says there is “no new message type” (`design.md:17-20`) while simultaneously
  introducing `node.distill.prompt.request` and `node.distill.prompt`
  (`design.md:34-38, 60-63`). The current control boundary requires a request id,
  authenticated returned node id and a registered waiter/result handler (compare
  `GatewayControl.request_node_prompt_preview()` and
  `_handle_node_prompt_preview()` at `src/IM/ws/gateway/control.py:472-520,
  863-887`, plus `GatewayRuntime` dispatch at `runtime.py:24-50, 145-161`). The
  delta says only “prompt or understandable error”, leaving result shape,
  correlation and malformed/wrong-node response handling to worker inference.

  **Recommended revision.** Say “no new *ordinary relay* message type”, and add
  the lean request/result schema: generated `request_id`, authenticated `node_id`,
  success `{prompt}` or stable actionable error; the IM waiter treats disconnect/
  timeout as the existing prompt-error state. This is a single control RPC, not a
  recovery protocol or a new relay lifecycle.

- **[R5-W2][WARNING] [tasks.md test strategy] The test plan has the right small shape but does not satisfy the repository's required affected-test disposition, making the requested test pruning unverifiable.**

  The proposed permanent seams are appropriately few: rewrite the conversation
  API/repository projection, extend a control/API seam and the existing frontend
  journey, plus one semantic Gateway resolver test; the two-Gateway browser run is
  correctly temporary (`tasks.md:16-27`). That is consistent with
  `docs/development/testing.md:7-20, 75-82`. But the file does not name current
  tests or give `keep`/`rewrite-merge`/`delete` dispositions as required by
  `testing.md:22-32, 95-113`. The affected set is already concrete:
  `tests/im_service/integration/test_users_conversations_api.py`,
  `tests/im_service/unit/test_repositories_user_conversation.py`,
  `chat-workspace.integration.test.tsx`, and
  `components/conversation-sidebar.test.tsx`. In particular, the nested scanner
  test is genuinely retired, while the API/repository and frontend user outcomes
  need rewrite/merge rather than blind deletion.

  **Recommended revision.** Add the compact required table and name the existing
  control seam and the proposed resolver test's final owner/path. Do not add
  duplicate browser/E2E coverage; retain the one-off dual-Gateway evidence only.

### Recommendations

1. Keep v5's minimal sequence and its removal of recovery, metadata and hidden
   injection. Resolve C1–C3 by stating the now-visible path policy, one durable
   same-node handoff, and one local capability preflight.
2. Make the control RPC as small as the existing prompt-preview RPC rather than
   inventing an operation log, receipt or transcript transport.
3. In the test table, delete scanner-specific assertions, rewrite only the
   formerly path-based public/selection assertions into `source_node_id` and
   prompt-result behaviour, and leave two-Gateway validation as progress evidence.

### Full coverage inventory

| Inventory | Atoms reviewed | Result and disposition |
|---|---|---|
| Current-state assertion | IM scans `workspace_root` to project `source_jsonl_path` (`design.md:13-15`) | **Pass.** Repository code performs this scan and returns the resolved path (`src/IM/infra/repositories/conversations.py:683-737`); deleting it directly addresses the cross-host defect. |
| Current-state assertion | Browser treats the path as eligibility and builds the visible ordinary draft | **Pass.** Current `distill-selection.ts:3-18` and `chat-workspace-page.tsx:195-213, 980-995` match v5's replacement source of truth. |
| Current-state assertion | Existing skill/capability preflight | **Blocked by R5-C3.** It is a user-visible pre-chat protection, not scanner baggage; v5 must retain it or explicitly replace it locally. |
| Current-state assertion | Ordinary relay selects a node at send time | **Blocked by R5-C2.** The current code proves that v5 cannot merely assert the necessary node continuity. |
| Current-state assertion | Gateway-local binding and builtin read the current-format paths | **Pass.** This is the correct local owner for v5; no transcript bytes need cross the RPC boundary. |
| Incident reproduction/RCA | Separate IM/Gateway filesystems make IM scanning invalid (`incident.md:20-40`) | **Pass.** v5 removes the invalid scan rather than adding a host-sharing assumption. |
| Incident Q1 / non-goal | feat-515 creation recovery remains separate | **Pass.** v5 correctly withdraws all recovery work. |
| Incident Q2 / repair direction | Gateway ownership and no path exposure | **Blocked by R5-C1.** Ownership is right; the stipulated visibility is intentionally reversed without an authoritative clarification. |
| Incident Q3 | One selected Gateway only | **Blocked by R5-C2.** D1/D2 preflight selection is correct, but its promise must survive the subsequent ordinary send. |
| Incident unavailable/offline requirement | Clear pre-chat source/capability/offline feedback | **Blocked by R5-C3; otherwise Pass.** Binding/path/offline failures are specified; capability is omitted. |
| Incident acceptance proof | Isolated filesystems and no IM path access | **Blocked by R5-C1.** Keep the isolated-topology proof, but change the obsolete “path never appears” assertion to “IM never owns filesystem access”. |
| D1 | `source_node_id` projection, same-node selection and executor picker | **Pass with R5-C2.** It removes path-derived eligibility and correctly limits UI selection; source/executor ownership must be tied to the later handoff. |
| D2 | Owner/idle/node validation and prompt request before conversation creation | **Blocked by R5-C3 and R5-W1.** The ordering and IM-owned validation are right; local capability and the RPC result contract are incomplete. |
| D3 | Raw returned prompt, editable intent, ordinary relay and unchanged builtin | **Blocked by R5-C1/C2.** This is the user-chosen minimal execution path once visible-path policy and selected-node continuity are made true. |
| D4 | Error before direct chat; post-success ordinary semantics unchanged | **Blocked by R5-C3.** It must include the retained capability failure. It correctly avoids special receipts/lifecycle for prompt-time errors. |
| Interface table | Browser/IM/Gateway/ordinary-chat ownership | **Blocked by R5-C2/W1.** The owner split is sound; “ordinary chat” needs an authoritative selected-node association and control-frame result handling needs a precise home. |
| Frontend/prototype | Same-node selection, existing dialog and current-format visible draft | **Pass with R5-C1/C3.** No visual rebuild is required; prototype acceptance must use the revised path policy and readiness failure. |
| IM Web Chat delta | Same-node source/executor, raw prompt prefill, prompt error/no empty chat, ordinary sidebar | **Blocked by R5-C3.** Add missing distiller/tool unavailable Scenario and the explicit post-prompt same-node guarantee from R5-C2. |
| IM gateway-relay delta | No ordinary relay metadata/receipt/idempotency change | **Pass.** This correctly captures v5's decision; do not revive the v1–v4 action protocol. |
| Gateway relay-protocol delta | Binding-to-path prompt, no transcript/model/session creation, all-or-nothing source failure | **Blocked by R5-C2/C3/W1.** Add only local readiness and correlated control-result semantics; it must not describe a new model run or transcript API. |
| Kernel/CLI delta | None | **Pass.** v5 leaves builtin parsing/execution and CLI untouched. |
| M1 exit | Cross-host same-node prompt→ordinary-message journey; no IM scan; cross/running/offline/unparsable pre-chat failures | **Blocked by R5-C2/C3.** Add selected-node continuity and unavailable-skill outcome; no recovery or permanent E2E expansion. |
| Test plan and temporary acceptance | Projection rewrite, sidebar lock, resolver, control/API, frontend journey, one-off dual Gateway | **Warning R5-W2.** The test count/layers are restrained and appropriate, but exact old-test disposition and permanent owner paths must be written. |

### Architecture attack

| Angle | Assessment |
|---|---|
| Ownership | v5 correctly transfers filesystem access to Gateway. R5-C1 makes the changed visibility decision explicit; R5-C2 prevents an A-local path from reaching B; R5-C3 keeps runtime skill availability with its local owner. |
| Necessity | A prompt RPC plus unchanged ordinary relay is the narrow solution requested. A transcript RPC, hidden injection, durable operation/recovery protocol, new receipt lifecycle, cross-Gateway transfer, or permanent full-stack E2E is unnecessary. |
| Deep vs. shallow | Gateway should hide binding→path discovery behind its prompt handler; IM should only validate user/conversation/node identity and await one result. R5-W1 asks for the smallest observable wire, not an abstraction layer. |
| Root cause | Removing IM scanning eliminates the actual cross-machine failure. Letting its returned paths route to a different Gateway would recreate the failure at a later boundary, which is why R5-C2 is essential. |

### Conclusion

Return v5 to `change-design-author` for a narrow v5.1. It should clarify the
intentional visible-path policy, make “same Gateway through ordinary send” true,
retain the local capability preflight, and write the standard small test
disposition table. Once those changes are made, the unit can return for a delta
closure review; it does **not** need a return to the abandoned recovery/transcript
or metadata architecture.

## Round 6

### Metadata

| Field | Value |
|---|---|
| Reviewer target | `bugfix-518-gateway-owned-skill-distill@design-v5.1` |
| Review mode | delta |
| Mode reason | v5.1 is bounded to R5's visible-path clarification, correlated control RPC, node-pinned direct conversation, readiness retention and test disposition. The previous full inventory remains valid except for those changed atoms and their ordinary-relay/control-boundary effects. |
| Started | 2026-08-09T02:13:00+08:00 |
| Finished | 2026-08-09T02:19:28+08:00 |
| Duration | 6m 28s |

### Verdict

**REVISE — 1 CRITICAL / 1 WARNING.** v5.1 correctly keeps the requested minimal
architecture and closes four of the five R5 findings. Its node pin is not yet
authoritative against the existing public message-request override, so the core
same-Gateway guarantee can still be bypassed. No recovery, metadata relay or
hidden input injection should be restored.

### Historical issues closure

| Historical item | Author resolution | This-round verification | Status |
|---|---|---|---|
| R5-C1 | Incident Q2 and repair direction now explicitly accept Gateway-produced paths in the prompt/IM/browser/ordinary message, while forbidding IM filesystem ownership. | `incident.md:15-19, 45-51` and `design.md:18-26` agree on the intentional visible-path policy and replace the obsolete no-path acceptance claim with no-IM-access evidence. | **closed** |
| R5-C2 | Prompt success creates a conversation with opaque `target_node_id`; ordinary direct relay is declared to prefer it over later profile rebind. | This is the right minimal state owner and handles profile re-registration (`design.md:72-79`; `specs/im/gateway-relay.md:3-7`). However the current message API lets its caller override resolution with `target_node_id`; see R6-C1. | **partially closed; reopened narrowly as R6-C1** |
| R5-C3 | Retain browser distiller/`skill_view` preflight and repeat the final check locally in Gateway prompt generation. | D2/D4, Web IM and Gateway deltas consistently require pre-chat failure/no conversation, with no new execution lifecycle (`design.md:56-70, 81-85`; `specs/im/web-chat-ux.md:26-34`; `specs/gateway/relay-protocol.md:25-28`). | **closed** |
| R5-W1 | Define request id, authenticated node id, success/error result and timeout/malformed handling as one short-lived control waiter. | D2 now mirrors the existing authenticated control pattern: `GatewayRuntime` authorizes and normalizes sender node identity before dispatch (`src/IM/ws/gateway/runtime.py:109-161`; `src/IM/ws/gateway/sessions.py:350-391`). The contract is sufficient without a durable operation. | **closed** |
| R5-W2 | Add affected-test disposition and retain a small permanent test shape. | `design.md:124-132` names the path/scanner/frontend dispositions and `tasks.md:20-30` stays appropriately lean. The required disposition table still belongs in `tasks.md`, and the control seam is not named; see R6-W1. | **partially closed** |

### Issues

- **[R6-C1][CRITICAL] [D3, IM gateway-relay delta, M1] A pinned conversation does not win over the existing caller-controlled `target_node_id`, so it cannot yet guarantee same-Gateway path use.**

  D3 says the browser cannot specify a target node and ordinary relay prefers the
  conversation pin (`design.md:74-79`). In the actual public message request,
  however, `CreateMessageRequest` accepts `target_node_id`
  (`src/IM/api/routes/messages.py:70-86`) and the route selects that value *before*
  `service.resolve_target_node_id()` (`messages.py:413-421`). A caller can therefore
  post a message in the new pinned distill conversation with node B, bypass the
  A pin, and send A-local paths to B. The frontend not rendering the field does not
  enforce the claimed service contract.

  **Required revision.** Specify that for a direct conversation with an internal
  non-empty pin, IM ignores or rejects any caller-supplied `target_node_id` and
  resolves to the pin before the legacy client hint; unpinned conversations retain
  their current route behaviour. Add the lowest HTTP/relay outcome to the existing
  message API seam: a pinned distill conversation receives a caller hint for B
  after its Agent rebinds, but its relay task still targets A (or the request is
  explicitly rejected). Without this, worker implementation can pass a benign
  rebind test yet leave the cross-Gateway path failure reachable through the
  existing API.

- **[R6-W1][WARNING] [tasks.md test strategy] The R5 test-pruning disposition is in `design.md`, but still not in the required `tasks.md` table and leaves the real control/message test owners unnamed.**

  The proposed tests are not excessive: Gateway request/result behaviour already
  has focused owners in `tests/im_service/unit/test_gateway_handler.py` and
  `tests/unit/personal_assistant/test_gateway_im_connection_behavior.py`; the
  caller-override outcome belongs in the existing HTTP seam
  `tests/im_service/integration/test_messages_api.py`. `tasks.md:18-30` instead
  says only “existing Gateway control/API seam”, while the required
  per-affected-test disposition table remains only in `design.md:124-132`.
  `docs/development/testing.md:22-41, 95-113` requires that table and a concrete
  owner in `tasks.md`.

  **Recommended revision.** Copy a compact disposition table into `tasks.md`, name
  the above existing files, and add the R6-C1 assertion there. Keep the one new
  semantic resolver test and temporary dual-Gateway browser evidence; do not add a
  parallel transport matrix or permanent browser E2E.

### Recommendations

1. Make the direct-conversation pin authoritative at the existing message-route
   selection point; it is a narrow priority rule, not a special relay protocol.
2. Retain the v5.1 design otherwise: short-lived correlated RPC, Gateway-local
   readiness/path discovery, visible current-format draft and ordinary builtin.
3. Finish the test record in `tasks.md` so scanner-only assertions are deleted and
   every retained permanent test has one clear seam owner.

### Delta coverage

| Rechecked atom | Evidence and result |
|---|---|
| Visible-path policy / incident repair | **Pass.** Incident, D3 and both user-facing deltas now make the user-approved tradeoff explicit; the boundary is IM filesystem access, not path-string display. |
| D2 correlated prompt control RPC | **Pass.** The request/result carries the only needed correlation and uses authenticated sender-node normalization. It names disconnect, timeout, malformed and wrong-node outcomes without creating recovery state (`design.md:64-70`). |
| D3 node-pinned direct conversation | **Blocked by R6-C1.** Storing a server-only conversation pin is the correct minimal design and survives profile rebind, but current message API precedence must be reversed/restricted for the pin to be authoritative. |
| D4 browser plus Gateway readiness | **Pass.** Browser preflight gives immediate dialog feedback; Gateway recheck covers stale/direct callers before prompt creation. Neither creates a new model, session or delivery path. |
| IM Web Chat delta | **Pass except R6-C1.** It preserves selection, no-empty-chat error, visible prompt and normal sidebar, and now specifies same-Gateway ordinary send (`specs/im/web-chat-ux.md:7-38`). |
| IM gateway-relay delta | **Pass except R6-C1.** It correctly has no new relay wire contract; its stated pin guarantee needs the server-side precedence rule. |
| Gateway relay-protocol delta | **Pass.** It remains consumer-observable: local binding/readiness, correlated prompt/error and no transcript/model/session creation (`specs/gateway/relay-protocol.md:5-28`). |
| M1 / tests | **Warning R6-W1.** The coverage dimensions are now the right minimum—projection, selection, control, pin/rebind, readiness, resolver and temporary real topology—but `tasks.md` needs exact existing-test ownership and the client-hint adversarial case. |
| Retained-from Round 5 | No recovery, metadata relay, internal prompt injection, builtin rewrite, Kernel/CLI delta, cross-Gateway transfer and permanent E2E remain out of scope; no v5.1 change invalidates that assessment. |

### Affected architecture attack

| Angle | Assessment |
|---|---|
| Ownership | Conversation-scoped node affinity belongs in IM, which already owns conversation routing. R6-C1 prevents a browser HTTP field from becoming a competing routing authority for the one conversation that carries Gateway-local paths. |
| Necessity | The pin is necessary only because v5 restores visible paths; short-lived control correlation and two readiness checks are sufficient. No durable prompt operation, receipt protocol or transcript service is justified. |
| Depth | Gateway still hides binding→path/readiness behind one prompt response; IM hides pin storage and route selection. Reversing a single priority rule is deeper and smaller than inventing special metadata. |
| Root cause | v5.1 removes IM's remote scan. Enforcing the pin closes the remaining route by which an A-local path can be delivered to B despite that fix. |

### Conclusion

Return to `change-design-author` for one v5.2 correction: make the internal
conversation pin override/reject the request's target-node hint, and record its
single existing HTTP/control test owners in `tasks.md`. With that closure, the
minimal Gateway-owned-prompt design can proceed without reviving any withdrawn
subsystem.

## Round 7

### Metadata

| Field | Value |
|---|---|
| Reviewer target | `bugfix-518-gateway-owned-skill-distill@design-v5.2` |
| Review mode | delta |
| Mode reason | v5.2 is confined to the two R6 corrections: server-pinned direct-conversation routing takes priority over the legacy client hint, and `tasks.md` now records the affected-test dispositions. The prior full review remains valid for all other atoms. |
| Started | 2026-08-09T02:20:00+08:00 |
| Finished | 2026-08-09T02:24:17+08:00 |
| Duration | 4m 17s |

### Verdict

**APPROVE — 0 CRITICAL / 0 WARNING.** v5.2 closes both R6 findings with one
server-side route-priority rule and focused ownership of existing test seams.
The resulting journey is still exactly the approved minimum: choose an Agent on
one Gateway → that Gateway returns the existing complete prompt → ordinary chat
continues on the same Gateway. It introduces no recovery, transcript, relay
metadata, or prompt-injection subsystem.

### Historical issues closure

| Historical item | Author resolution | This-round verification | Status |
|---|---|---|---|
| R6-C1 | A direct conversation with a non-empty internal `target_node_id` pin resolves that pin before the legacy `CreateMessageRequest.target_node_id`; the caller hint is ignored. Unpinned conversations retain existing routing. | D3, the Web Chat delta and the IM gateway-relay delta now state the same server-authoritative rule; `tasks.md` assigns the rebind-plus-conflicting-hint outcome to `tests/im_service/integration/test_messages_api.py`. This removes the only route by which an A-local prompt could be redirected to B through the public API. | **closed** |
| R6-W1 | `tasks.md` now contains an affected-test disposition table and names the existing Gateway-handler, Gateway-connection, and message-API seams. | The table preserves the required scanner/frontend rewrites, retains one focused control seam and one message-routing seam, and deletes no required behavioral coverage. It follows `docs/development/testing.md` without adding a parallel transport matrix or permanent browser E2E. | **closed** |
| R5 closures retained in R6 | Visible user-approved paths, correlated short-lived control RPC, and browser-plus-Gateway readiness checks were already closed. | v5.2 changes none of their ownership or failure semantics. The mandatory pin priority is a single IM message-route rule, not a new Gateway protocol. | **remain closed** |

### Issues

None.

### Recommendations

1. Implement the documented priority at the existing IM direct-message route:
   read the conversation's internal pin first, then consult the legacy client
   hint only when that pin is absent.
2. Keep the named focused tests; do not revive removed scanner-only tests,
   transport duplication, or a permanent two-Gateway browser suite.

### Delta coverage

| Rechecked atom | Evidence and result |
|---|---|
| Authoritative same-Gateway route | **Pass.** `design.md` D3 gives the server-side conversation pin precedence over the legacy request hint and preserves legacy behavior only for unpinned conversations. The corresponding IM/Web deltas make the rule externally consistent. |
| Rebind plus conflicting client hint | **Pass.** The single message-API test disposition covers the exact prior escape hatch: even after later profile rebind and a caller hint for B, the pinned conversation routes to A. |
| Gateway-owned prompt boundary | **Pass.** D2/D4 retain local Gateway binding/readiness and return the existing complete prompt through one correlated request/result. IM neither scans nor reads a Gateway filesystem path. |
| Minimal user journey | **Pass.** Selection remains scoped to one ready Agent/Gateway; success creates the normal direct conversation and uses normal chat. No intermediate delivery chain, special message type, or UI-managed transcript is specified. |
| Scope exclusions | **Pass.** `design.md` and all three current-spec deltas continue to exclude recovery state, transcript retrieval, relay metadata, internal prompt injection, model/session creation, cross-Gateway transfer, and builtin rewrite. |
| Test disposition | **Pass.** `tasks.md` has the required affected-test table with concrete owners for control and routing semantics, while keeping temporary real-topology evidence non-permanent. |

### Affected architecture attack

| Angle | Assessment |
|---|---|
| Ownership | IM owns the conversation and its internal route pin; Gateway owns local path discovery and prompt construction. The browser has no routing authority for a pinned conversation. |
| Necessity | One priority check at the existing message-routing seam is sufficient to preserve the restored visible-path experience safely. A separate route protocol or metadata channel would add no user value. |
| Depth | The pin remains an opaque conversation detail and the Gateway exposes only a prompt/error result. Existing normal-chat and builtin behavior stay undisturbed. |
| Root cause | The former defect was IM-side remote filesystem discovery. The design removes it, and the pin rule prevents the remaining client hint from sending the returned local path to another Gateway. |

### Conclusion

v5.2 is ready for `change-orchestrator`. Implement the narrow IM pin-priority
rule and the listed focused tests; keep the Gateway control RPC and normal-chat
path otherwise unchanged.

## Round 8

### Metadata

| Field | Value |
|---|---|
| Reviewer target | `bugfix-518-gateway-owned-skill-distill@design-v5.3` |
| Review mode | delta |
| Mode reason | v5.3 only records the retained external-shadow binding fallback in the Gateway relay delta. |

### Verdict

**APPROVE — 0 CRITICAL / 0 WARNING.** The delta keeps the external identity
private to IM→Gateway control, tries the normal `web_relay` durable binding
first, and falls back only when an existing external-shadow binding is present.
It does not reintroduce IM filesystem access, browser-provided paths, or a
second transcript mechanism.

### Conclusion

v5.3 remains ready for implementation and verification.

## Round 9

### Metadata

| Field | Value |
|---|---|
| Reviewer target | fallback independent reviewer `bugfix_518_code_finder` |
| Review mode | narrow delta |
| Mode reason | The original reviewer could not be resumed because the agent-thread limit was reached. This round covers only v5.4's reviewer runbook. |

### Verdict

**APPROVE — 0 CRITICAL / 0 WARNING.** The runbook now gives the reviewer direct
frontend cwd/port commands, a distinct second-Gateway config/runtime/workspace,
explicit launch and authenticated registration check, plus cleanup. It is
operational acceptance guidance only and changes no product behavior,
architecture, or protocol contract.

### Historical issue closure

| Item | Resolution | Status |
|---|---|---|
| R9-W1 | Added explicit Vite cwd/free port and second Gateway derivation/start/readiness commands. | **closed** |

### Conclusion

v5.4 is ready for the independent reviewer and verifier gates.

## Round 10

### Metadata

| Field | Value |
|---|---|
| Reviewer target | fallback independent reviewer `bugfix_518_code_finder` |
| Review mode | narrow delta |
| Mode reason | v5.5 adds only a test-only no-`skill_view` execution Agent to the second isolated Gateway reviewer fixture. |

### Verdict

**APPROVE — 0 CRITICAL / 0 WARNING.** The explicit `tool_allowlist: [read]`
deterministically excludes `skill_view`, while the distinct node, Agent and
runtime state keep it out of every production/default configuration. The
runbook now lets the reviewer exercise D2's visible preflight failure in place,
without a prompt RPC or empty `Skill distill` chat.

### Conclusion

v5.5 is ready for targeted product re-acceptance.
