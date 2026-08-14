# Design Review: feat-523

## Round 1

### Metadata

- reviewer: `/root/feat_523_design_review`
- review_mode: `full`
- mode_reason: `R1 requires a complete review of every bearing design atom and all architecture attack angles.`
- started_at: `2026-08-14T22:07:00+08:00`
- completed_at: `2026-08-14T22:17:25+08:00`
- duration: `10m 25s`

### Verdict

Issues Found — 2 CRITICAL / 1 WARNING

### Coverage

- Read the complete `spec.md`, `design.md`, and Gateway delta spec. The inventory covers the three first-spec requirements and all seven scenarios, both clarification records, both scope statements, the delta requirement and its four scenarios, all twelve present-state/reusable-capability claims, decisions 1–4, and M1.
- Traced the production composition path from `build_gateway_runtime()` through `_send_external_reply()` and `build_kernel_event_observer()` (`src/personal_assistant/gateway/composition.py:331-349,505-519`), then both external-final paths: observer `_mirror_external_reply()` (`runtime_delivery/observer.py:312-364`) and coordinator `_deliver_final_reply()` (`session_run_coordinator.py:1426-1480`).
- Checked the owning Gateway contracts: external replies are complete assistant bubbles, final bubbles must not be repeated, and runtime telemetry is not an ordinary external message (`docs/specs/gateway/external-channels.md:125-144`); external trigger vs internal-shadow direction is fixed separately (`docs/specs/gateway/external-channels.md:93-123`).
- Checked configuration and delivery facts: `LocalConfig`/`RuntimeConfigOwner` are immutable config snapshot owners (`config/local_store.py:317-379,582-625`); accepted lifecycle currently has no model field (`gateway/inbound_models.py:197-208`); `RunDeliveryContext` is seeded from that accepted update (`runtime_delivery/context.py:359-449`); `turn_end` carries usage/context-window (`agent/platform/hooks/builtins/realtime_stream.py:199-218`).
- Checked isolation/runbook grounding against the actual Feishu E2E contract (`docs/development/worktree-runtime.md:14-21,30-38,79-92`) and the concrete launcher/probe (`scripts/e2e-up.sh:167-177`, `scripts/e2e-feishu-probe.py:92-149`).

### 核实台账

| 类型 | 原子 | 核实与证据 | 结论 |
|---|---|---|---|
| 现状 | `local_store` 是 typed config + snapshot owner | `LocalConfig` owns the complete local document and `RuntimeConfigOwner.snapshot()` returns the current immutable value (`config/local_store.py:317-379`); parsing and construction are centralized at `:582-625`. | 成立 |
| 现状 | coordinator resolves one run model but accepted update lacks it | `_project_runtime()` resolves the model and builds `SessionRuntimeConfig(model=...)` (`session_run_coordinator.py:1562-1579`; `session_composition.py:82-97`), while the accepted update has only ids (`session_run_coordinator.py:1258-1267`) and the DTO has no model (`inbound_models.py:197-208`). | 成立 |
| 现状 | observer owns normal external bubble mirror and shadow stores plain content first | `_mirror_external_reply()` prepares `cleaned_text` for shadow before scheduling the external send (`observer.py:320-364`); its final dispatch occurs on terminal turn handling (`observer.py:1469-1478`). | 成立 |
| 现状 | coordinator retains an external terminal fallback | `_deliver_final_reply()` writes external shadow content then sends through the router for external inbound (`session_run_coordinator.py:1449-1479`). | 成立 |
| 约束 | Gateway—not adapter or IM—owns this product rule | Composition is the only normal sender that turns metadata into `ReplyContext` (`composition.py:331-349`); the external-channel spec fixes external-vs-shadow direction (`external-channels.md:93-123`). | 成立 |
| 约束 | complete-bubble and final-dedupe boundaries must survive | Canonical spec requires no repeat at terminal (`external-channels.md:125-144`); router establishes a cross-path semantic final-text dedupe key (`outbound_router.py:65-81`). | 成立，但 design 的 parity 设计不足，见 R1-C2 |
| 约束 | missing usage/window and disabled config do not fabricate output | The realtime event only includes `context_window` when positive (`realtime_stream.py:212-218`); first spec explicitly requires partial/no-footer behavior (`spec.md:38-43`) and default-off (`:47-50`). | 成立 |
| 约束 | real Feishu validation is isolated | Worktree documentation requires isolated config/data/identity and prohibits the main config (`worktree-runtime.md:14-21`); dedicated E2E credentials/profile are guarded (`:30-38`). | 成立 |
| 决策 | D1 final-only placement | The listed observer final and coordinator terminal path are the two actual normal-final paths; controls use a separate `_deliver_control_reply()` route (`session_run_coordinator.py:1825-1845`). | 不成立为可实施决策：与 D4 的 sole-caller statement 矛盾，见 R1-C1 |
| 决策 | D2 global + platform config, fixed fields | Fixed `model · context_pct` is within first spec scope (`spec.md:70-73`); platform prefix matches existing Feishu channel names (`external-channels.md:84-91`). | 成立，but positive override acceptance is missing，见 R1-W1 |
| 决策 | D3 admission model + terminal context facts | Admission can carry `runtime_projection.runtime.model`; the coordinator stream sees the same events before `_deliver_final_reply()` (`session_run_coordinator.py:1185-1272,1876-1956`), while `turn_end` is the source of `context_window`. | 不完整：facts must be made identical across paths，见 R1-C2 |
| 决策 | D4 small pure footer module, no adapter port | No existing equivalent footer module exists; `OutboundRouter` is deliberately generic (`outbound_router.py:14-56`), so a pure Gateway helper avoids per-adapter copies. | 归属合理，但 caller ownership conflicts with D1，见 R1-C1 |
| spec | final external reply shows model + context | D1/D3 and the flow target the final external send; delta Scenario 1 preserves the actual-token requirement (`specs/gateway/external-channels.md:9-13`). | 覆盖，但 parity gap blocks reliable completion，见 R1-C2 |
| spec | intermediate, tool, approval, control have no footer | D1 excludes all these paths and delta Scenario 3 states the observable boundary (`specs/gateway/external-channels.md:21-25`). | 覆盖 |
| spec | partial/no data silently omits | D3 plus delta Scenario 4 specifies partial / no footer (`specs/gateway/external-channels.md:27-32`). | 覆盖 |
| spec | default-off, global enable, channel override | D2’s default and precedence shape covers it; first spec’s override scenario is global-on → channel-off (`spec.md:47-61`). | 覆盖 baseline; one useful polarity is absent，见 R1-W1 |
| spec | Web IM remains plain | D1 preserves `cleaned_text` in shadow and D3 does not write back to the context; delta text explicitly preserves Web IM shadow (`specs/gateway/external-channels.md:5-7`). | 覆盖 |
| spec | non-goals | D2 fixes two fields and rejects command/field configurability; D1 excludes all process/control bodies. No client, token count, cost, cwd, or adapter-specific implementation is introduced. | 不越界 |
| delta | added Gateway requirement | This is a true additive final-reply presentation rule, anchored at the narrow external-channels area; scenarios are externally observable and retain the existing mirror requirement untouched. | 成立 |
| milestone | M1 vertical slice / two exit tracks | One end-to-end M1 includes config, lifecycle, both delivery paths, unit tests, delta, and real Feishu evidence; it contains both reviewer and worker exit criteria (`design.md:168-170`). | 成立，but must add R1-C1/C2 closure targets |

