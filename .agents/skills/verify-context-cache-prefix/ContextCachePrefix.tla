---- MODULE ContextCachePrefix ----
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS Agents, MaxRequests, MaxTools, MaxChanges, AllowImages, Fault
VARIABLE s

Entry(kind, id) == <<kind, id>>
Header(agent) == [system |-> <<agent, "persona">>,
                  tools |-> <<"common", agent, "optional">>,
                  route |-> "primary"]

Init ==
    \E agent \in Agents :
        s = [agent |-> agent, stage |-> "idle",
             header |-> Header(agent), expected |-> Header(agent),
             history |-> <<>>, protected |-> <<>>, bad |-> {},
             config |-> "initial", changes |-> {}, compaction |-> "native",
             pending |-> "", first |-> 0, count |-> 0,
             settled |-> [i \in 1..2 |-> ""],
             requests |-> 0, toolCalls |-> 0]

CanUse(change) == change \notin s.changes /\ Cardinality(s.changes) < MaxChanges
Use(change) == s.changes \cup {change}

IsPrefix(old, current) ==
    /\ Len(old) <= Len(current)
    /\ \A i \in 1..Len(old) : old[i] = current[i]

Corrupt(history) ==
    IF Len(history) = 0 THEN history ELSE [history EXCEPT ![1][2] = 0]

UserInput ==
    /\ s.stage = "idle"
    /\ s.pending # "personal-state"
    /\ s.requests < MaxRequests
    /\ s' = [s EXCEPT !.stage = "ready",
             !.history = Append(@, Entry("user", s.requests + 1))]

\* Image payloads are symbolic. Each request in this scenario fits within
\* the 20 MiB aggregate encoded image budget.
ImageInput ==
    /\ AllowImages
    /\ s.stage = "idle"
    /\ s.pending # "personal-state"
    /\ s.requests < MaxRequests
    /\ s' = [s EXCEPT !.stage = "ready",
             !.history = Append(@, Entry("image", s.requests + 1))]

QueueEvent(kind) ==
    /\ s.requests < MaxRequests
    /\ s.pending = ""
    /\ CanUse(kind)
    /\ s' = [s EXCEPT !.pending = kind, !.changes = Use(kind)]

\* A PA followup waits for the next turn. Other input producers are represented
\* by a pre-step environment batch, admitted after the current tool exchange.
QueueEnvironment == QueueEvent("environment")
QueuePersonalState == s.agent = "PA" /\ QueueEvent("personal-state")

AdmitEvent ==
    /\ s.pending # ""
    /\ s.stage = "idle" \/ (s.stage = "ready" /\ s.pending = "environment")
    /\ s' = [s EXCEPT !.stage = "ready", !.pending = "",
             !.history = Append(IF Fault = "pa-event" /\ s.pending = "personal-state"
                                THEN Corrupt(@) ELSE @,
                                Entry(s.pending, s.requests + 1))]

EmitRequest ==
    /\ s.stage = "ready"
    /\ s.pending # "environment"
    /\ s.requests < MaxRequests
    /\ s' = [s EXCEPT !.stage = "awaiting-model", !.requests = @ + 1,
             !.protected = s.history,
             !.bad = @ \cup {field \in DOMAIN s.header :
                                     s.header[field] # s.expected[field]}
                       \cup (IF IsPrefix(s.protected, s.history)
                             THEN {} ELSE {"messages"})]

FinishReply ==
    /\ s.stage = "awaiting-model"
    /\ s' = [s EXCEPT !.stage = "idle",
             !.history = Append(@, Entry("assistant", s.requests))]

StartBatch(size) ==
    /\ s.stage = "awaiting-model"
    /\ s.toolCalls + size <= MaxTools
    /\ s' = [s EXCEPT !.stage = "awaiting-tools", !.toolCalls = @ + size,
             !.first = s.toolCalls + 1, !.count = size,
             !.history = Append(@, Entry("assistant-calls", <<s.toolCalls + 1, size>>))]

SettleTool(slot, outcome) ==
    /\ s.stage = "awaiting-tools"
    /\ slot \in 1..s.count
    /\ s.settled[slot] = ""
    /\ s' = [s EXCEPT !.settled[slot] = outcome]

\* Completion order and commit order differ. The durable loop commits ready
\* slots in model order and does not emit until the exchange is complete.
FinishBatch ==
    /\ s.stage = "awaiting-tools"
    /\ \A slot \in 1..s.count : s.settled[slot] # ""
    /\ s' = [s EXCEPT !.stage = IF \E slot \in 1..s.count : s.settled[slot] = "aborted"
                                THEN "idle" ELSE "ready",
             !.history = (IF Fault = "parallel" /\ s.count = 2 THEN Corrupt(@) ELSE @)
                 \o [slot \in 1..s.count |-> Entry("tool-result", <<s.first + slot - 1, s.settled[slot]>>)],
             !.first = 0, !.count = 0, !.settled = [i \in 1..2 |-> ""]]

CancelBatch ==
    /\ s.stage = "awaiting-tools"
    /\ \E slot \in 1..s.count : s.settled[slot] = ""
    /\ s' = [s EXCEPT !.settled = [i \in 1..2 |->
                  IF i <= s.count /\ s.settled[i] = "" THEN "aborted" ELSE s.settled[i]]]

ModelError ==
    /\ s.stage = "awaiting-model"
    /\ CanUse("failure")
    /\ s' = [s EXCEPT !.stage = "failed", !.changes = Use("failure")]

