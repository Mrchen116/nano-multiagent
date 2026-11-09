---- MODULE CacheBreakpoint ----
EXTENDS Naturals

CONSTANTS Lookback, MaxAppended
VARIABLES lastBlock, messageBreakpoint, sent

\* Index 1 denotes the last content block in request one. Earlier tools and
\* system breakpoints may hit independently, but cannot recover this entry.
Init ==
    /\ lastBlock = 1
    /\ messageBreakpoint = 1
    /\ sent = FALSE

AppendBlock ==
    /\ ~sent
    /\ lastBlock < MaxAppended + 1
    /\ lastBlock' = lastBlock + 1
    /\ UNCHANGED <<messageBreakpoint, sent>>

EmitWithMovedBreakpoint ==
    /\ ~sent
    /\ lastBlock > 1
    /\ messageBreakpoint' = lastBlock
    /\ sent' = TRUE
    /\ UNCHANGED lastBlock

Next == AppendBlock \/ EmitWithMovedBreakpoint

\* The new marked position counts as the first of the lookup positions.
OldMessageBreakpointReachable ==
    ~sent \/ messageBreakpoint - 1 < Lookback
====