### 架构进攻

| 角度 | 检查 | 发现 |
|---|---|---|
| 归属 | Tested placing policy in adapter/router versus Gateway delivery layer. | Gateway is the natural owner: router only normalizes a `ReplyContext`, and adapters are provider transports. The proposed `runtime_footer` location avoids an `IM -> personal_assistant` inversion. No separate issue. |
| 该不该存在 | Deleted the proposed helper mentally and placed precedence/formatting at both callers. | That would duplicate partial-data and platform-override semantics. A small pure helper is justified; a factory/protocol for one implementation is not. The document nevertheless contradicts who calls it (R1-C1). |
| 深/浅 | Searched the Gateway and test tree for an existing footer-policy primitive and compared the public surface with its hidden policy. | There is no reusable runtime-footer equivalent. A `config + adapter-name + run facts -> optional footer` operation hides meaningful precedence/normalization, so it is deep enough; no new adapter port is needed. |
| 治本/补丁 | Tested the design against the actual final-dedupe mechanism instead of appending a second message or modifying adapters. | Keeping one bubble and formatting before the normal send is the right root-level direction. But cross-path dedupe keys are based on the text actually sent; unspecified terminal-fact propagation can turn this into duplicate finals (R1-C2). |

### Issues

- [R1-C1][CRITICAL] [决策 1 / 决策 4 / 架构总览] The document gives mutually exclusive ownership for the formatter. Decision 1 says both `_mirror_external_reply(phase="final")` and `SessionRunCoordinator._deliver_final_reply()` call it (`design.md:60-64`), and the graph draws both paths into `Footer` (`:44-52`); Decision 4 then says “observer is the only caller” (`:94-98`). Choose one exact contract and wiring: for example, make the pure helper a composition-injected dependency used by *both* named normal-final call sites, while all intermediate/control/approval/background paths remain outside it. If uncorrected, a worker can faithfully implement observer-only behavior and omit the footer from the no-shadow fallback, or move it into a too-broad shared sender and accidentally decorate nonordinary final messages.

- [R1-C2][CRITICAL] [决策 1 / 决策 3 / 接口与数据流] The design requires observer and coordinator output parity but does not define how the coordinator receives the same terminal footer facts. The observer sees `turn_end` with `context_window` (`src/agent/platform/hooks/builtins/realtime_stream.py:199-218`); `_await_terminal_run()` currently returns only the terminal `run_status` and reply text (`session_run_coordinator.py:1876-1956`), and `_extract_usage()` only consumes `run_state["usage"]` without a context window (`:2106-2121`). This is not merely an implementation detail: router cross-path final dedupe includes the physical final text (`outbound_router.py:76-80`). Require a concrete shared `TerminalFooterFacts` carrier and specify its lifetime/hand-off—e.g. capture the completed `turn_end` facts in `_await_terminal_run`, return them alongside `run_state`, and pass them with the admission-frozen model to both named format calls. Then require identical decorated final text for the two routes. Without it the observer can send `answer\n\nmodel · 42%` while coordinator fallback sends `answer\n\nmodel` or plain `answer`, defeating semantic dedupe and violating the canonical no-duplicate-final scenario.

