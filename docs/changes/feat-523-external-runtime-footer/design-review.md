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
