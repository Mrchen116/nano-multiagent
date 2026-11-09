---- MODULE ContextCachePrefix ----
EXTENDS Naturals, Sequences

CONSTANTS Agents, MaxRequests, MaxTools
VARIABLE s

Init ==
    \E agent \in Agents :
        s = [agent |-> agent, stage |-> "idle",
             tools |-> <<agent, "initial-tools">>,
             system |-> <<agent, "initial-system">>,
             history |-> <<>>, protectedHistory |-> <<>>,
             last |-> [tools |-> <<>>, system |-> <<>>],
             allowedHeaders |-> {}, bad |-> {},
             config |-> "initial", pruned |-> FALSE, window |-> 0,
             requests |-> 0, toolCalls |-> 0]

IsPrefix(old, current) ==
    /\ Len(old) <= Len(current)
    /\ \A i \in 1..Len(old) : old[i] = current[i]

UserInput ==
    /\ s.stage = "idle"
    /\ s.requests < MaxRequests
    /\ s' = [s EXCEPT !.stage = "ready",
             !.history = Append(@, <<"user", s.requests + 1>>)]

EmitRequest ==
    /\ s.stage = "ready"
    /\ s.requests < MaxRequests
    /\ s' = [s EXCEPT !.stage = "awaiting-model", !.requests = @ + 1,
             !.last = [tools |-> s.tools, system |-> s.system],
             !.protectedHistory = s.history, !.allowedHeaders = {},
             !.bad = @ \cup (IF s.requests = 0 THEN {} ELSE
                {field \in {"tools", "system"} :
                    field \notin s.allowedHeaders /\ s.last[field] # s[field]}
                \cup (IF IsPrefix(s.protectedHistory, s.history)
                      THEN {} ELSE {"messages"}))]

FinishReply ==
    /\ s.stage = "awaiting-model"
    /\ s' = [s EXCEPT !.stage = "idle",
             !.history = Append(@, <<"assistant", s.requests>>)]

StartTool ==
    /\ s.stage = "awaiting-model"
    /\ s.toolCalls < MaxTools
    /\ s' = [s EXCEPT !.stage = "awaiting-tool", !.toolCalls = @ + 1,
             !.history = Append(@, <<"tool-call", s.toolCalls + 1>>)]

ToolReturn ==
    /\ s.stage = "awaiting-tool"
    /\ s' = [s EXCEPT !.stage = "ready",
             !.history = Append(@, <<"tool-result", s.toolCalls>>)]

RestrictSelection ==
    /\ s.config = "initial"
    /\ s' = [s EXCEPT !.config = "restricted",
             !.tools = <<s.agent, "restricted-tools">>,
             !.allowedHeaders = @ \cup {"tools"}]

BeginIdleConfigApply ==
    /\ s.config = "restricted"
    /\ s.stage = "idle"
    /\ s' = [s EXCEPT !.config = "applying"]

ApplyPersona ==
    /\ s.config = "applying"
    /\ s' = [s EXCEPT !.config = "persona-updated",
             !.system = <<s.agent, "updated-system">>,
             !.allowedHeaders = @ \cup {"system"}]

ApplyTools ==
    /\ s.config = "persona-updated"
    /\ s' = [s EXCEPT !.config = "applied",
             !.tools = <<s.agent, "updated-tools">>,
             !.allowedHeaders = @ \cup {"tools"}]

Prune(i) ==
    /\ s.stage = "ready"
    /\ ~s.pruned
    /\ s.history[i][1] = "tool-result"
    /\ s' = [s EXCEPT !.pruned = TRUE,
             !.history[i][1] = "pruned-result",
             !.protectedHistory = IF i <= Len(@)
                 THEN [@ EXCEPT ![i][1] = "pruned-result"] ELSE @]

PruneToolResult ==
    \E i \in 1..Len(s.history) : Prune(i)

RollWindow ==
    /\ s.stage \in {"idle", "ready"}
    /\ s.requests > 0
    /\ s.window = 0
    /\ s' = [s EXCEPT !.window = 1, !.history = <<<<"window-notice", 1>>>>,
             !.protectedHistory = <<>>]

Next ==
    \/ UserInput
    \/ EmitRequest
    \/ FinishReply
    \/ StartTool
    \/ ToolReturn
    \/ RestrictSelection
    \/ BeginIdleConfigApply
    \/ ApplyPersona
    \/ ApplyTools
    \/ PruneToolResult
    \/ RollWindow

NoSilentPrefixRewrite == s.bad = {}
====