Retry ==
    /\ s.stage = "failed"
    /\ s' = [s EXCEPT !.stage = "ready"]

EndFailedTurn ==
    /\ s.stage = "failed"
    /\ s' = [s EXCEPT !.stage = "idle"]

InterruptReply ==
    /\ s.stage = "awaiting-model"
    /\ CanUse("interrupt")
    /\ s' = [s EXCEPT !.stage = "idle", !.changes = Use("interrupt"),
             !.history = Append(@, Entry("interrupted", s.requests))]

Restart ==
    /\ s.stage \in {"idle", "ready", "failed"}
    /\ s.requests > 0
    /\ CanUse("restart")
    /\ s' = [s EXCEPT !.changes = Use("restart"),
             !.header.system = IF Fault = "restart" THEN <<"changed on restart">> ELSE @]

RestrictedTools(agent) == <<"common", agent>>
ConfiguredTools(agent) == <<"common", agent, "added">>
ConfiguredSystem(agent) == <<agent, "configured-persona">>

RestrictSelection ==
    /\ s.config = "initial"
    /\ CanUse("configuration")
    /\ s' = [s EXCEPT !.config = "restricted", !.changes = Use("configuration"),
             !.header.tools = RestrictedTools(s.agent),
             !.expected.tools = RestrictedTools(s.agent)]

BeginIdleConfigApply ==
    /\ s.config = "restricted"
    /\ s.stage = "idle"
    /\ s' = [s EXCEPT !.config = "applying"]

ApplyPersona ==
    /\ s.config = "applying"
    /\ s' = [s EXCEPT !.config = "persona-updated",
             !.header.system = ConfiguredSystem(s.agent),
             !.expected.system = ConfiguredSystem(s.agent)]

ApplyTools ==
    /\ s.config = "persona-updated"
    /\ s' = [s EXCEPT !.config = "applied",
             !.header.tools = IF Fault = "configuration" THEN <<"wrong order">> ELSE ConfiguredTools(s.agent),
             !.expected.tools = ConfiguredTools(s.agent)]

ApplyWorkspacePlugin ==
    /\ s.stage = "idle"
    /\ CanUse("plugin")
    /\ s' = [s EXCEPT !.changes = Use("plugin"),
             !.header.tools = Append(@, "plugin-tool"),
             !.expected.tools = Append(@, "plugin-tool")]

\* A different route changes the cache namespace. It is not a history reset.
ChangeRoute ==
    /\ s.stage \in {"idle", "failed"}
    /\ CanUse("route")
    /\ s' = [s EXCEPT !.changes = Use("route"),
             !.stage = IF s.stage = "failed" THEN "ready" ELSE "idle",
             !.header.route = "secondary", !.expected.route = "secondary",
             !.history = Append(@, Entry("route-notice", s.requests))]

Prune(i) ==
    /\ s.stage = "ready"
    /\ CanUse("prune")
    /\ s.history[i][1] = "tool-result"
    /\ s' = [s EXCEPT !.changes = Use("prune"),
             !.history[i][1] = "pruned-result",
             !.protected = IF i <= Len(@)
                 THEN [@ EXCEPT ![i][1] = "pruned-result"] ELSE @]

\* A committed reset creates its own expected initial history, rather than
\* granting a request-wide exemption. Failed/rejected resets change nothing.
RollWindow ==
    /\ s.stage \in {"idle", "ready", "failed"}
    /\ s.compaction = "native"
    /\ s.requests > 0
    /\ CanUse("roll")
    /\ s' = [s EXCEPT !.changes = Use("roll"),
             !.stage = IF s.stage = "failed" THEN "ready" ELSE @,
             !.history = <<Entry("window-notice", 1)>>,
             !.protected = <<Entry("window-notice", 1)>>]

RestartWithLegacyCompaction ==
    /\ s.stage = "idle"
    /\ CanUse("legacy")
    /\ s' = [s EXCEPT !.changes = Use("legacy"), !.compaction = "legacy"]

WithSummary(history, cut) == <<Entry("summary", cut)>> \o SubSeq(history, cut + 1, Len(history))

CommitSummary(cut) ==
    /\ s.stage \in {"ready", "failed"}
    /\ s.compaction = "legacy"
    /\ CanUse("roll")
    /\ s.protected[cut][1] \in {"assistant", "interrupted"}
    /\ s' = [s EXCEPT !.changes = Use("roll"), !.stage = "ready",
             !.history = WithSummary(@, cut), !.protected = WithSummary(@, cut)]

Next ==
    \/ UserInput \/ ImageInput \/ QueueEnvironment \/ QueuePersonalState \/ AdmitEvent
    \/ EmitRequest \/ FinishReply \/ ModelError \/ Retry \/ EndFailedTurn \/ InterruptReply \/ Restart
    \/ \E size \in 1..2 : StartBatch(size)
    \/ \E slot \in 1..2, outcome \in {"ok", "error"} : SettleTool(slot, outcome)
    \/ FinishBatch \/ CancelBatch
    \/ RestrictSelection \/ BeginIdleConfigApply \/ ApplyPersona \/ ApplyTools
    \/ ApplyWorkspacePlugin \/ ChangeRoute
    \/ \E i \in 1..Len(s.history) : Prune(i)
    \/ RollWindow \/ RestartWithLegacyCompaction
    \/ \E cut \in 1..Len(s.protected) : CommitSummary(cut)

NoSilentPrefixRewrite == s.bad = {}
====