- [R1-W1][WARNING] [决策 2 / M1 exit criteria] The precedence rule says a platform setting overrides global whenever `enabled` is explicitly present (`design.md:72-85`), but the delta and M1 only exercise global-on → Feishu-off (`spec.md:57-61`; `design.md:170`). Add the symmetric `global=false, platforms.feishu.runtime_footer.enabled=true` scenario/test (and describe it in delta if that is intended behavior), or explicitly limit override to suppression. Otherwise the default-off setting cannot be safely enabled for only the currently deployed Feishu channel once a second external channel exists, and implementers may encode a disable-only exception despite the documented general precedence rule.

### Recommendations

- [R1-R1] Keep the existing `cleaned_text` shadow record and apply the footer only to the external copy after that record; this is the right way to preserve Web IM’s plain bubble.
- [R1-R2] After resolving the two critical data-flow decisions, add focused tests that make the observer-first and fallback-only routes produce identical decorated text and assert the router emits exactly one final bubble.

### Author Resolutions

| Issue | Resolution | Evidence |
|---|---|---|
| R1-C1 | accepted — observer is now the sole formatter caller. It builds one terminal external projection; the observer mirror and coordinator fallback are named consumers only. | `design.md` 决策 1、决策 4、架构图与时序图已统一该 owner。 |
| R1-C2 | accepted — `TerminalFooterFacts` and `RunDeliveryContext.external_final_text` are now explicit run-owned carriers. The projection is created before observer's `message_id` branch, so fallback reads the same byte string rather than reconstructing facts/config. | `design.md` 决策 1/3、接口与数据流、风险与 M1 worker exit criterion。 |
| R1-W1 | accepted — platform override is full precedence, not disable-only; added the global-off / Feishu-on acceptance scenario to the first spec and Gateway delta. | `spec.md` “单一外部 channel 可以独立开启”；`specs/gateway/external-channels.md` 同名 Scenario；`design.md` M1。 |

## Round 2

### Metadata

