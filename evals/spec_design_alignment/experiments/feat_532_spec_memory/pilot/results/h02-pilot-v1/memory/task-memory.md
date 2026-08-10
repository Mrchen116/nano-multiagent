# Provisional cross-fitted task memory

This non-scoring pilot memory is fallible cross-case context, not owner truth.
Use an entry only when it applies to the current repository evidence and task.

## M01 — user_preference

Preserve the user's clarification answers verbatim. Put any paraphrase or interpretation in a separate `Agent 解读` field so implicit qualifications are not lost downstream.

Applicability: When writing specs, fix documents, clarification logs, or retrospective records from a conversation.
Confidence: high
Source refs: source-0068:L5-L11, source-0068:L27-L32

## M02 — user_preference

State small rules concisely and precisely; do not bury a simple requirement under repeated warnings, examples, or lengthy rationale.

Applicability: When authoring skills, specifications, acceptance rules, and corrective guidance.
Confidence: high
Source refs: source-0068:L9-L15, source-0089:L41-L44, source-0096:L51-L53

## M03 — common_correction

Investigate the actual product and code context before asking clarification questions. Bring the user an analyzed recommendation with real tradeoffs instead of transferring the analysis back to them.

Applicability: Before requirement clarification, especially when product scope or an existing behavior can be established from evidence.
Confidence: high
Source refs: source-0002:L29-L35, source-0008:L17-L19, source-0184:L33-L35

## M04 — design_principle

Define each agent role by its outcome and responsibility first. Procedures and hard rules are supporting scaffolding; when the procedure is incomplete, the role should use its objective as the decision-making north star.

Applicability: When designing agent workflows, role prompts, or operating skills.
Confidence: high
Source refs: source-0047:L12-L18, source-0047:L24-L30, source-0047:L36-L42

## M05 — user_preference

Reduce process tax and let the responsible agent choose whether to work directly, decompose, or delegate. Preserve only risk-justified invariants such as isolated unit worktrees, engineering-quality obligations, and independent reviewer, verifier, and code-review gates.

Applicability: When simplifying an implementation workflow or deciding which process constraints are essential.
Confidence: high
Source refs: source-0008:L5-L18, source-0008:L20-L30, source-0008:L31-L32

## M06 — design_principle

Run all independent quality gates for initial validation, then revalidate after fixes according to the actual delta. Retain unaffected conclusions only with an explicit invalidation analysis; use targeted checks for narrow changes and restore full validation for high-risk changes or uncertain impact.

Applicability: When specifying fix loops, validation ledgers, or PR evidence after review findings.
Confidence: high
Source refs: source-0013:L19-L27, source-0013:L41-L47

## M07 — product_judgment

A UI prototype is an implementation contract for the final user experience, not an inspiration board. It must first ground itself in the existing product's pages, components, hierarchy, and interaction patterns, then show how the increment fits them.

Applicability: For frontend requirements, prototypes, visual references, and their implementation or review criteria.
Confidence: high
Source refs: source-0004:L18-L22, source-0004:L36-L48

## M08 — product_judgment

Aim for restrained, commercial-grade UI rather than demo-grade or overdesigned controls. Keep primary content readable and native interactions intact; expose secondary message actions only when needed and integrate new controls subtly into the existing surface.

Applicability: When designing Web IM or similarly content-centric interaction surfaces.
Confidence: high
Source refs: source-0182:L13-L21, source-0182:L23-L35, source-0184:L8-L13

## M09 — design_principle

Design documents serve two audiences: humans must be able to review the architecture quickly, while implementation agents need unambiguous interfaces, fields, flows, and exit conditions. Use layered detail and diagrams chosen for the requirement's actual structural, sequence, state, data, or branching difficulty.

Applicability: When structuring design.md or deciding which visualizations belong in a technical design.
Confidence: high
Source refs: source-0096:L45-L49, source-0096:L65-L78

## M10 — design_principle

Design review must actively attack architectural choices for quality and optimality, not merely verify factual correctness, completeness, and checklist compliance. Examine ownership, dependency direction, module depth, unnecessary seams, duplicated mechanisms, and symptom-masking patches, and record the analysis even when approved.

Applicability: For architecture review, design review, and approval criteria.
Confidence: high
Source refs: source-0010:L12-L22, source-0010:L28-L38

## M11 — design_principle

Surfaces that promise the same semantics should share one implementation owner or source of truth. Do not maintain parallel runtime, preview, or product-specific implementations that can drift; add a regression check comparing their observable outputs.

Applicability: When the same configuration, resolution, rendering, or behavior appears in multiple product paths.
Confidence: high
Source refs: source-0002:L33-L35, source-0002:L70-L85, source-0196:L20-L28

## M12 — common_correction

