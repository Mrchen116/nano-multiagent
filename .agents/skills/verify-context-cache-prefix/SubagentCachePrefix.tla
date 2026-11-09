---- MODULE SubagentCachePrefix ----
EXTENDS Naturals, Sequences

CONSTANTS Agents, Depth, Scenario, MaxRequests, MaxTools, MaxChanges
VARIABLE s

Base == INSTANCE ContextCachePrefix WITH AllowImages <- FALSE, Fault <- "none"

ChildHeader(owner) ==
    [system |-> (IF Depth = 1 THEN <<owner, "owner-name", "shared-feature">>
                 ELSE <<"native-nested-guidance">>) \o <<"context-guidance">>,
     tools |-> <<"native-worker-tools", IF Depth = 1 THEN "level-one" ELSE "level-two", "context-tools">>,
     route |-> "primary"]

Init ==
    \E owner \in Agents :
        s = [Base!InitialState(owner) EXCEPT !.compaction = IF Scenario = "summary" THEN "legacy" ELSE @,
                                             !.header = ChildHeader(owner),
                                             !.expected = ChildHeader(owner)]

ChildInput ==
    /\ s.requests < MaxRequests
    /\ s.stage = "idle"
    /\ s' = [s EXCEPT !.stage = "ready", !.config = "initial",
             !.history = @
                 \o (IF s.config \in {"new-skill-catalog", "new-workspace-context"}
                     THEN <<Base!Entry(s.config, s.requests + 1)>> ELSE <<>>)
                 \o <<Base!Entry(IF s.requests = 0 THEN "assignment" ELSE "parent-message", s.requests + 1)>>
                 \o (IF s.config = "route-notice"
                     THEN <<Base!Entry("route-notice", s.requests + 1)>> ELSE <<>>)]

\* The previous request, not the root's policy, supplies the comparison baseline.
EmitChildRequest ==
    /\ s.stage = "ready"
    /\ s.pending # "environment"
    /\ s.requests < MaxRequests
    /\ s' = [s EXCEPT !.stage = "awaiting-model", !.requests = @ + 1,
             !.expected = s.header, !.protected = s.history,
             !.bad = IF s.requests = 0 THEN {} ELSE
                        {field \in DOMAIN s.header : s.header[field] # s.expected[field]}
                        \cup (IF Base!IsPrefix(s.protected, s.history) THEN {} ELSE {"messages"})]

BetweenTurns(event) ==
    /\ Scenario = event
    /\ s.stage = "idle"
    /\ s.requests > 0
    /\ Base!CanUse(event)

ApplyRootChoices ==
    /\ BetweenTurns("root-choices")
    /\ s' = [s EXCEPT !.changes = Base!Use("root-choices")]

RenameOwner ==
    /\ BetweenTurns("rename")
    /\ s' = [s EXCEPT !.changes = Base!Use("rename"),
             !.header.system = IF Depth = 1 THEN [@ EXCEPT ![2] = "renamed-owner"] ELSE @,
             !.expected.system = IF Depth = 1 THEN [@ EXCEPT ![2] = "renamed-owner"] ELSE @]

DisableSharedFeature ==
    /\ Scenario = "feature"
    /\ s.stage \in {"idle", "awaiting-tools", "ready"}
    /\ s.requests > 0
    /\ Base!CanUse("feature")
    /\ s' = [s EXCEPT !.changes = Base!Use("feature"),
             !.header.system = SelectSeq(@, LAMBDA part : part # "shared-feature"),
             !.expected.system = SelectSeq(@, LAMBDA part : part # "shared-feature")]

RefreshSkillCatalog ==
    /\ BetweenTurns("skill")
    /\ s' = [s EXCEPT !.changes = Base!Use("skill"), !.config = "new-skill-catalog"]

RefreshWorkspaceInstructions ==
    /\ BetweenTurns("workspace")
    /\ s' = [s EXCEPT !.changes = Base!Use("workspace"), !.config = "new-workspace-context"]

DisableContextPlugin ==
    /\ BetweenTurns("context-plugin")
    /\ s' = [s EXCEPT !.changes = Base!Use("context-plugin"), !.compaction = "legacy",
             !.header.system = SelectSeq(@, LAMBDA part : part # "context-guidance"),
             !.header.tools = SelectSeq(@, LAMBDA part : part # "context-tools"),
             !.expected.system = SelectSeq(@, LAMBDA part : part # "context-guidance"),
             !.expected.tools = SelectSeq(@, LAMBDA part : part # "context-tools")]

SwitchParentModel ==
    /\ BetweenTurns("route")
    /\ s' = [s EXCEPT !.changes = Base!Use("route"), !.header.route = "secondary",
             !.config = "route-notice"]

RollChildWindow ==
    /\ Scenario = "rollover"
    /\ s.compaction = "native"
    /\ s.stage \in {"idle", "ready", "failed"}
    /\ s.requests > 0
    /\ Base!CanUse("rollover")
    /\ s' = [s EXCEPT !.changes = Base!Use("rollover"),
             !.stage = IF s.stage = "failed" THEN "ready" ELSE @,
             !.history = <<Base!Entry("window-notice", 1)>>,
             !.protected = <<Base!Entry("window-notice", 1)>>]

CommitChildSummary(cut) ==
    /\ Scenario = "summary"
    /\ s.compaction = "legacy"
    /\ s.stage = "ready"
    /\ Base!CanUse("summary")
    /\ s.protected[cut][1] \in {"assistant", "interrupted"}
    /\ s' = [s EXCEPT !.changes = Base!Use("summary"),
             !.history = Base!WithSummary(@, cut),
             !.protected = Base!WithSummary(@, cut)]

Next ==
    \/ ChildInput \/ EmitChildRequest
    \/ Base!QueueEnvironment \/ Base!AdmitEvent
    \/ Base!FinishReply \/ Base!ModelError \/ Base!Retry \/ Base!EndFailedTurn \/ Base!InterruptReply \/ Base!Restart
    \/ \E size \in 1..2 : Base!StartBatch(size)
    \/ \E slot \in 1..2, outcome \in {"ok", "error"} : Base!SettleTool(slot, outcome)
    \/ Base!FinishBatch \/ Base!CancelBatch
    \/ ApplyRootChoices \/ RenameOwner \/ DisableSharedFeature \/ RefreshSkillCatalog
    \/ RefreshWorkspaceInstructions \/ DisableContextPlugin \/ SwitchParentModel
    \/ /\ Scenario = "prune"
       /\ \E i \in 1..Len(s.history) : Base!Prune(i)
    \/ RollChildWindow
    \/ \E cut \in 1..Len(s.protected) : CommitChildSummary(cut)

SubagentPrefixPreserved == s.bad = {}
====