- reviewer: `/root/feat_523_design_review`
- review_mode: `full`
- mode_reason: `R1-C1/C2 changed the core caller ownership and cross-path terminal data flow, so a closure or delta review could not safely inherit the former architecture attack.`
- started_at: `2026-08-14T22:22:24+08:00`
- completed_at: `2026-08-14T22:22:52+08:00`
- duration: `28s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R1-C1 | observer becomes the sole formatter caller; observer mirror and coordinator fallback only consume the cached projection. | D1 now says exactly this (`design.md:62-68`), D4 repeats observer-only ownership (`:96-100`), and both diagrams show the cached context projection rather than a second formatter call (`:39-55,111-134`). | closed |
| R1-C2 | run-owned `TerminalFooterFacts` and `external_final_text` provide one terminal projection. | D3 fixes facts to the successful `turn_end` and makes fallback read the cached string only (`design.md:90-94`); interface section names both carriers and the no-reformat rule (`:102-109`). This matches actual router semantic dedupe over sent text (`src/personal_assistant/gateway/outbound_router.py:65-81`). | closed |
| R1-W1 | platform precedence supports a positive override and is acceptance-tested. | First spec now covers global-off → one-channel-on (`spec.md:63-67`), and the Gateway delta carries the same consumer scenario (`specs/gateway/external-channels.md:21-25`); M1 includes “仅 Feishu 开启” (`design.md:182`). | closed |

### Coverage

- Re-read the revised first spec, all Gateway delta scenarios, the whole design, R1 evidence, and author resolutions. The revised bearing atoms include the new independent-enable first-spec scenario, corresponding delta scenario, decisions 1/3/4, both diagrams, shared-carrier interface, risk/recovery statement, and M1.
- Re-traced the unchanged production facts that constrain the revision: composition owns both observer construction and normal external sender wiring (`src/personal_assistant/gateway/composition.py:227-271,331-349,505-525`); observer gets terminal `usage/context_window` through `_turn_token_usage()` (`runtime_delivery/observer.py:496-522`) and final mirror currently uses `cleaned_text` for both shadow and sender (`:312-364,1469-1478`); coordinator runs fallback before emitting completed lifecycle (`session_run_coordinator.py:1268-1322,1426-1480`); context is discarded only by the later completed callback (`runtime_delivery/lifecycle.py:31-49,143-166`).
- Rechecked the canonical external channel contract: visible replies are whole bubbles, final bubbles cannot duplicate, and runtime telemetry remains non-message state (`docs/specs/gateway/external-channels.md:125-144`); the new delta adds presentation behavior without weakening these existing scenarios.

### 核实台账

| 类型 | 原子 | 本轮核实与证据 | 结论 |
|---|---|---|---|
| 现状 | typed config snapshot is a suitable policy input | `RuntimeConfigOwner.snapshot()` returns the current immutable `LocalConfig` (`config/local_store.py:341-379`), and parse/round-trip remain centralized in `local_store.py:582-625,889-932`. D2’s typed `display` extension therefore belongs at the existing boundary. | 成立 |
| 现状 | model can be frozen at admission | Projection resolves `SessionRuntimeConfig.model` before submit (`session_run_coordinator.py:1185-1202`; `session_composition.py:82-97`); accepted lifecycle then seeds `RunDeliveryContext` (`runtime_delivery/context.py:359-449`). D3’s added model field is a direct, one-way extension. | 成立 |
| 现状 | successful terminal facts are available to observer before fallback | Coordinator awaits the observer for every stream event before recognizing terminal `run_status` (`session_run_coordinator.py:1915-1935`); completed `turn_end` carries normalized prompt/window inputs (`observer.py:496-522`). Thus the projection is available before `_deliver_final_reply()`. | 成立 |
| 现状 | context lifetime covers fallback | `_deliver_final_reply()` happens before completed lifecycle emission (`session_run_coordinator.py:1298-1322`), while lifecycle discards only on completed/failed (`runtime_delivery/lifecycle.py:31-49,159-166`). | 成立 |
| 决策 | D1 single formatter / two consumers | The revised decision states observer formatting once, plain shadow record, external-only projection, and coordinator read-only fallback (`design.md:62-68`). It is compatible with the present observer’s combined shadow/external seam because it explicitly requires the implementation to retain plain `cleaned_text` for shadow and use `external_final_text` only for sender. | 成立 |
| 决策 | D2 global + full platform precedence | The config shape, default false, adapter-prefix normalization, and non-goals are fixed (`design.md:70-88`); both override polarities are now observable in first spec/delta (`spec.md:57-67`; `specs/gateway/external-channels.md:15-25`). | 成立 |
| 决策 | D3 exact common facts and byte-identical output | `TerminalFooterFacts` is created only from successful `turn_end`; fallback reads cached output and must not reformat (`design.md:90-94,102-109`). This exactly protects router’s `run_id:final_text:<text>` cross-path dedupe (`outbound_router.py:76-80`). | 成立 |
| 决策 | D4 small pure footer module | The module owns genuine policy complexity—precedence, adapter normalization, shortening, percentage, missing-data behavior—while `OutboundRouter` remains a generic transport (`outbound_router.py:14-56`). No speculative port/factory is introduced. | 成立 |
| spec | final external only; process/control/internal shadow excluded | D1 names intermediate/control/approval/tool/background and silence as having no projection (`design.md:64-66`); delta Scenario “非最终或内部消息” remains externally observable (`specs/gateway/external-channels.md:27-31`). | 覆盖且不冲突 |
| spec | model/context, partial data, no fabricated fields | Formatter facts and branch diagram retain the model-only/percent-only/plain outcomes (`design.md:90-94,136-151`); delta Scenario “运行信息缺失时静默省略” preserves the behavior (`specs/gateway/external-channels.md:33-38`). | 覆盖 |
| spec | default-off, global enable, both platform override polarities | D2 plus the three first-spec configuration scenarios cover default, global on, global-on/platform-off, and global-off/platform-on (`spec.md:47-67`). | 覆盖 |
| spec | Web IM unchanged and scope/non-goals | Shadow consumes plain text while only external sender consumes cached projection (`design.md:39,64-66,104-109`); no client, cwd, cost, token count, field customisation, or adapter-specific copy enters the plan (`spec.md:76-79`). | 覆盖且不越界 |
| delta | additive Gateway behavioral contract | The delta is a narrow ADDED external-channel presentation rule with only user-observable GIVEN/WHEN/THEN clauses (`specs/gateway/external-channels.md:3-38`), so it neither duplicates nor silently replaces canonical mirror/dedupe requirements. | 成立 |
| milestone | one vertical M1 and dual exits | M1 includes all layers needed for one observable result, parity/dedupe proof, all configuration cases, external screenshot evidence, and focused worker checks (`design.md:178-182`). | 成立 |

### 架构进攻

| 角度 | 检查 | 结论 |
|---|---|---|
| 归属 | Re-tested observer-only formatting against router, adapters, IM, and coordinator. | Observer has the terminal event facts; Gateway retains external product ownership. A read-only projection provider lets coordinator consume without taking formatting responsibility or reversing package dependencies. |
| 该不该存在 | Applied deletion test to `TerminalFooterFacts`, cached projection, and the pure module. | Removing the module duplicates policy; removing the cached projection forces coordinator to reconstruct unavailable context-window/config facts. Both additions eliminate a concrete cross-path inconsistency, not hypothetical extensibility. |
| 深/浅 | Compared helper surface with the details it hides. | `config snapshot + adapter name + immutable terminal facts -> optional appended text` substantially reduces caller knowledge. No existing helper has these semantics and no premature adapter abstraction remains. |
| 治本/补丁 | Tested against current cross-path dedupe and shadow/output split. | The plan formats once before either physical final send, preserves plain shadow text, and requires identical text for semantic dedupe. It resolves the root data-flow issue rather than adding a second footer message or adapter exception. |

### Issues

- None.

### Recommendations

- [R2-R1] Keep the parity test phrased in terms of physical text and one final outbound bubble; that directly guards the observed router contract rather than a private helper call.

## Round 3

### Metadata

- reviewer: `/root/feat_523_design_review_r3`
- review_mode: `delta`
- mode_reason: `The only new design atoms since Round 2 are the repository-owned Feishu E2E fixture enabling the opt-in footer and the reviewer prerequisite that names it. They do not alter the terminal delivery architecture, model/facts carriers, or product contract reviewed in Round 2.`
- started_at: `2026-08-14T22:52:00+08:00`
- completed_at: `2026-08-14T22:57:19+08:00`
- duration: `5m 19s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### Coverage