For a bugfix, trace the feature's originating change and record its original intent and invariants before choosing a repair. Removing the failing path may erase the symptom while silently crippling the intended capability.

Applicability: During bugfix RCA, fix-spec authoring, and design constraints for existing features.
Confidence: high
Source refs: source-0179:L9-L17, source-0179:L19-L35

## M13 — common_correction

Passing unit tests is not proof that the user's problem is solved. Reproduce the original symptom through the real browser, CLI, endpoint, or other product entry after the change; for visual work, compare the running product with the supplied reference.

Applicability: For runtime bugfix completion, frontend work, and live-critical acceptance.
Confidence: high
Source refs: source-0181:L13-L23, source-0181:L27-L41, source-0099:L28-L41

## M14 — design_principle

Keep long-lived specifications at the consumer-observable contract level. Internal calls, logging strings, and implementation topology belong in design or code evidence, not in the durable behavioral contract or tests that merely lock an implementation.

Applicability: When writing canonical specs, acceptance criteria, or long-lived regression tests.
Confidence: high
Source refs: source-0089:L22-L28, source-0089:L30-L44

## M15 — design_principle

Close each completed change by updating the maintained, long-lived spec and architecture documents. Define what those documents contain before backfilling them; otherwise stale or poorly structured documents will continue to rot.

Applicability: When designing SDD document lifecycle, archival, or unit completion requirements.
Confidence: high
Source refs: source-0067:L14-L28, source-0067:L30-L40

## M16 — common_correction

Retrospectives should reconstruct evidence and timelines, then follow the actual clues to the current failure's root causes. Prior incidents are examples, not a fixed checklist that every future retrospective must mechanically apply.

Applicability: For incident analysis, workflow retrospectives, and improvement proposals.
Confidence: high
Source refs: source-0042:L15-L20, source-0042:L32-L40

## M17 — user_preference

Prefer clear written norms that agents are guaranteed to read before adding mechanical enforcement. Add contract checks only for rules that remain repeatedly violated; first identify the concrete production defects the guidance must prevent.

Applicability: When introducing testing, coding, documentation, or workflow governance.
Confidence: high
Source refs: source-0046:L13-L25, source-0046:L27-L29

## M18 — user_preference

Do not add speculative legacy fallbacks, mixed-version protocol negotiation, or backward-compatibility state unless a real supported compatibility requirement exists. Prefer one current canonical contract and fail clearly when required current configuration is absent.

Applicability: When evolving schemas, configuration formats, internal protocols, or discovery behavior.
Confidence: high
Source refs: source-0184:L37-L39, source-0195:L45-L50

## M19 — user_preference

Keep changes tightly scoped to the diagnosed requirement. Avoid unrelated refactors, repository-specific overfitting of reusable skills, and extra tracking machinery whose complexity does not advance the requested outcome.

Applicability: When defining unit boundaries, adapting reusable skills, or reviewing proposed implementation scope.
Confidence: high
Source refs: source-0004:L18-L18, source-0004:L32-L34, source-0039:L31-L37

## M20 — user_preference

Once requirements and design are clear, the implementation and validation loop should close autonomously without routine human intervention. Missing live evidence should cause environmental repair or a return to the worker, not a downgraded completion claim.

Applicability: When specifying orchestrator behavior for implementation, environment failures, and live-critical work.
Confidence: high
Source refs: source-0185:L22-L34, source-0185:L40-L45

## M21 — design_principle

When learning from a reference implementation, inspect the authoritative original rather than relying on a secondary summary. Any simplification of researched behavior is legitimate only when explicitly identified and justified in the design.

Applicability: When adapting behavior from another product, repository, study, or reference implementation.
Confidence: high
Source refs: source-0170:L414-L416

## M22 — domain_knowledge

Long-running agent work should not be constrained by a short absolute wall-clock deadline. Detect a stuck run using inactivity—resetting the deadline whenever relevant events arrive—so productive tasks may continue for hours.

Applicability: When specifying streaming run lifecycle, CLI waiting behavior, or watchdog timeouts.
Confidence: high
Source refs: source-0007:L16-L27

## M23 — domain_knowledge

User steering during an active run should enter at the next model-round boundary without interrupting tools already executing. Multiple messages should be injected FIFO without loss, and the mechanism should be a shared core capability rather than separate product implementations.

Applicability: When specifying active-run steering for multiple clients or product entry points.
Confidence: high
Source refs: source-0196:L15-L28

## M24 — design_principle

Maintain a small catalog of critical end-to-end user journeys and guard them through real product interfaces and process boundaries. Favor representative journeys that exercise the dominant seams, and keep expensive true-LLM suites explicitly runnable even when they are not part of every CI run.

Applicability: When defining end-to-end test strategy and deciding which product paths require black-box coverage.
Confidence: high
Source refs: source-0124:L18-L34, source-0124:L38-L52
