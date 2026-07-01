# Kernel delta-spec: web_fetch cancel and prompt handling

This delta applies to `docs/specs/kernel/spec.md`.

## Modified Requirement: User-Initiated Interrupts

`Kernel.interrupt(session_id)` must treat a user-initiated stop as a hard boundary for the active run in that session:

- If no run is active, interrupt remains a no-op.
- If a run is active, interrupt marks the run controller as user-interrupted and forces the owned run carrier task to finish cancellation/recovery promptly.
- If a foreground stopper is registered for the session, the kernel calls it before force-cancelling the run carrier.
- The session lock must be released after interrupt recovery so the same session can accept a later user message.
- Open tool calls from the interrupted run must be closed before any later model request can include the transcript.
- User-interrupted tool recovery content must be exactly:
  `[Request interrupted by user for tool use]`
- Late results from interrupted tools must not be appended to a later run's transcript.

## Added Requirement: Tool Task Cancellation

When the agent loop is cancelled while tool calls are queued or executing, the tool executor must discard unfinished work:

- Started tool tasks are cancelled.
- Queued tool calls are not started after discard.
- User-interrupted discard preserves user-interrupt attribution for downstream transcript recovery.
- Non-user cancellation must not be reported as a user interruption.
- Discarded internal tool results are not yielded as normal tool results on the user-interrupt path.
- User-interrupted transcript closure is owned by runtime recovery, and must use exactly:
  `[Request interrupted by user for tool use]`

## Added Requirement: Async-Compatible Tool Execution

The kernel tool execution path may support tools that expose an async-native execution method while preserving existing sync tools:

- Tools with an async-native method are awaited in the active event loop so task cancellation can propagate to async I/O.
- Tools without that method continue to execute through the existing sync `run(args, ctx)` path.
- Hook dispatch, liveness events, result serialization, and error wrapping continue to be owned by the common tool registry path.
- This delta does not expand the public SDK `ToolContext` protocol.
- Cancellation is propagated to async-native tools through `asyncio.Task.cancel()` / `CancelledError`, not through a new `ToolContext` cancellation field or metadata-based run lookup.
- Both async-native and sync execution branches must remain covered by the generic execution-update ticker so long-running tool awaits do not look idle to product watchdogs.
- For sync tools that still run in worker threads, user interrupt must release the run/session and close transcript, but the underlying blocking worker may continue until its own timeout. Late sync worker returns must not append transcript output for a later run.

## Added Requirement: WebFetch Prompt Handling

The built-in `web_fetch` tool must make prompt processing outcome visible:

- If fetch succeeds and prompt processing succeeds, the tool result contains the prompt-processed content.
- If fetch succeeds but prompt processing fails, the tool result is an explicit tool error that preserves the real failure reason.
- Prompt processing must not silently fall back to the raw fetched content.
- Prompt processing uses the shared LLM client timeout/retry/cancel behavior; WebFetch must not add a separate prompt-only LLM timeout.
- If the fetched response is `text/markdown` and the content length is under the prompt-processing cap, WebFetch may return the markdown content directly without LLM prompt processing. This rule is independent of preapproved-domain permission policy.