- Re-read the new fixture atom and reviewer prerequisite, plus the retained Round 2 decision and acceptance boundaries. `config/e2e/gateway.yaml:1-45` is repository-owned and contains no Feishu App credentials; it enables only `display.runtime_footer.enabled` while retaining the Feishu channel as disabled with empty settings.
- Traced the real launcher rather than treating the fixture as documentation: `scripts/e2e-up.sh:167-177` copies that fixture into worktree-local `.gateway-config.yaml`, injects private credentials only into that copy for `--feishu`, and makes the copy mode 0600. The documented runtime contract confirms the source fixture is never modified (`docs/development/worktree-runtime.md:26-37,83-87`).
- Rechecked the default policy input and its consumer-level coverage: absent `display` returns `DisplayConfig()` with `runtime_footer_enabled=False` (`src/personal_assistant/config/local_store.py:317-326,1472-1485`); the focused formatter test uses that default and preserves the plain answer (`tests/unit/personal_assistant/test_runtime_footer.py:14-27`). The fixture is therefore a deliberately enabled isolated test profile, not a production/local default change.
- Re-ran the reviewer journey prerequisites against the actual probe boundary: `e2e-feishu-probe.py` requires an active `--feishu` worktree and a verified non-default profile before it sends a nonce (`scripts/e2e-feishu-probe.py:83-149`), while the runbook explicitly prohibits reviewer-side config edits and requires cleanup (`design.md:168-176`).

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| Round 2 Approved | The terminal projection remains observer-owned and default-off. | The fixture and runbook are limited to E2E setup; no formatter ownership, facts hand-off, or canonical external-channel behavior changed. | retained_from: Round 2 |

### Delta 评审台账

| 原子 | 本轮核实与证据 | 结论 |
|---|---|---|
| Dedicated secret-free E2E fixture | The tracked fixture contains test IM credentials only, has no App ID/secret/Bot ID, and keeps `feishu:e2e` disabled (`config/e2e/gateway.yaml:1-45`). `--feishu` derives a private worktree copy before it renders channel credentials (`scripts/e2e-up.sh:169-175`). | 成立 |
| Default-off production/local behavior | The typed absent-config default is false (`local_store.py:317-326,1472-1485`); the sole `enabled: true` addition is under `config/e2e/`, whose launcher path is explicitly an isolated copy (`e2e-up.sh:167-177`; `worktree-runtime.md:83-87`). | 成立 |
| Zero-tracked-config-write, reproducible reviewer journey | The runbook fixes the known fixture instead of asking a reviewer to patch YAML (`design.md:172-176`). It names the isolated start, health and probe commands; the launcher rejects an explicit alternate main config with `--feishu` (`scripts/e2e-up.sh:124-135`) and the probe rejects a non-Feishu stack (`e2e-feishu-probe.py:83-89`). Generated worktree-local state and the deliberate test-chat message remain necessary runtime side effects, but neither mutates a tracked config nor reaches a production bot/profile. | 成立 |

### 架构进攻

| 角度 | 检查 | 结论 |
|---|---|---|
| 归属 | Tested whether opt-in belongs in a reviewer command or in the E2E fixture. | The fixture is the narrow ownership boundary: it is copied only into an isolated worktree and lets the runbook remain declarative. Putting this in reviewer instructions would reintroduce untracked manual configuration drift. |
| 该不该存在 | Applied deletion test to the one `enabled: true` stanza. | Removing it forces every real-Feishu reviewer to mutate config before validation, defeating reproducibility. It is a concrete fixture requirement, not a production compatibility switch. |
| 深/浅 | Compared the fixture with a new script flag or adapter-specific setup. | A six-line typed config fragment reuses the existing loader and launcher copy step; a new flag or parallel config generator would add a wider, shallower surface. |
| 治本/补丁 | Tested the flow against the earlier manual-enable failure mode. | Checked-in, secret-free opt-in plus private-copy credential injection fixes the source of reviewer configuration drift while preserving the existing isolation/lock guardrails. |

### Issues

- None.

### Recommendations

- [R3-R1] In reviewer evidence, state that “zero-write” means no tracked-config edit; the isolated launch necessarily creates disposable worktree runtime files and the real Feishu journey necessarily posts one message to the dedicated test chat.

## Round 4

### Metadata

