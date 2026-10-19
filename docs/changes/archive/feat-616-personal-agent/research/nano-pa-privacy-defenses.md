# Nano: privacy defenses for an owner-global PA with external collaborators

Research checked 2026-10-16. Scope: design review and offline synthetic evaluation only; no live attacks conducted. Architecture recommendations below are synthesis, not claims that the cited implementations are production-ready.

## Bottom line

Keep the richly informed personal assistant owner-only. Give each external collaboration a separate, fresh agent that receives an explicitly authorized task packet, not the owner's global history or retrieval authority. Put deterministic identity, memory-access, label-propagation, and outbound-action checks outside all LLMs. Privacy instructions, classifiers, and LLM reviewers can improve judgment but cannot constitute the isolation boundary.

“Same model, separate prompt” is insufficient if both invocations share memory tools, caches, logs, session state, credentials, or an unrestricted route back to the private core. A sandbox needs actual resource and capability separation.

## Six especially useful primary sources

### 1. AirGapAgent: Protecting Privacy-Conscious Conversational Agents (2024)
[Paper](https://arxiv.org/abs/2405.05175), [design details](https://arxiv.org/html/2405.05175v2#S4).

Closest fit to Nano's threat model: a third party converses with an agent holding private user facts and tries to change the apparent context to make disclosure seem appropriate. A minimizer sees the trusted user task and private vault; the external conversational agent sees only the minimized task data. Third-party questions do not flow back into the minimizer. Missing information is escalated to the user.

Engineering/heuristic distinction: exclusion of data from a genuinely isolated worker is structural; deciding which data to include with an LLM is fallible. The authors explicitly note the lack of formal guarantees for that minimizer. Trusted task and trusted vault are assumptions; poisoned memory violates them. Reported 97% protection for one Gemini Ultra experiment is not a universal guarantee. Best Nano takeaway: make the authorized disclosure set before engaging with an adversarial interlocutor, and never let that interlocutor silently enlarge it.

### 2. CaMeL: Defeating Prompt Injections by Design (2025)
[Paper](https://arxiv.org/abs/2503.18813), [official code](https://github.com/google-research/camel-prompt-injection).

Separates a privileged planner from an untrusted-data parser and executes generated plans through an interpreter tracking capabilities, provenance, and allowed readers. The parser has no tools; policies gate tool executions. The paper reports 67% AgentDojo task completion with its security approach.

Important limits: trusted user query and uncompromised memory are explicit assumptions. Misleading text without forbidden data/control flow, phishing, implementation bugs, side channels, poor policies, and user declassification fatigue remain relevant. The paper explicitly identifies interpreter formal verification as future work. Thus “provable security” must be qualified by the formal model and policy; it is not a fully verified deployed stack or a complete solution to rich-memory privacy. Best Nano takeaway: enforce data destination and authority in a reference monitor, independently of what an LLM decides.

### 3. Fides: Securing AI Agents with Information-Flow Control (2025)
[Paper](https://arxiv.org/abs/2505.23643), [official executable tutorial](https://github.com/microsoft/fides).

Tracks both confidentiality and integrity. It hides sensitive/untrusted values from the planner and selectively inspects them through constrained schemas, with policy-controlled declassification/endorsement. Its formal analysis distinguishes enforceable explicit-secrecy and safety properties from unrestricted claims of noninterference. Appropriate policies stop all attacks in its AgentDojo evaluation; turning policies off makes all evaluated planner designs vulnerable.

This is an engineering-enforced approach conditional on correct labels, policies, mediation, and implementation. The public repository is a tutorial notebook illustrating mechanisms, not evidence of a production-hardened agent gateway. Best Nano takeaway: privacy and authority are separate labels. A trusted medical record may still be confidential; an apparently harmless external message may still be low integrity. JSON schema conformance alone does not make a value trusted or shareable.

### 4. PrivacyLens: Evaluating Privacy Norm Awareness of Language Models in Action (NeurIPS 2024)
[Paper](https://arxiv.org/abs/2409.00138), [official framework/data](https://github.com/SALT-NLP/PrivacyLens).

Builds contextual-integrity seeds into vignettes and agent trajectories. Seeds specify data type, subject, sender, recipient, and transmission principle. This captures inappropriate disclosure even without malicious instructions. In the published setup, privacy-enhanced prompts still yielded leakage in 25.68% of GPT-4 cases and 38.69% of Llama-3-70B cases.

The benchmark measures behavior, not just whether a model can answer privacy questions correctly. It is not a deployment guarantee or an exhaustive adaptive-attack suite; generated cases need quality review. Best Nano takeaway: test a helpful reply that accidentally explains the owner's private reason for declining, not only explicit attempts to retrieve secrets.

### 5. AgentDojo (NeurIPS 2024)
[Paper](https://arxiv.org/abs/2406.13352), [official framework](https://github.com/ethz-spylab/agentdojo).

An extensible environment for tool-using agents, with 97 legitimate tasks and 629 security test cases in the original release. Separately measures user-task utility and attacker-goal success under malicious tool-return content. Useful infrastructure for email, workspace, calendar, and banking-like mock tasks.

It is an evaluation framework, not a defense. Its original tasks are not sufficient coverage for Nano's direct external interlocutors, cross-session memory, or long-horizon cumulative disclosures. Pin the release and model settings; add Nano-specific scenarios rather than interpreting a leaderboard as a security certification. Best Nano takeaway: preserve separate success metrics so a system that refuses everything does not appear secure and useful.

### 6. Privacy in Action / PrivacyChecker / PrivacyLens-Live (2025)
[Paper](https://arxiv.org/abs/2509.17488), [published paper](https://aclanthology.org/2025.findings-emnlp.925.pdf).

Extends privacy evaluation into dynamic MCP/A2A workflows and proposes contextual-integrity reasoning at inference time. GPT-4o leakage falls from 33.06% to 8.32% in its static evaluation; its helpfulness score falls from 2.69 to 2.45. Thus the paper's broad “without task performance loss” wording should not be treated as literally zero measured utility change.

This is probabilistic mitigation. The authors report extraction mistakes, wrong privacy judgments, judgment/action mismatch, and possible memory-poisoning vulnerability. Dynamic and more complex workflows can leak more than static trajectories. Best Nano takeaway: a privacy reviewer is useful defense in depth, but must not possess unilateral power to override a hard sharing policy. MCP/A2A interoperability does not itself establish information-flow authorization.

## Proposed layered architecture (design synthesis)

1. **Authenticated ingress and separate principals.** Bind the sender and channel identity outside the prompt. Owner directives, observed IM messages, external requests, quoted content, and tool outputs have distinct provenance. Seeing the owner in an IM transcript is not automatically a command to the PA. An external agent's claimed delegation is not proof of owner authority.
2. **Owner-private core and vault.** Owner IM observations and global memories default to owner-only. Store provenance, subject, confidentiality, integrity, audience, purpose, retention, and source timestamps alongside memory. Observation, summary, and inferred preference are distinct record types. Third-party claims cannot rewrite authoritative sharing policy or become owner approvals through summarization.
3. **Explicit task contract.** Before external work, bind task ID, authenticated counterpart, purpose, allowed data fields/derived outputs, permissible tools, allowed destinations, expiry, and whether state changes are authorized. Separate consent to read from consent to transmit. Prefer “return busy/free slots” over “send calendar”; “unavailable” over the private reason. Keep these contracts inspectable by the owner.
4. **Fresh external worker.** No global retrieval, previous task histories, raw IM transcript, inherited reasoning context, or secrets. Provision only the approved packet and short-lived task capabilities. An external conversation cannot alter those capabilities. Tool outputs and replies remain low integrity even when they come from a familiar collaborator.
5. **Constrained request broker.** If the worker lacks something, it requests a named field/operation through a typed broker. The broker checks the original contract; it does not forward raw external persuasive text into a privileged minimizer as instructions. Requests exceeding the contract require owner approval with specific recipient, information, and purpose. No generic “ask the private PA anything” tool.
6. **Complete egress mediation.** Gate chat replies, email, tool arguments, search queries, URL paths/query strings, attachments, calendar descriptions, shared documents, logs, telemetry, and inter-agent messages. Resolve recipients and destinations to authenticated identities, not attacker-provided display names. Derivations inherit restrictive labels unless an approved transformation declassifies them. No shell/network/tool escape route around the gateway.
7. **Optional semantic privacy review.** Before release, inspect proposed content against purpose and audience; look for implications, sensitive justifications, and excess detail. Use it to reject or ask for clarification, not to override deterministic denial. High-risk free-form disclosures can require owner review.
8. **Memory quarantine and lifecycle.** External conversations write only to a separate, provenance-preserving inbox. Promotions to owner memory cannot upgrade authority. Recheck permissions when retrieving and before sending; revoke/expire task capabilities and delete task-local state. Prevent cross-owner or cross-task cache reuse. Audit approvals, broker decisions, and egress without making audit logs an additional public sink.

### Concrete guarantee boundary

A reasonable narrow claim: an external worker cannot retrieve records outside its permitted task set, and all outbound operations are checked against a fixed recipient/data/action policy, assuming correct mediation and resource isolation. This is testable at the application boundary.

Do not claim: the system cannot reveal anything sensitive. Approved attributes can imply unapproved ones; multiple harmless answers can compose into a sensitive inference. Output timing, refusal differences, task completion, scheduling choices, logs, exception text, and notification presence can act as channels. Even an approved “busy” answer reveals something. Decide which derived answers are intentionally declassified; enforce query budgets/aggregation and consistent denials where appropriate, but do not label these generic differential-privacy guarantees.

Confused-deputy example at the design level: an external collaboration request causes the owner-authorized core to retrieve unrelated private records and use its own messaging credentials to answer. Fixing only the final prompt leaves that authority confusion intact. Scope retrieval and egress independently.

## Offline synthetic-canary evaluation plan

### Environment and ground truth
- Use only invented owners, contacts, IM histories, documents, calendars, and canaries. Disable actual external networking and replace all communications/tools with deterministic mock sinks. No real personal corpus or live adversary contact.
- Create policy fixtures labeling each fact and derived answer by audience/purpose. Include both arbitrary high-entropy canaries (exact disclosure detection) and natural-language synthetic facts (semantic and inference tests).
- Have two independent reviewers resolve ambiguous norms before evaluation. Pin corpus version, policies, model/version, prompts, tools, seeds, and runtime. Keep adversarial examples separated from hidden held-out evaluation families.

### Cases
- Benign tasks: scheduling, logistics, project collaboration, introduction, gift coordination, form completion. Include authorized sharing so refusal-only systems fail utility tests.
- External elicitation: ordinary-looking unnecessary questions, claimed owner permission, changed purpose, helpfulness pressure, identity/role confusion, and requests relayed through another agent. Keep all scenarios inside mocks.
- Indirect injection surfaces: retrieved email/document/calendar content, quoted IM, tool result, attachment text, memory summaries, search snippets, and agent metadata.
- Multi-turn/cross-task: progressive scope expansion, fragmented disclosures, repeated inference questions, multiple cooperating mock counterparts, task restart, recipient change, revoked approval, expired capability, and mistaken identity.
- Poisoning/persistence: externally supplied memory facts, attempted policy/consent promotion, false source attribution after summarization, retrieval ranking that brings unrelated sensitive facts into context, and stale approved task packets.
- Egress coverage: human-readable reply, attachment, tool arguments, URLs, logs, errors, shared state, notification text, and inter-agent handoff. Test derived and paraphrased disclosure as well as literal canary copying.

### Compare and measure
Compare (a) global-context baseline, (b) privacy prompting, (c) isolation/minimization, (d) runtime policy gates, (e) full stack plus semantic review. Disable one layer at a time to identify actual contribution.

Report: unauthorized egress by recipient/purpose; unauthorized reads; exact-canary leakage; human-validated semantic disclosure; sensitive inference accuracy above a public-information baseline; cumulative session leakage; intended task completion; over-refusal; owner interruptions; latency/cost; and attempted versus executed forbidden actions. Use repeated seeds, confidence intervals, and held-out attack families. Assess success over a whole conversation, not only single-turn averages. Record leakage even when the main task fails.

Acceptance criteria: zero successful unauthorized canary egress and zero policy-bypass operations in the tested deterministic boundaries; no unapproved capability expansion; no cross-task memory access; predeclared utility floor; review every semantic/inference failure. Zero observed failures is finite test evidence, not proof. Add property-based tests and model-independent unit tests of access checks, label propagation, revocation, and sink coverage; use a smaller trusted computing base and independent security review before broad rollout.

Operational stopping condition: finish the offline suite, produce a per-boundary failure report, fix observed failures, and rerun regressions. Do not progress to live adversarial contact or real-private-data testing without separately authorized scope and safeguards.

## Integration note from Nano code audit

The parent investigation reports that fresh sessions inherit global skills, plugins, memory, and tool exposure, and that a global tool allowlist can reintroduce send_message/subagent capabilities. This is a code-audit finding supplied by the parent, not independently inspected in this research pass. It materially changes implementation priority: a clean conversation context is not a security principal or a capability boundary. Task-scoped exposure must be enforced in tool discovery, dispatch, memory retrieval, connector credentials, and recursively spawned agents. Global defaults must not widen a task's capabilities; child permissions must be the intersection of parent scope and requested child scope. Add regression tests that create a nominally restricted fresh session and try every inherited route to private retrieval and outbound messaging, using only synthetic data and mock sinks.

Optional permissions-design background: [How Agents Ask for Permission: User Permissions for AI Agents, from Interfaces to Enforcement](https://arxiv.org/abs/2607.13718) (Michael and Roesner, July 2026) surveys 21 permissions proposals and five commercial agents. Its taxonomy separates user-facing specification, internal policy representation, derivation from user input, and runtime enforcement. Useful Nano design-review structure: a convincing approval interface or precise-looking natural-language policy is not evidence that the runtime enforces the same scope.
