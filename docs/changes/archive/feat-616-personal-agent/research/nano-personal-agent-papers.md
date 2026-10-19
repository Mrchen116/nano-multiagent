# Evidence matrix: persistent personal agents in multi-user IM

Research date: 2026-10-16. Six primary papers, with evidence strength distinguished from architecture recommendations. No product changes. Nano context (provided by parent, not independently inspected): global per-agent inbox/heartbeat/taskgraphs; planned unique personal-agent role per user.

## Bottom line

The closest deployed precedent is Electric Elves, not a generic LLM multi-agent framework. Its successes and failures argue for a persistent owner proxy with explicit authority boundaries. Neither these papers nor the newer proactive benchmark establish that every message visible to a person should wake their agent, notify the person, or receive an autonomous reply.

## Six-paper matrix

### 1. Scerri, Pynadath & Tambe — Towards Adjustable Autonomy for the Real World (JAIR 17, 2002, pp. 171–228)
Primary: https://arxiv.org/pdf/1106.4573 ; DOI https://doi.org/10.1613/jair.1037 . The 2011 arXiv posting is a later archive of the 2002 paper.

- **Mechanism:** Transfer-of-control strategies are conditional sequences of handing decisions to people/agents and modifying coordination constraints to buy time. MDPs optimize decision quality against waiting, coordination disruption, and erroneous-action costs. User-specified safety constraints restrict admissible strategies.
- **Evidence:** Formal model, experiments, and real Electric Elves deployment over six months; thousands of autonomy decisions. This is actual human-agent team coordination, not simulated LLM personas.
- **Limit:** Narrow office activities and explicitly modeled costs/probabilities. It does not establish open-ended LLM permission safety.
- **Nano inference:** Taskgraphs should represent waiting-for-owner, deadlines, and authorized fallback actions explicitly. An unanswered question is a state, not permission. A timeout may trigger re-evaluation or escalation, never automatically broaden authority. Model multi-step interaction costs rather than independently scoring each notification.

### 2. Tambe et al. — Electric Elves: What Went Wrong and Why (2005 author manuscript; AI Magazine version, 2008)
Author manuscript: https://www.cs.cmu.edu/~pscerri/papers/Elves_lessons.pdf . Published version: https://doi.org/10.1609/aimag.v29i2.2123 . Do not call the linked six-page 2005 manuscript the 2008 publication.

- **Mechanism/evidence:** Nearly a dozen persistent proxies each represented a person for seven months. A Friday could reschedule a meeting, tell other Fridays, and those proxies informed their owners. Real failures included unauthorized-feeling cancellations after timeout, almost 50 successive five-minute delays, disclosure of location/presence, and exposure of inferred interpersonal importance. Learned behavior changes confused users; later work allowed inviolable constraints.
- **Limit:** Retrospective deployment lessons, not randomized evaluation. Privacy problems were observed without a complete deployed solution. Later privacy simulations should not be mistaken for deployment safeguards.
- **Nano inference:** Agent-to-agent messaging is plausible, but recipient agent receiving a request must not confer the recipient owner's authority. Suppress redundant cascades. Keep private context and externally shareable conclusions separate. Even a coarse presence signal can leak sensitive intent.

### 3. Horvitz, Jacobs & Hovel — Attention-Sensitive Alerting (UAI, July 1999)
Primary PDF: https://www.erichorvitz.com/priorities.pdf ; author landing page: https://www.erichorvitz.com/attend.htm .

- **Mechanism:** Estimate message criticality as cost of delayed review; combine it with uncertain attention and the expected time until the user independently checks messages. Alert when expected benefit outweighs interruption cost. PRIORITIES integrates email/calendar, ranking and notification policies.
- **Evidence:** Implemented Outlook prototypes tested internally; criticality classifier evaluated using about 1,500 training messages and 500 balanced test messages.
- **Limit:** Classifier evidence is not a controlled demonstration of long-term productivity improvement. Email criticality is narrower than whether an agent should speak in a social conversation.
- **Nano inference:** Receipt and indexing can be immediate without immediate human notification. Compute a separate notify-now/defer decision. If the user is already reading or replying, the incremental value of an agent alert is often lower. A heartbeat is a chance to reconsider deferred items, not a duty to say something.

### 4. Horvitz, Koch & Apacible — BusyBody: Creating and Fielding Personalized Models of the Cost of Interruption (CSCW, November 2004)
Primary PDF: https://www.microsoft.com/en-us/research/wp-content/uploads/2004/11/busybody_cscw.pdf .

- **Mechanism:** Periodic user assessments train personalized Bayesian networks from computer activity, calendar, location, time, and conversation cues. Runtime predicts interruption-cost distributions. Seed/personal models can be combined as personalized evidence grows.
- **Evidence:** Four reported participants over several weeks; random 80/20 train/test splits; classification accuracies 70–87%. Participants found assessment prompts somewhat annoying.
- **Limit:** Small organizational sample, self-reported labels, and random rather than forward-time holdout. Accuracy does not establish optimal interruption outcomes. Unanswered training probes were sometimes labeled busy; that is a dataset convention, not a general meaning of silence.
- **Nano inference:** Start with explicit quiet hours and controls, then learn cautiously from labeled feedback. Measure notification burden, not only prediction accuracy. Do not treat an ignored recommendation as rejection of its underlying task, or acceptance as permission for unrelated future actions.

