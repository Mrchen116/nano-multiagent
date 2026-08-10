# H02 private rubric — PA unified tool approval model

Keep this directory and every historical owner answer out of candidate exports. The held-out unit, implementation and tests prove that the decision surface is real; they are not a requirement to copy field names, helper modules, state keys, class names, prose or test topology.

## 1. Decision handling and fixed owner replay

D01-D06 are six resolved historical value decisions. Before a confirmatory run, the runtime owner-answer policy must be created in `historical_owner_record` mode, bind the frozen inventory hash and cover exactly D01-D06. It may replay an answer only when that arm actually raises the semantically equivalent decision after the no-answer refinement window.

Reward semantic consolidation. An arm may ask one compact batch or combine dependent questions, but it must expose all six forks clearly enough that the mapper can identify them. Do not require the historical question wording or order. Repeated synonymous questions count as user burden; an arm does not receive an answer to a decision it never raises.

The six frozen semantic answers are:

- configured scope is PA; the kernel remains product-neutral and supports explicit selection or reuse of the current run model;
- omission preserves the existing per-run or per-Agent classifier model;
- an explicit unregistered model rejects startup rather than degrading silently;
- the dedicated model is used only by both automatic classifier stages, not normal or post-tool Agent turns;
- runtime failure never changes classifier model, although existing retry of that same model remains allowed;
- file changes take effect after Gateway restart, not through a new hot-reload path.

D07-D12 are cutoff facts or non-negotiable correctness properties and should be derived without asking the owner. A candidate-created need to widen product scope, cross an architecture redline, expose a new remote control surface or weaken fail-closed permission behavior becomes a new H and pauses only its dependent branch.

## 2. User burden and personalization

- The one-line brief is intentionally under-specified. Asking where “all” stops, what omission means, what failure does and when configuration activates is useful burden.
- Do not reward questions whose answers are directly retrievable from cutoff code, such as where the classifier calls the model, which run origins exist or whether the SDK already accepts an explicit hook model.
- A+USER/B profile evidence must exclude feat-510, PR 248, the exact configuration field, provider-routing correction, run-origin correction, deterministic sequences and canonical descendants.
- Personalization can reward independently supported preferences such as preserving omission behavior or avoiding hypothetical abstractions, but it cannot pre-answer D01-D06 before the arm raises them.

## 3. Spec oracle

A strong final spec makes these behaviors testable without forcing the historical spelling:

- PA can optionally choose one registered model for automatic tool-permission classification across every Agent in the Gateway.
- The choice covers all PA run origins that reach the canonical classifier, including interactive user runs, heartbeat, cron and Agent-derived background work.
- Only classification changes model. A run using model A still uses A before the tool call and after the tool result; a different Agent using B retains B.
- Omitting the choice preserves the cutoff behavior and allows the Gateway to start normally.
- An explicit empty or unregistered choice is rejected before the Gateway serves useful work, with an actionable configuration error.
- Timeout, upstream failure or unparseable classifier output never retries classification with the Agent or another model. Existing attended approval and unattended fallback semantics remain the failure outcome.
- Modifying the file does not alter a running process; a restart validates and activates the new choice.
- Coding CLI behavior, permission rules, classifier prompts, approval UI/cards, per-Agent overrides and a new hot-reload system remain out of scope unless separately justified.

The historical field name `llm.tool_approval_model` can receive full credit, but another PA-owned name or shape can also pass if its catalog ownership, omission, save/reload and error semantics are equally clear. Missing PA-only scope, omission compatibility, classifier-only routing, startup rejection, no-cross-model-fallback or restart lifecycle is major or critical according to the resulting silent-misconfiguration risk.

## 4. Design oracle

Judge the end-to-end ownership and proof, not historical-symbol similarity:

1. The design traces the cutoff path from PA config parsing and persistence through Gateway composition and `agent.sdk.build_kernel` into the canonical automatic classifier, then through `HookModelCall.model` to runtime provider selection.
2. PA owns the configured choice; the SDK surface remains product-neutral. The design obeys `personal_assistant -> agent.sdk`, `platform -> core` and `sdk -> core + platform`, without making IM depend on agent or restoring an HTTP kernel.
3. The selection is build-scoped and has one authority per kernel. Registry extension state, a trusted built-in dependency bundle or an equivalent narrow seam can pass. Session metadata, per-Agent duplication, module-global mutable state and simultaneous bridge/bundle protocols do not.
4. Both classifier stages receive the same optional explicit model. `None` continues to resolve through the run model; a non-`None` choice uses the existing catalog/provider routing. Ordinary run submission and post-tool continuation remain unchanged.
5. Validation occurs early enough to guarantee startup rejection. A public SDK option should defend its own catalog invariant or explain an equally strong consumer-neutral contract; PA should produce a field-level error and preserve the field across config save/reload.
6. Provider retry may repeat the same selected model. Classifier error handling must not initiate a second request with the Agent/default model and must retain existing ask/unattended behavior.
7. All PA origins converge on the same kernel dependency. Do not reward four copied origin branches; do require the real `background_task` origin rather than invented terminology.
8. Delta-specs cover the PA/Gateway contract, the public SDK construction seam and kernel run classification semantics. A single vertical milestone is sufficient when it closes config, SDK, classifier, operations and deterministic tests together.

Equivalent designs receive full credit when they preserve those properties with a smaller coherent mechanism. The historical extension-state helper is one implementation for the cutoff, not the answer key. Penalize a design that copies `tool_approval_model.py` or a state key but cannot explain ownership, provider routing, lifecycle and normal-run isolation.

## 5. Deterministic downstream probes

The hidden implementation-oriented probe set should include:

- two Agents whose normal models are A and B with an explicit classifier model C: complete request sequences are A -> C -> A and B -> C -> B;
- omission: A -> A -> A and B -> B -> B;
- stage 1 and stage 2 both use C, including a stage-1 escalation into stage 2;
- user, heartbeat, cron and `background_task` origins all select C without per-origin wiring;
- A and C registered under distinct providers reach distinct recording clients;
- empty and unregistered selections fail construction/startup and identify the offending field/value;
- C timeout, upstream error and unparseable output produce the existing permission-failure path with no A/B classifier request;
- config parse/save/reload retains an explicit value and preserves omission;
- changing C to D on disk leaves the running process on C and uses D after restart;
- Coding CLI or another consumer that omits the SDK option keeps its previous behavior;
- import and source scans preserve package boundaries and one production classifier consumer.

Request bodies, recording clients or an equivalent deterministic provider boundary are valid evidence. Generated model wording is not. A test using one override client for every provider cannot prove cross-provider routing. No real external channel, browser, Claude Code snapshot or production account is required for this case.

## 6. Evidence and verdict

The candidate world contains the complete cutoff repository, so architecture and current behavior claims should cite or trace cutoff code rather than held-out names. The private judge may use the archived target, final implementation, verification warnings and acceptance sequences as counterexamples and downstream probes while allowing equivalent solutions.

After deterministic snapshot/path/leak checks and blind semantic review, report decision handling, user burden, personalization, spec, design, downstream conversion and cost separately as `win`, `tie`, `loss` or `insufficient evidence`. This is a C1 historical-posthoc regression case, not a clean holdout, and must not be averaged as one.
