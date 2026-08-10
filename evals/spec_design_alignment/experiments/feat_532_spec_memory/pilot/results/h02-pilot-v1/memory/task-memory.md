# Provisional cross-fitted task memory

This non-scoring pilot memory is fallible cross-case context, not owner truth.
Use an entry only when it applies to the current repository evidence and task.

## M01 — user_preference

Analyze the code, product surfaces, and real risks before asking clarification questions. Do not hand obvious or technically decidable analysis back to the user; present a reasoned recommendation and reserve questions for genuine product choices.

Applicability: When drafting clarifications, resolving scope, or choosing among technically constrained options.
Confidence: high
Source refs: source-0002:L30-L35, source-0008:L18-L19, source-0105:L16-L21

## M02 — user_preference

Keep each change tightly scoped to the directly affected behavior and ownership boundary. Do not opportunistically refactor adjacent systems, especially when the requirement belongs to one product rather than the shared SDK.

Applicability: When defining in-scope modules, consumers, and non-goals.
Confidence: high
Source refs: source-0004:L32-L34, source-0110:L39-L41, source-0186:L25-L27

## M03 — design_principle

Specs and long-lived contracts should describe consumer-observable behavior, not internal function calls, log strings, or implementation structure. Tests that merely lock mock calls or no-op internals have weak long-term value.

Applicability: When writing requirements, acceptance criteria, evergreen contracts, or selecting regression tests.
Confidence: high
Source refs: source-0089:L22-L28, source-0112:L19-L21

## M04 — product_judgment

A design document must be a self-contained design for the requested behavior, readable enough for human review and unambiguous enough to guide implementation. Choose diagrams according to the requirement's actual difficulty without asking the user to select diagram types.

Applicability: When defining design deliverables or reviewing design-document completeness.
Confidence: high
Source refs: source-0096:L25-L38, source-0096:L45-L49

## M05 — product_judgment

A product prototype is an implementation contract, not a moodboard. Design should inspect the current UX, preserve the relevant entry points and inherited interaction traits, and record conclusions rather than an evidence-gathering transcript.

Applicability: When a UI change includes a prototype or must integrate with an existing experience.
Confidence: high
Source refs: source-0004:L36-L42

## M06 — design_principle

Equivalent preview, runtime, and multi-consumer behavior should come from one underlying resolver or capability rather than independent implementations. Shared mechanics belong at the reusable kernel/SDK boundary; product surfaces should be validating consumers.

Applicability: When the same behavior appears in preview/runtime, IM/CLI, or future product integrations.
Confidence: high
Source refs: source-0002:L33-L35, source-0196:L20-L28

## M07 — design_principle

Keep the SDK product-neutral: expose stable capabilities and data contracts, while product-specific composition and presentation semantics stay in the owning product layer. New products should compose the kernel without adding product branches inside the SDK.

Applicability: When deciding whether behavior belongs in core, SDK, Gateway, CLI, or another product adapter.
Confidence: high
Source refs: source-0110:L30-L35, source-0110:L42-L44

## M08 — common_correction

For a pure refactor, preserve user and operator workflows, visible results, and failure/recovery behavior, while allowing internal fields, protocols, persistence shapes, and module boundaries to change. Do not smuggle unrelated new features into an invariance change.

Applicability: When specifying or reviewing refactors and migrations.
Confidence: high
Source refs: source-0112:L14-L21, source-0112:L22-L27, source-0195:L15-L20

## M09 — user_preference

Reduce process tax and role ceremony without deleting engineering safeguards. Implementation organization may be autonomous, but isolation, architecture and coding quality, tests, real-entry verification, root-cause repair, independent review perspectives, and complete delivery remain required.

Applicability: When simplifying agent workflows or deciding which process constraints are essential.
Confidence: high
Source refs: source-0008:L14-L35, source-0012:L15-L17

## M10 — user_preference

Write workflow instructions compactly and positively: state the current rule directly, use imperative language, avoid explaining deleted historical rules, and do not repeat one constraint across multiple sections unless necessary.

Applicability: When authoring skills, agent instructions, runbooks, or process documentation.
Confidence: high
Source refs: source-0009:L29-L35, source-0012:L23-L29, source-0185:L26-L30

## M11 — design_principle

Architecture review must actively judge whether a design is good and near-optimal, not merely factual and complete. Use multiple concrete attack angles and require a plausible failure scenario for each candidate issue; avoid unnecessary shadow-solution rituals.

Applicability: When reviewing architecture or designing review skills and checklists.
Confidence: high
Source refs: source-0010:L20-L34

## M12 — common_correction

Bug fixes must trace the original design intent and verify the user's original symptom through a real product entry. A red-to-green unit test supplements this evidence but cannot prove that a cross-layer runtime problem was fixed at the correct seam.

