# Open-source personal-agent messaging: concrete implementation precedents

Checked 2026-10-16. Source snapshots: OpenClaw d0c81f7ddabefc88bce6be9b72c00f1c40bfee5b; Hermes f57e46207d2adf267c9fec49e9ec6653d0e4aa1e; NanoClaw d61af17b541f52632c6194692a166184839a926f. These are observed main-branch commits, not claims about a released version. Official repository documentation plus selected implementation code; no runtime tests. Three projects chosen because each supplies concrete messaging admission, persistence, and outbound semantics. Letta was not needed to fill out a weaker fourth example.

## Executive finding

These systems do not equate “message arrived” with “human must see a copy” or “agent must reply.” The clearest implementable distinction is:

1. Receive/filter transport event.
2. Record context without waking.
3. Admit a durable pending input.
4. Wake or steer an agent turn.
5. Record its processing outcome.
6. Explicitly publish a human-visible message, separately from internal final text.
7. Track publication acceptance/delivery separately from model completion.

Other people can message an assistant when configured identity and room gates allow it. Other agents can also communicate, but bot admission and local agent-to-agent authorization are different mechanisms. None of the reviewed sources establishes universal immediate mirroring of every third-party/agent message into the owner's personal chat. Their concrete precedents support selective publication and separately inspectable transcripts. That is an evidence-bounded conclusion, not proof that no optional UI or integration offers mirroring.

## 1. OpenClaw: strongest explicit ambient and notification semantics

### Admission, identity, and authority

Groups default to allowlist admission and mention-triggered replies; DM access is separate. Pairing is not group authorization. Session keys separate agent/channel/group or channel identity; topics add a topic suffix. Direct chats use main unless DM scope is configured. Importantly, a common agent workspace/memory is not the same as complete public/private isolation: docs recommend separate agents when those must never mix.

