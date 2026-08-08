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