Applicability: When diagnosing regressions, writing fix acceptance criteria, or validating backend/runtime repairs.
Confidence: high
Source refs: source-0181:L25-L41, source-0181:L45-L49

## M13 — user_preference

Avoid speculative backward-compatibility machinery in development-stage or coordinated upgrades. Distinguish redundant mixed-version protocol fallbacks from preservation of real stored user choices or state; the latter may still require an explicit migration/read semantic.

Applicability: When considering aliases, schema negotiation, legacy fallbacks, or migration behavior.
Confidence: high
Source refs: source-0121:L44-L45, source-0184:L37-L39, source-0195:L45-L50

## M14 — product_judgment

Newly discovered or installed capabilities must not silently expand an existing user's explicit saved selection. Defaults may apply to new or still-default configurations, while explicit enable/disable choices remain authoritative across upgrades.

Applicability: When adding built-ins, skills, providers, tools, or other configurable capabilities.
Confidence: high
Source refs: source-0006:L18-L26, source-0184:L25-L27

## M15 — design_principle

Fail loudly on invalid explicit configuration or provider failure instead of silently falling back to a different choice. Errors should name the missing configuration, unreachable provider, invalid model, or exact required fields so users or models can correct the problem.

Applicability: When specifying configuration validation, provider selection, tool schemas, and fallback behavior.
Confidence: high
Source refs: source-0178:L21-L30, source-0189:L35-L41, source-0195:L41-L50

## M16 — product_judgment

User-facing failures should be semantic, actionable, and attributable. Preserve useful upstream details, clearly mark failure state and responsible agent, distinguish user denial from automatic policy denial, and retain the user's unfinished request for later recovery without injecting synthetic failure text into model history.

Applicability: When designing model/tool error handling, denial feedback, and recovery semantics.
Confidence: high
Source refs: source-0001:L23-L37, source-0088:L26-L48

## M17 — product_judgment

Permission UI must show the requested tool and complete input before the user decides. Pending approval is not execution: show running only after allow, show denied without pretending the tool ran, and preserve each decision rather than overwriting approval history.

Applicability: When specifying approval cards, tool timelines, or execution-state presentation.
Confidence: high
Source refs: source-0121:L31-L45

## M18 — design_principle

Lifecycle cleanup belongs at the ownership boundary: when a parent service exits, its owned listeners or workers should exit with it. Do not make next-start orphan scanning or inactivity heuristics the primary correctness mechanism.

Applicability: When defining subprocess, listener, channel, worker, or resource ownership and shutdown behavior.
Confidence: high
Source refs: source-0101:L18-L28

## M19 — design_principle

Critical end-to-end tests should exercise real user journeys through public product interfaces and the real process stack, with robust observable assertions. Prioritize the common agent path that includes a genuine tool call, plus cross-layer journeys such as approvals, restart continuity, and group-directed interaction.

Applicability: When defining commercial-grade smoke tests, critical-path catalogs, or e2e acceptance.
Confidence: high
Source refs: source-0124:L38-L56

## M20 — product_judgment

For IM interaction design, optimize from a commercial product baseline: content reading and native interaction come first, secondary actions appear on demand, and the solution should converge to a coherent final design without becoming a feature grab bag or an overdesigned visual treatment.

Applicability: When specifying or reviewing message, chat, and general end-user interaction UX.
Confidence: high
Source refs: source-0182:L17-L21, source-0190:L25-L29

## M21 — domain_knowledge

Running-session steering is a round-boundary operation, distinct from abort: finish the active tool batch, inject all newly received messages before the next model call, preserve FIFO order, and use the same reusable mechanism across consumers.

Applicability: When specifying concurrent user input during an active agent run.
Confidence: high
Source refs: source-0196:L17-L28

## M22 — product_judgment

Derived model context should not mutate user-authored message content or pollute display, copy, and search. Preserve per-message source facts, use reliable source timestamps with a documented receive-time fallback, and do not fabricate metadata for historical records lacking evidence.

Applicability: When adding timestamps, channel provenance, routing context, or other model-only envelopes.
Confidence: high
Source refs: source-0186:L28-L47

## M23 — user_preference

Prefer the installed product version and observable local state as the default documentation authority. Consult remote material only when the user explicitly asks about the latest version or changes, and clearly identify version differences.

Applicability: When building product-manual or documentation-answering capabilities.
Confidence: high
Source refs: source-0006:L15-L17

## M24 — design_principle

Operational logs should contain the identifiers and measurements needed for diagnosis, such as model, agent, session, token counts, and rates, but not prompt bodies or user content.

Applicability: When specifying diagnostics, alerts, telemetry, or cache/performance logging.
Confidence: high
Source refs: source-0176:L25-L28