### 5. Lu et al. — Proactive Agent: Shifting LLM Agents from Reactive Responses to Active Assistance (arXiv, 16 October 2024; inspected v2)
Primary: https://arxiv.org/html/2410.12361v2 ; code: https://github.com/thunlp/ProactiveAgent .

- **Mechanism:** Update memory on incoming events; generate a possible task or stay silent; obtain user-agent/reward-model feedback; accepted tasks execute in a gym. ProactiveBench contains 6,790 training events and 233 test events; training is generated with an LLM-driven environment pipeline.
- **Evidence:** Fine-tuned Qwen2-7B reports 66.47% F1, but only 49.78% precision and 50.22% reported false-alarm ratio. A learned reward model supplies automatic acceptance judgments. Feedback can reduce false alarms while sharply reducing recall.
- **Limit:** Not evidence of a deployed multi-user assistant's utility, consent, or long-term user trust. Extensive user-centric evaluation is future work. The headline F1 conceals over-eager proposals.
- **Nano inference:** Separate candidate generation from outward intervention. Evaluate silence, missed useful opportunities, and false interruptions independently. Test on real message streams and user outcomes; do not use a synthetic user judge as the final authority on appropriateness.

### 6. South et al. — Authenticated Delegation and Authorized AI Agents (arXiv, 16 January 2025)
Primary: https://arxiv.org/html/2501.09674v1 .

- **Mechanism:** Proposes human-ID and Agent-ID credentials plus a delegation token linking the two, with scope, expiry/revocation, and optional audit metadata. Remote services and other agents verify representation and authority. Discusses translating natural-language constraints into service-enforceable controls.
- **Evidence:** Architecture/proposal with illustrative use cases; do not present it as experimentally demonstrated end-to-end secure delegation.
- **Limit:** Authentication establishes identity/delegation, not benign intent or correctness. Natural-language scope interpretation remains a hard problem. Signing a token does not make a model a reliable access-control engine.
- **Nano inference:** Carry principal, actor, authority grant, and conversation context separately. A sender can authenticate as Bob's agent without becoming authorized to act as Alice. Enforce resource/action scopes outside the model, with narrow grants, expiry, revocation and audit. Read, send-as-agent, and commit-on-owner's-behalf are different permissions.

## Proposed Nano architecture: synthesis, not a claim made or tested by one paper

1. **Identity and ownership:** Unique personal role maps to an owner principal; a runtime agent ID is not the owner identity. Preserve actual sender, represented principal, target principal, conversation, and delegation reference in each envelope.
2. **Read delegation:** Determine whether this owner's personal assistant may access this conversation at all. Owner membership is an input, not a universal license to ingest or retain everything. Respect conversation policy, membership revocation, retention constraints, and explicit exclusions.
3. **Observation projection:** For allowed sources, mirror an event or reference into the owner's observation stream without changing human unread/read receipts. Deduplicate by source message ID. A reference projection avoids unnecessary duplicate message stores; check permission again on fetch.
4. **Wake gate:** Separately decide whether this event deserves immediate model work, deferred batch work, or no action. Explicit address, an expected reply, a deadline change, or active-task dependency can justify waking. Rate limits and per-owner budgets constrain external attempts to consume attention/compute.
5. **Notification gate:** Model work may silently update a task or prepare context. Notify the human only when the information is useful now, considering urgency, prior delivery, human engagement, quiet hours, and unresolved decisions.
6. **Response/action gate:** Decide separately whether to answer the sender, draft for the owner, ask the owner, or act under a specific grant. Every external action must pass a deterministic authorization check. Store expiry and revocation with the grant, not just in a prompt.

### Important group-chat distinction

Private assistance using delegated read access and joining a group as an autonomous speaking participant are separate product modes. The papers do not establish a universal legal or social rule that every group member must consent to all private assistance, nor do they establish that one member's read access licenses an undisclosed agent participant. Make the actual group policy explicit: what can be read, whether agent processing is disclosed, whether the agent appears as a participant, and who can invite or remove it. Require the relevant group policy and owner send authority before autonomous participation. Others' text can supply facts or requests; it cannot itself grant the owner's authority.

### Specific defaults worth testing

- Let permitted humans and agents address the personal agent, but treat first-contact messages as requests from their original principal. Do not automatically export owner context in a reply.
- Mirror eligible messages promptly as observations, not as executable commands. Avoid blanket full-LLM wake-on-every-message.
- If an owner-directed message and an agent-directed message both arrive, correlate them rather than producing duplicate tasks.
- Attach an origin/correlation ID, bounded hop count and response budget to agent conversations. Auto-acknowledgments should not awaken reciprocal auto-acknowledgments.
- Provide separate feedback: wrong content, wrong time, already handled, permission denied, and never for this topic/source. Silence is censored/ambiguous feedback.

### Minimum evaluation suite

Replay: bursty group conversation, explicit direct requests, user already replying, changed/cancelled deadlines, revoked membership, spoofed owner instructions, agent-to-agent loops, delayed owner approval, and duplicate delivery. Measure useful-intervention precision, urgent-miss rate, notification latency, interruptions per owner/day, duplicate replies, unauthorized disclosures/actions, loop termination, and wake cost. Run shadow mode first; compare event mirroring with batch wake versus wake-every-event. Report user-controlled policy violations separately from relevance scores. No paper here validates the entire resulting IM architecture; these are evidence-informed hypotheses to test.
