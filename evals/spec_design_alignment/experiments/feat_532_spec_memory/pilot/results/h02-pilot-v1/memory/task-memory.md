# Provisional cross-fitted task memory

This non-scoring pilot memory is fallible cross-case context, not owner truth.
Use an entry only when it applies to the current repository evidence and task.

## M01 — user_preference

Keep requirements and workflow instructions concise and precise. State each rule once or twice at most; do not repeat it across multiple sections merely for emphasis.

Applicability: When writing specs, skills, acceptance criteria, or process guidance.
Confidence: high
Source refs: source-0068:L9-L14, source-0009:L29-L31

## M02 — user_preference

Analyze the product and code context before asking questions. Resolve obvious or technical-detail choices independently and bring the user a reasoned recommendation instead of delegating the analysis back to them.

Applicability: During requirement clarification and design scoping, unless a genuine product decision remains.
Confidence: high
Source refs: source-0002:L29-L35, source-0008:L17-L19, source-0105:L15-L20

## M03 — design_principle

Reduce process tax and give the implementing agent freedom over execution topology, while retaining isolation, engineering-quality obligations, independent review, verification, and code review.

Applicability: When simplifying development workflows or defining implementation autonomy.
Confidence: high
Source refs: source-0008:L14-L32

## M04 — common_correction

Preserve substantive TDD red-to-green discipline, but remove commit-count rituals and historical comparisons to deleted procedures. Describe only the current required behavior in positive, direct language.

Applicability: When specifying implementation and testing workflows.
Confidence: high
Source refs: source-0012:L15-L28, source-0185:L27-L30

## M05 — product_judgment

A prototype is an implementation-directing product contract, not a mood board. It must first inspect and inherit the existing product UX so the depicted interaction is the intended final experience.

Applicability: For UI/UX design work that produces prototypes or implementation guidance.
Confidence: high
Source refs: source-0004:L18-L22, source-0004:L36-L42

## M06 — product_judgment

Design from the perspective of a polished commercial product: integrate new capability into the existing experience with restraint, avoid demo-like mode selectors or visually dominant controls, and prefer direct editing of sensible defaults.

Applicability: When selecting interaction models and visual hierarchy for user-facing features.
Confidence: high
Source refs: source-0175:L27-L37, source-0182:L9-L15

## M07 — design_principle

Design review must judge whether a solution is architecturally good and near-optimal, not merely factually grounded and complete. Use active, concrete attacks that identify failure scenarios rather than relying only on checklist compliance.

Applicability: When reviewing architecture or technical designs.
Confidence: high
Source refs: source-0010:L14-L22, source-0010:L28-L34

## M08 — common_correction

Preview and runtime behavior representing the same capability must share one source of truth and implementation path; matching outputs produced by independent implementations are insufficient because they will drift.

Applicability: Whenever configuration previews, inspectors, or UI summaries claim to represent runtime behavior.
Confidence: high
Source refs: source-0002:L33-L35

## M09 — design_principle

Long-lived specifications should express consumer-observable behavior, not internal calls, log strings, or implementation structure. Avoid implementation-locking tests that have no durable regression value.

Applicability: When authoring canonical specs and selecting permanent regression tests.
Confidence: high
Source refs: source-0089:L22-L28

## M10 — common_correction

A runtime bug is not fixed until the original user-reported symptom is reproduced through the real product entry point and shown to disappear. Green unit tests alone can validate code in the wrong layer or provider.

Applicability: For runtime and cross-layer bug fixes, especially when lite workflows omit broad review.
Confidence: high
Source refs: source-0062:L25-L28, source-0181:L9-L23, source-0181:L27-L33

## M11 — design_principle

Run the locally reproducible CI-equivalent checks before opening a PR. Treat any remote CI failure as an ordinary defect that must re-enter the fix loop until green.

Applicability: For implementation completion and PR readiness criteria.
Confidence: high
Source refs: source-0009:L21-L27

## M12 — design_principle

Tests should provide real regression protection, not maximize test count. Delete, merge, or rewrite low-value tests; expected errors must be locally asserted, while unexplained warnings or errors should fail the supported test environment rather than be globally filtered.

Applicability: When cleaning test suites or defining test-quality gates.
Confidence: high
Source refs: source-0173:L15-L22, source-0188:L44-L56, source-0188:L64-L74

## M13 — user_preference

For an explicitly development-stage product, do not add speculative legacy fallbacks, mixed-version protocol negotiation, or historical data migration. Prefer one current canonical contract unless existing user data specifically requires protection.