Trigger authority and context visibility are separate: default supplemental quote/history context may include non-allowlisted senders; configurable contextVisibility filters it. Requester tool restrictions are retained through queued/delegated work. Readable context must not implicitly grant authority.
[Group configuration, pinned](https://github.com/openclaw/openclaw/blob/d0c81f7ddabefc88bce6be9b72c00f1c40bfee5b/docs/channels/groups.md)

### Read versus wake versus speak

Ambient room events are supported on Discord, Slack (including private channels and multiperson DMs), and Telegram groups. With mention gating off and unmentionedInbound=room_event, allowed unmentioned messages become quiet events: the model may update state, but final assistant text remains private. A message-tool call is required for visible output. DMs, mentions, control commands, and aborts remain user requests. Typing/lifecycle reactions are suppressed, except an explicitly broad acknowledgment-reaction setting. This is an actual ambient assistant path, beyond a mention-response bot.

Caveat: group docs say mention-gated skipped messages can remain context, while the ambient guide warns mention gating prevents room events/backlog; verify the selected adapter and desired history behavior rather than assuming a universal transport contract.
[Ambient semantics, pinned](https://github.com/openclaw/openclaw/blob/d0c81f7ddabefc88bce6be9b72c00f1c40bfee5b/docs/channels/ambient-room-events.md)

### Local agent messages, no automatic ping-pong

sessions_send addresses a local session, not an external human destination. It supports enqueue-and-return, waiting, steering, separate follow-up turns, and mode=notify (queue context without starting a turn). Timeout of the sender's wait is distinct from receiver execution. Accepted/queued is not consumed/completed. Send-only permissions can grant a target without granting arbitrary history access.

Inter-session provenance explicitly marks isUser=false. Replies return once to the requester, inline or delayed; the requester response is not automatically fed back, and no target announcement turn is generated. Thread targets are denied by default. The docs warn that sending to a privileged target can still induce disclosure/action: send-only access is not isolation.
[Session tools, pinned](https://github.com/openclaw/openclaw/blob/d0c81f7ddabefc88bce6be9b72c00f1c40bfee5b/docs/concepts/session-tool.md)

### External bot loops

Current docs explicitly say Slack/Discord accept bot-authored messages under normal mention/access rules by default; allowBots=false overrides. Bot context and turn admission remain separable. The core guard uses unordered bot identity pairs scoped to account/conversation: default 20 events per 60 seconds, then 60-second cooldown. Slower loops can continue, so this is rate containment, not semantic termination. Internal broadcast groups separately cap four rounds/32 participant turns.
[Bot-loop guard semantics, pinned](https://github.com/openclaw/openclaw/blob/d0c81f7ddabefc88bce6be9b72c00f1c40bfee5b/docs/channels/bot-loop-protection.md)

### Proactivity and user delivery

Heartbeat is a system-owned scheduled automation, normally running main-session agent turns. Execution context and delivery target are independent. Default target is owner DM; last-room delivery is opt-in, and none suppresses external delivery for periodic polling. Event-driven completion turns can occur without recurring cadence. The docs distinguish completion-owned routes from generic heartbeat routes and document rate guards (30-second event spacing; five starts/minute flood guard). A designer should not assume turning off recurring ticks also turns off event wakes.
[Heartbeat, pinned](https://github.com/openclaw/openclaw/blob/d0c81f7ddabefc88bce6be9b72c00f1c40bfee5b/docs/gateway/heartbeat.md)

## 2. Hermes: strong observe-only context, durable Bot Chat delivery, and failure visibility

### Who may contact it

Gateway authorization defaults to deny, with explicit platform/global allowlists, paired users, and optional allow-all flags. Chat DMs default to a pairing-code flow: unknown sender gets an eight-character code for owner CLI approval. Alternatives are ignore or decline; decline sends one refusal then ignores that sender for 24 hours. Email defaults to ignore. Pairing is rate-limited and expiring. This is access to interact with the agent, not a claim that every allowed user should inherit owner authority.
[Security, pinned](https://github.com/NousResearch/hermes-agent/blob/f57e46207d2adf267c9fec49e9ec6653d0e4aa1e/website/docs/user-guide/security.md)

### Read without waking

Telegram observe_unmentioned_group_messages=true, with both allowed_chats and group_allowed_chats configured and require_mention=true, appends unmentioned chatter to shared chat/topic transcripts without dispatching the agent. A later mention/reply uses it. Observed lines have sender identity; the triggered turn adds safety framing that prior chatter is context rather than instructions. Transport visibility is still necessary (Telegram privacy disabled or bot admin). This is an excellent low-cost ambient-read precedent; unlike OpenClaw room events, it does not itself run reasoning for every observed message.
[Telegram observe mode, pinned](https://github.com/NousResearch/hermes-agent/blob/f57e46207d2adf267c9fec49e9ec6653d0e4aa1e/website/docs/user-guide/messaging/telegram.md)

### Session privacy boundary

Default DMs have one session per platform/chat. Groups/channels are per-user when an ID is available, whereas group threads/topics are shared by default (optional per-user threads). Missing participant identity falls back to a shared room session. Therefore “separate sessions” must be evaluated against topology, not advertised as unconditional user isolation.
[Sessions, pinned](https://github.com/NousResearch/hermes-agent/blob/f57e46207d2adf267c9fec49e9ec6653d0e4aa1e/website/docs/user-guide/sessions.md)

### Bot-loop implementation, directly checked

gateway/bot_loop_guard.py defines a per-conversation sliding-window budget, enabled by default: 20 bot messages in 300 seconds, then 600-second cooldown. admit() checks cooldown, expires old timestamps, and trips once the prior admitted count reaches max_events; settings reload on each call. The module explicitly distinguishes ALLOW_BOTS admission from loop containment. This verifies the guard implementation, not coverage of every platform adapter.
[Code, pinned](https://github.com/NousResearch/hermes-agent/blob/f57e46207d2adf267c9fec49e9ec6653d0e4aa1e/gateway/bot_loop_guard.py)

### Proactive delivery and bot recipients

Cron delivery can target local audit output, messaging destinations, or canonical Bot Chat. bot-chat:<profile> targets another same-machine profile; it is not included in all. Bot Chat receives a real incoming message and incurs an agent turn. A live mailbox owner receives a durable enqueue even when busy; cron does not create a competing writer. Receipt states distinguish queued/claimed from completion. Failed delivery is a separate status; ambiguous interrupted sends are not blindly retried.

Successful outputs containing [SILENT] suppress target delivery while remaining auditable; failed jobs cannot use that marker to hide failure. These are unusually useful precedents for separating “processed,” “accepted,” and “human notified.”
[Cron behavior, pinned](https://github.com/NousResearch/hermes-agent/blob/f57e46207d2adf267c9fec49e9ec6653d0e4aa1e/website/docs/user-guide/features/cron.md)

## 3. NanoClaw v2: strongest small-system mailbox and edge-authorization precedent

Do not cite NanoClaw's old SPEC.md as current: it explicitly labels the single-DB/file-IPC/task-scheduler model historical v1.

### Durable mailbox, trigger, and output

Current architecture separates inbound.db (host writes; container reads) from outbound.db (container writes; host reads). messages_in has trigger=0 for accumulated context versus trigger=1 to wake, process_after, status, and source_session_id. messages_out has deliver_after and routing. processing_ack records processing/completed/failed separately; the host's delivered table records outbound delivery. Polling reconciles pending input, stale processing, due output, and recurrence. The adapter controls platform visibility/filtering; platform channel/thread IDs determine shared versus per-thread sessions.

Authority roles are owner/global admin/group admin/member; approval cards go to the chosen approver's DM rather than the originating room. Documentation contains some stale-looking customization prose beside newer destination descriptions, so implementation is the stronger A2A evidence below.
[Architecture, pinned](https://github.com/nanocoai/nanoclaw/blob/d61af17b541f52632c6194692a166184839a926f/docs/architecture.md)

### Other agents can message it, but only across granted edges

a2aSend checks a source-to-target destination grant, target existence, and optional policy hold for a named approver; self-send is allowed. Policy rows can tighten to hold, not bypass missing destination grants. After approval it rechecks live structural authorization, so revocation while a card was pending prevents delivery.
[Guard code, pinned](https://github.com/nanocoai/nanoclaw/blob/d61af17b541f52632c6194692a166184839a926f/src/modules/agent-to-agent/guard.ts)
[Approval replay, pinned](https://github.com/nanocoai/nanoclaw/blob/d61af17b541f52632c6194692a166184839a926f/src/modules/agent-to-agent/message-gate.ts)

routeAgentMessage writes to the target inbox then requests wake. Replies prefer the original source_session_id, then peer affinity, then resolve an agent-shared session. This path does not copy every message to the owner's chat; human visibility happens when the approval gate requires it or via separate publication. No explicit bot-loop budget appears in these inspected A2A files; do not generalize that to an audited project-wide absence.
[Routing code, pinned](https://github.com/nanocoai/nanoclaw/blob/d61af17b541f52632c6194692a166184839a926f/src/modules/agent-to-agent/agent-route.ts)

### Scheduled work

Tasks belong to agent groups and run in dedicated system sessions, separate from normal chat. One-shot and recurrence are explicit. This preserves task execution identity without requiring a continuous visible conversation.
[Scheduled tasks, pinned](https://github.com/nanocoai/nanoclaw/blob/d61af17b541f52632c6194692a166184839a926f/docs/scheduled-tasks.md)

## Design implications for Nano (recommendations, not observed universal standards)

- Make receive/read/enqueue/wake/respond/publish distinct states or permissions.
- Give outside human and agent messages explicit authenticated provenance; never convert them into owner instructions simply because they arrive in the owner's assistant.
- Permit send-only contact edges without granting private memory/history access, and still constrain target actions to delegated authority.
- Preserve original reply destination and session generation. “Most recently active chat” is unsafe as an implicit delivery target.
- Default owner notifications to decisions, failures, urgent events, and useful synthesized results; offer an audit inbox for all received messages rather than forcing every event into the conversational stream.
- Support passive context storage and a distinct reasoning wake. Cost and attention policies belong at different stages.
- Combine message-ID dedupe and delivery receipts with hop/turn/cost/time budgets. Rate guards alone allow slow infinite loops.
- Recheck grants before deferred input admission and held-message release. Treat accepted, model-consumed, completed, and sent as different receipts.