- reviewer: `/root/feat_523_card_design_review`
- review_mode: `full`
- mode_reason: `Reviewer failover is required: the previous reviewer worker is not recoverable, and the user corrected the core Feishu contract from a plain-text footer to one native card. That change crosses the external consumer contract, adapter transport, payload form, delta-spec reconciliation, and E2E proof boundaries, so Round 1–3 approval cannot be retained as a delta or closure review.`
- started_at: `2026-08-15T01:29:06+08:00`
- completed_at: `2026-08-15T01:33:03+08:00`
- duration: `3m 57s`

### Verdict

Issues Found — 3 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| Round 1–3 approvals | Those rounds approved the now-superseded plain-text footer design and its isolated fixture. | `HEAD` already contains the archived feature's canonical requirement, which still says to append a text footer (`docs/specs/gateway/external-channels.md:148-181`); the active first spec and D3 instead require a native interactive card (`spec.md:31-36`; `design.md:75-81`). The prior reviewer cannot be resumed, so its prior conclusion is not an effective Gate 2 approval for this user-corrected contract. | superseded — re-reviewed in full |
| R1-C1/R1-C2/R1-W1 | The former author resolutions established observer-owned, cached final text and full config override precedence. | The revised design retains a single run-owned projection, unchanged shadow body, and two consumers (`design.md:59-65,83-120`); current Gateway wiring still exposes the observer cache to the fallback and preserves final-text dedupe (`runtime_delivery/observer.py:533-561`; `session_run_coordinator.py:1639-1697`; `outbound_router.py:180-195`). | retained as architecture evidence, not as approval |

### Coverage

- Read the complete active `spec.md`, `design.md`, Gateway delta spec, all three prior review rounds, the existing canonical external-channel requirement, and the reopening diff. The inventory covers all three clarification records; the eight first-spec scenarios; both scope statements; the delta requirement and its six scenarios; four present-state assertions; decisions 1–4; and M1.
- Traced the production delivery seam instead of relying on the former text-footer review: `RunDeliveryContext` holds run-owned final material (`runtime_delivery/context.py:92-118,363-454`), the observer constructs it at successful `turn_end` before mirror delivery (`observer.py:533-561,866-878,1510-1519`), and the coordinator reads the same cached projection in its no-shadow fallback (`session_run_coordinator.py:1639-1697`). `OutboundRouter` copies opaque metadata without changing its final text dedupe (`channels/base.py:113-129`; `outbound_router.py:52-72,180-195`).
- Traced the actual Feishu transports. Ordinary replies use `send_message()` as a `post` and first resolve Markdown images (`channels/feishu/client.py:321-360,412-447`); interactive delivery simply JSON-serializes a supplied card (`:466-480`). Approval cards prove the native `wide_screen_mode` / `markdown` / `hr` transport and an actual UTF-8 card-size boundary, not a reusable normal-reply body projection (`channels/feishu/approval.py:385-426,564-570`; `tests/unit/test_feishu_adapter_permission_approval.py:278-363`).
- Checked the isolated E2E boundary. The fixture enables the feature only in the generated E2E config (`config/e2e/gateway.yaml:12-16`), and the current probe verifies ingress only (`scripts/e2e-feishu-probe.py:83-149`); the design correctly assigns a stronger outbound-card/shadow assertion and native screenshot to this unit (`design.md:131-144`).

### 核实台账