Applicability: Only when the product is confirmed to be in development and backward compatibility has been explicitly declined.
Confidence: high
Source refs: source-0121:L43-L45, source-0184:L37-L39

## M14 — design_principle

Keep reusable kernel capabilities orthogonal to product form and policy. Products own defaults and presentation choices; shared mechanisms belong in the SDK/kernel and should be reused by all current and future consumers.

Applicability: When assigning responsibilities across kernel, SDK, Gateway, CLI, and other product layers.
Confidence: high
Source refs: source-0014:L31-L33, source-0021:L32-L34, source-0196:L26-L28

## M15 — product_judgment

Agent configuration is current product state, not a value frozen when a conversation was created. Successful capability changes should apply to the next new run in existing conversations while preserving visible history and any already-running turn’s configuration.

Applicability: For model, prompt, skill, tool, or other runtime agent-configuration changes.
Confidence: high
Source refs: source-0021:L25-L30, source-0131:L22-L29, source-0131:L33-L43

## M16 — product_judgment

Failures must preserve semantic cause, ownership, and an actionable next step. Distinguish user denial, policy denial, timeout, interruption, and provider failure rather than flattening them into generic errors; degraded operation should identify exactly which capability or permission is missing.

Applicability: When specifying error handling, permission UX, retries, or degraded states.
Confidence: high
Source refs: source-0001:L45-L57, source-0088:L38-L44, source-0155:L34-L44, source-0169:L36-L38

## M17 — product_judgment

Long-running agent work should not fail solely because a wall-clock limit elapsed. Continued liveness or progress signals mean the work remains healthy; distinguish a legitimate long duration from an idle or stuck operation.

Applicability: For run, tool, relay, and session timeout/watchdog semantics.
Confidence: high
Source refs: source-0007:L16-L20, source-0155:L34-L40

## M18 — design_principle

Separate stable wire identity from human-readable presentation identity. Route and persist with an immutable unique ID, display a readable mutable name, and perform explicit conversion at the product boundary instead of adding name-based fallback lookup.

Applicability: For mentions, routing, avatars, pickers, and any entity that can be renamed or share a display name.
Confidence: high
Source refs: source-0144:L24-L29, source-0144:L35-L45

## M19 — product_judgment

Tool-call UI has two naturally timed information sources: parameters are known and should be visible when execution starts, while results appear only after completion. A tool awaiting permission is not running; show execution state only after approval and a denied state after rejection.

Applicability: When specifying tool-call timelines, summaries, expansion panels, and approval cards.
Confidence: high
Source refs: source-0070:L31-L33, source-0121:L35-L41

## M20 — design_principle

System-prompt composition should follow enabled product features and runtime scenarios. Separate mandatory scenario-specific segments from user-toggleable feature segments, persist feature choices, and provide a live read-only preview derived from the same composition logic.

Applicability: For configurable agent capabilities and system-prompt assembly.
Confidence: high
Source refs: source-0051:L45-L50, source-0051:L57-L59, source-0002:L33-L35

## M21 — domain_knowledge

Optional discovery roots or resources that are missing or empty should be skipped without breaking other valid sources or existing sessions; adding a new compatible source should reuse established discovery and invalid-entry semantics.

Applicability: For skills, plugins, configuration roots, and other optional filesystem discovery.
Confidence: high
Source refs: source-0184:L29-L31

## M22 — user_preference

Keep changes tightly scoped: do not make unrelated improvements merely because they seem valuable, and avoid touching shared lower layers when the requirement is product-specific and can be solved within the owning product.

Applicability: When defining unit scope and choosing implementation layers.
Confidence: high
Source refs: source-0004:L18-L18, source-0004:L32-L34, source-0186:L26-L26

## M23 — design_principle

Write reusable workflow guidance against the general root cause, not one repository, one incident, or assumptions about an agent’s instincts. Use direct imperatives and introduce only compatibility changes that are actually necessary.

Applicability: When authoring reusable skills, standards, or cross-project process documents.
Confidence: high
Source refs: source-0009:L33-L35, source-0039:L31-L33, source-0185:L27-L32

## M24 — design_principle

End-to-end coverage should model representative commercial-product user journeys through real public entry points. For agent systems, a tool-using response is more representative than an echo reply, and critical multi-agent/group interactions deserve explicit guarded paths.

Applicability: When selecting critical-path E2E scenarios and acceptance journeys.
Confidence: high
Source refs: source-0124:L39-L44, source-0124:L46-L55