| 类型 | 原子 | 本轮核实与证据 | 结论 |
|---|---|---|---|
| 现状 | typed config can own default/global/platform policy | `DisplayConfig` defaults to false and stores platform overrides (`config/local_store.py:317-326`); the current formatter normalizes a channel to its platform before applying that precedence (`gateway/runtime_footer.py:34-44`). | 成立 |
| 现状 | normal and fallback terminal sends can share a run-owned projection | Observer caches terminal facts/text before its final mirror (`runtime_delivery/observer.py:533-561,1510-1519`); coordinator consumes the cache before router send (`session_run_coordinator.py:1663-1695`). | 成立 |
| 现状 | metadata is a narrow adapter hint and does not alter generic routing | `ReplyContext` and `OutboundMessage` both carry opaque metadata (`channels/base.py:96-129`); router copies it while dedupe keys remain derived from text plus existing reply identity (`outbound_router.py:52-72,180-195`). | 成立 |
| 现状 | Feishu can send one interactive card but its current normal path is a post | `FeishuAdapter.send()` currently calls `send_message()` (`channels/feishu/adapter.py:131-163`); client has a separate `send_interactive_message()` API (`client.py:466-480`). | 成立; body-transport gap is R4-C2 |
| 决策 1 | one projection / two terminal consumers | The proposed observer-owned immutable projection directly matches the actual terminal-event ownership and fallback timing. Keeping plain `cleaned_text` for the shadow also preserves the external-shadow contract. | 成立 |
| 决策 2 | Gateway owns semantics; Feishu is a presentation specialization; future channels get text | A small policy module is the right owner: config/facts are Gateway-owned while router remains generic. The non-Feishu text branch avoids speculative cross-platform card abstractions. | 成立 |
| 决策 3 | final Feishu card has original body plus compact footer, no second post | `reply_phase == "final"` plus a nonempty hint is sufficiently narrow to exclude intermediate/control/approval paths, and the approval client proves interactive send is available. But the design omits the current normal-body preparation and card-size contract. | 不完整，见 R4-C2/R4-C3 |
| 决策 4 | hint does not change dedupe or shadow | Carrying `runtime_footer` only in the final external metadata lets both terminal paths send identical body+hint while the shadow keeps the body. Existing final-text dedupe therefore remains applicable. | 成立 |
| spec | Feishu receives one native card with body and compact runtime information | D1–D4 map the user-visible card to a single normal final send; the E2E/screenshot gate is consumer-facing. It is not yet safe for all existing normal bodies or legal card sizes (R4-C2/R4-C3). | 部分覆盖 |
| spec | future external channels receive the same runtime facts via their supported text presentation | D2 produces platform-neutral compact text for non-Feishu adapters rather than leaking Feishu JSON through the router. | 覆盖 |
| spec | intermediate/tool/approval/control/empty replies and Web IM shadow remain unchanged | The hint is final-only; approval uses a separate adapter entry point; observer shadow writes `cleaned_text`, not the external projection (`design.md:63,77-87`; `observer.py:316-372`). | 覆盖 |
| spec | defaults, both override polarities, and partial facts are preserved | D1/D2 specify default-off, explicit platform precedence, model-only/percent-only/plain outcomes; M1 names the focused tests. | 覆盖 |
| spec | scope/non-goals | The plan does not add telemetry fields, a second footer post, or a future-channel card framework. | 不越界 |
| delta-spec | canonical external-channel behavior is reconciled without contradictory requirements | The active delta declares an ADDED, differently named requirement (`specs/gateway/external-channels.md:3-45`), but the canonical target already has the text-footer requirement being replaced (`docs/specs/gateway/external-channels.md:148-181`). | 不成立，见 R4-C1 |
| milestone | M1 is one vertical card-presentation slice with dual exits | M1 joins Gateway policy, propagation, adapter, tests, real E2E and screenshot. Its exits omit the three mandatory closure targets below. | 不完整，见 R4-C1/R4-C2/R4-C3 |

### 架构进攻

| 角度 | 检查 | 结论 |
|---|---|---|
| 归属 | Tested putting runtime facts/card JSON in IM, router, adapter, and Gateway policy. | Gateway remains the correct owner of facts and enablement; the adapter should own only Feishu serialization. No dependency-boundary issue. |
| 该不该存在 | Applied deletion tests to the projection, metadata hint, and a cross-platform card abstraction. | Deleting the projection recreates observer/fallback drift; deleting the hint forces Feishu policy into the adapter. A renderer registry/protocol for one adapter would be premature. |
| 深/浅 | Compared the proposed `runtime_footer` policy with the existing provider transport surface. | Policy is usefully deep, but D3 currently bypasses the existing post body's image preparation and has no bounded-card body seam. A small shared Feishu body-preparation/card-builder seam is justified by that concrete transport difference (R4-C2/R4-C3), not by hypothetical providers. |
| 治本/补丁 | Tested the card plan against canonical reconciliation, native payload limits, and normal Markdown replies. | One native final card is the right product direction, but leaving the old canonical footer requirement, raw body transport, or unbounded payload in place makes the correction fail at merge time or for ordinary users. These are contract gaps, not implementation polish. |

### Issues

- [R4-C1][CRITICAL] [delta spec: ADDED Requirement] The delta is marked `ADDED` with a new title even though the current canonical target already contains `Requirement: 外部 channel 最终回复的可配置运行信息页脚` and its text-footer scenarios (`docs/specs/gateway/external-channels.md:148-181`). This reopened unit changes that behavior from post-body append to one Feishu card; it must be a `MODIFIED` requirement anchored to that exact existing title, retaining and updating its existing scenarios (and adding only genuinely new scenarios). If left as ADDED, canonical reconciliation preserves both “append beneath the body” and “do not append a post body” contracts, so the next worker/closer cannot produce one coherent current behavior.

- [R4-C2][CRITICAL] [决策 3 / 文件与测试范围 / M1] The card design does not preserve the established normal-reply body transport. Today `send_message()` resolves Markdown image sources/uploaded `img_` keys before creating the post (`channels/feishu/client.py:346-360,412-447`), while `send_interactive_message()` only serializes a raw mapping (`:466-480`). D3 passes “original assistant Markdown” straight into the card without saying which shared client-owned preparation it consumes or testing it. Specify a minimal shared Feishu body-preparation seam used by both post and card paths, and require a card-payload regression with an outbound Markdown image plus ordinary Markdown. Otherwise, enabling the feature can turn a previously rendered normal reply image into a raw/unresolvable source in the card, violating the spec's promise that the card's upper body is the original reply.

- [R4-C3][CRITICAL] [决策 3 / 验收策略 / 风险 / M1] The single-card normal-reply contract has no serialized payload budget or overflow behavior. This repository already treats the interactive-card UTF-8 payload as a `<30_000` byte boundary, including escaped Markdown and emoji (`tests/unit/test_feishu_adapter_permission_approval.py:278-363`; `docs/changes/archive/bugfix-529-feishu-approval-compact-input/M1-fix/progress.md:125-141`), but normal assistant bodies are unbounded and D3 explicitly forbids falling back to a text-footer post after a card error. Require the first spec/design to choose the user-visible overflow behavior compatible with “one card”, then budget the complete JSON at the same `send_interactive_message()` serializer seam and add an oversized-body regression. Without this, a long ordinary answer can have its entire final reply rejected by Feishu instead of receiving the promised one-card result; different workers will otherwise guess between silent truncation, provider failure, and a forbidden second message.

### Recommendations

- [R4-R1] Keep the existing E2E fixture and extend its probe through the verified dedicated user profile's `+chat-messages-list`/message-content read path: bind the nonce to one new bot reply, assert `msg_type=interactive`, the unmodified body and footer in the same card JSON, exactly one final bot message, and the corresponding IM shadow body without the footer. The screenshot remains the separate visual proof of the compact bottom region.
- [R4-R2] Keep the existing final-text dedupe assertion, but make parity assert the complete Feishu delivery tuple `(body, runtime_footer hint, reply_phase)` for observer-first and fallback-only sends; that detects a one-path post/card split before provider I/O.

### Author Resolutions

| Issue | Resolution | Evidence |
|---|---|---|
| R4-C1 | accepted — the active delta now uses `MODIFIED Requirements` and retains the exact existing title `外部 channel 最终回复的可配置运行信息页脚`; its full replacement contract makes Feishu card behavior, other-channel presentation, and single-card overflow coherent with the canonical target. | `specs/gateway/external-channels.md`; `spec.md` overflow scenario; `design.md` file/test scope and M1. |
| R4-C2 | accepted — FeishuClient owns a shared public Markdown body-preparation seam, reused by existing post delivery and the runtime-card adapter path before card construction. | `design.md` 决策 3、文件与测试范围、验收策略。 |
| R4-C3 | accepted — the user-visible overflow behavior is one card with a body-prefix ending `... truncated` and an intact runtime note. The adapter builder must measure the complete serialized UTF-8 card at the existing `<30,000` boundary; no split or text-footer fallback is permitted. | `spec.md` and delta overflow scenarios; `design.md` 决策 3、风险、M1。 |

## Round 5

### Metadata

- reviewer: `/root/feat_523_card_design_review`
- review_mode: `closure`
- mode_reason: `The author changed only the three R4 closure targets: canonical delta reconciliation, the shared Feishu Markdown-body preparation seam, and the one-card serialized payload/overflow contract. Those changes are bounded and do not alter the Gateway projection, final-delivery ownership, config semantics, or future-channel policy established in Round 4.`
- started_at: `2026-08-15T01:37:42+08:00`
- completed_at: `2026-08-15T01:38:05+08:00`
- duration: `23s`

### Verdict

Approved — 0 CRITICAL / 0 WARNING

### 历史问题闭环

| 历史项 | Author Resolution | 本轮核实 | 状态 |
|---|---|---|---|
| R4-C1 | Delta is now `MODIFIED` under the exact canonical requirement title. | The canonical target's existing `外部 channel 最终回复的可配置运行信息页脚` requirement remains at `docs/specs/gateway/external-channels.md:148-181`; the delta now uses `## MODIFIED Requirements`, repeats that exact title, and replaces its post-footer scenarios with Feishu-card, non-Feishu, configuration, non-final, partial-fact, and overflow scenarios (`specs/gateway/external-channels.md:3-54`). No competing added rule remains. | closed |
| R4-C2 | Client owns one shared public Markdown body-preparation seam for post and card. | D3 now makes the seam's ownership, existing image upload/image-key behavior, and both callers explicit (`design.md:76-84`); file/test scope requires `client.py` plus `adapter.py` and a shared ordinary-Markdown/image regression (`:125-137`). This is the narrowest viable extension of today's post-only preparation (`src/personal_assistant/channels/feishu/client.py:346-447`), not a new renderer abstraction. | closed |
| R4-C3 | Overflow is one card with a `... truncated` body prefix and retained footer, budgeted at the complete serializer seam. | First spec and modified delta give the user-visible one-card/no-second-message result (`spec.md:56-61`; `specs/gateway/external-channels.md:47-54`). D3 fixes the complete `json.dumps(card, ensure_ascii=False).encode()` `<30_000` boundary, character-boundary truncation, retained note, and no fallback (`design.md:80-84`); tests, E2E, risks, and M1 all carry that same measurable condition (`:125-163`). | closed |
| R4-R1 | Probe should verify one native reply plus plain shadow; screenshot remains visual proof. | The revised E2E requirement binds a nonce to exactly one `msg_type=interactive` reply and verifies the card/body/footer plus plain shadow (`design.md:137-140`). | adopted |
| R4-R2 | Parity should cover the complete Feishu delivery tuple. | Unit tests now explicitly require observer-first/fallback-only equality of `(body, runtime_footer, reply_phase)` (`design.md:135-137`). | adopted |

### Issues

- None.

### Recommendations

- None. The R4 recommendations are incorporated into the closure evidence above.
